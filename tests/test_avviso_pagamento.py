"""Avviso di pagamento della rata al cliente: lettera da stampare ed email."""
from datetime import date, timedelta

from gestionale.models import Client, Policy, Settings, Title, db
from gestionale.titoli import add_months

OGGI = date.today()


def _polizza(app, frazionamento="semestrale"):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Officina Neri S.r.l.", referente="Paolo Neri",
                   email="paolo@officinaneri.it", indirizzo="Via Roma 1", cap="20100", citta="Milano", provincia="MI")
        db.session.add(c)
        db.session.flush()
        decorrenza = add_months(OGGI, -6) + timedelta(days=5)
        p = Policy(client_id=c.id, compagnia="Generali", numero_polizza="SEM-1", ramo="incendio", premio_annuo=1200.0,
                   frazionamento=frazionamento, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12),
                   stato="attiva")
        db.session.add(p)
        s = Settings.get()
        s.studio_nome, s.studio_pagamenti = "Studio Rossi Assicurazioni", "Bonifico IBAN IT60X0542811101000000123456"
        db.session.commit()
        return p.id, add_months(decorrenza, 6)


def test_avviso_rata_prevista_con_istruzioni_e_art_1901(client, app):
    pid, scadenza = _polizza(app)
    pagina = client.get(f"/titoli/avviso-rata/{pid}/{scadenza.isoformat()}").get_data(as_text=True)
    assert "Gentile Paolo Neri" in pagina and "rata 2/2" in pagina and "600,00" in pagina
    assert "IT60X0542811101000000123456" in pagina and "1901" in pagina and "Studio Rossi Assicurazioni" in pagina
    assert "Via Roma 1" in pagina  # indirizzo del cliente nella lettera
    # Data che non è una rata da pagare: si torna alla polizza.
    r = client.get(f"/titoli/avviso-rata/{pid}/{(scadenza + timedelta(days=3)).isoformat()}")
    assert r.status_code == 302


def test_avviso_del_titolo_inviato_per_email(client, app, monkeypatch):
    pid, scadenza = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        t = Title(policy_id=pid, client_id=p.client_id, data_effetto=scadenza, numero_rata=2, rate_totali=2,
                  data_fine_copertura=p.data_scadenza, premio_lordo=600.0, stato="da_incassare")
        db.session.add(t)
        db.session.commit()
        tid = t.id
    inviate = []
    from gestionale import mailer
    monkeypatch.setattr(mailer, "invia_al_cliente", lambda dest, ogg, testo, *a, **k: inviate.append((dest, ogg, testo)))
    assert "Avviso di pagamento al cliente" in client.get(f"/polizze/{pid}").get_data(as_text=True)
    pagina = client.get(f"/titoli/{tid}/avviso").get_data(as_text=True)
    assert "paolo@officinaneri.it" in pagina
    r = client.post(f"/titoli/{tid}/avviso", data={"destinatario": "paolo@officinaneri.it", "oggetto": "Promemoria",
                                                     "testo": "Gentile Paolo, ..."})
    assert r.status_code == 302 and inviate == [("paolo@officinaneri.it", "Promemoria", "Gentile Paolo, ...")]


def test_avviso_nella_lista_oggi(client, app):
    _polizza(app)
    pagina = client.get("/").get_data(as_text=True)
    assert "/titoli/avviso-rata/" in pagina
