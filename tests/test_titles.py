"""Test di titoli, incassi, rinnovi, foglio cassa ed estratto conto."""
from datetime import date, timedelta

import pytest

from gestionale.models import AuditLog, Client, FollowUp, Notification, Policy, Title, db
from gestionale.titoli import TitoliGiaPresenti, add_months, annualita_corrente, genera_titoli

OGGI = date.today()


def _cliente_e_polizza(app, **kw):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="ACME S.r.l.")
        db.session.add(c)
        db.session.flush()
        dati = dict(
            client_id=c.id, compagnia="Generali", numero_polizza="P-100", ramo="incendio",
            premio_annuo=1200.0, provvigione_perc=20.0, frazionamento="annuale",
            data_decorrenza=OGGI - timedelta(days=30), data_scadenza=add_months(OGGI - timedelta(days=30), 12),
            stato="attiva",
        )
        dati.update(kw)
        p = Policy(**dati)
        db.session.add(p)
        db.session.commit()
        return c.id, p.id


# ----------------------------------------------------------------------
# Calcoli puri
# ----------------------------------------------------------------------
def test_add_months_end_of_month():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)
    assert add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)


def test_genera_titoli_mensile_somma_esatta(app):
    _, pid = _cliente_e_polizza(app, premio_annuo=1000.0, frazionamento="mensile")
    with app.app_context():
        p = db.session.get(Policy, pid)
        titoli = genera_titoli(p)
        assert len(titoli) == 12
        assert round(sum(t.premio_lordo for t in titoli), 2) == 1000.0
        assert titoli[0].premio_lordo == 83.33 and titoli[-1].premio_lordo == 83.37
        inizio, fine = annualita_corrente(p)
        assert titoli[0].data_effetto == inizio
        assert titoli[1].data_effetto == add_months(inizio, 1)
        assert titoli[-1].data_fine_copertura == fine
        assert titoli[0].tipo == "perfezionamento" and titoli[1].tipo == "rata"
        assert titoli[0].provvigione == round(83.33 * 0.2, 2)


def test_genera_titoli_quietanza_per_polizza_vecchia(app):
    _, pid = _cliente_e_polizza(
        app, frazionamento="semestrale",
        data_decorrenza=OGGI - timedelta(days=1000), data_scadenza=OGGI + timedelta(days=100),
    )
    with app.app_context():
        titoli = genera_titoli(db.session.get(Policy, pid))
        assert [t.tipo for t in titoli] == ["quietanza", "rata"]
        assert [t.premio_lordo for t in titoli] == [600.0, 600.0]


def test_genera_titoli_rifiuta_duplicati_e_premio_mancante(app):
    _, pid = _cliente_e_polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p)
        db.session.commit()
        with pytest.raises(TitoliGiaPresenti):
            genera_titoli(p)
        p.premio_annuo = None
        with pytest.raises(ValueError):
            genera_titoli(p, inizio=add_months(p.data_scadenza, 0), fine=add_months(p.data_scadenza, 12))


def test_copertura_sospesa_art_1901(app):
    with app.app_context():
        primo = Title(tipo="perfezionamento", data_effetto=OGGI - timedelta(days=1), premio_lordo=10, stato="da_incassare")
        rata_10 = Title(tipo="rata", data_effetto=OGGI - timedelta(days=10), premio_lordo=10, stato="da_incassare")
        rata_20 = Title(tipo="rata", data_effetto=OGGI - timedelta(days=20), premio_lordo=10, stato="da_incassare")
        pagata = Title(tipo="rata", data_effetto=OGGI - timedelta(days=20), premio_lordo=10, stato="incassato")
        assert primo.copertura_sospesa
        assert rata_10.arretrato and not rata_10.copertura_sospesa
        assert rata_10.data_sospensione == rata_10.data_effetto + timedelta(days=15)
        assert rata_20.copertura_sospesa
        assert not pagata.copertura_sospesa and not pagata.arretrato


# ----------------------------------------------------------------------
# Percorsi HTTP
# ----------------------------------------------------------------------
def test_nuova_polizza_genera_titoli(client, app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Beta")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = client.post(f"/polizze/nuova/{cid}", data={
        "compagnia": "Allianz", "numero_polizza": "AL-1", "ramo": "rct_rco", "stato": "attiva",
        "premio_annuo": "2.400,00", "provvigione_perc": "15", "frazionamento": "trimestrale",
        "data_decorrenza": OGGI.isoformat(), "data_scadenza": add_months(OGGI, 12).isoformat(),
        "genera_titoli": "on",
    })
    assert resp.status_code == 302
    with app.app_context():
        p = Policy.query.filter_by(numero_polizza="AL-1").one()
        assert p.premio_annuo == 2400.0
        assert len(p.titoli) == 4
        assert all(t.premio_lordo == 600.0 for t in p.titoli)
    assert client.get(resp.headers["Location"]).status_code == 200


def test_polizza_scadenza_prima_della_decorrenza_rifiutata(client, app):
    cid, _ = _cliente_e_polizza(app)
    client.post(f"/polizze/nuova/{cid}", data={
        "compagnia": "X", "numero_polizza": "BAD", "data_decorrenza": OGGI.isoformat(),
        "data_scadenza": (OGGI - timedelta(days=1)).isoformat(),
    })
    with app.app_context():
        assert Policy.query.filter_by(numero_polizza="BAD").count() == 0


def test_incasso_annullamento_e_storno(client, app):
    _, pid = _cliente_e_polizza(app, frazionamento="semestrale")
    client.post(f"/polizze/{pid}/genera-titoli")
    with app.app_context():
        t1, t2 = db.session.get(Policy, pid).titoli
        t1_id, t2_id = t1.id, t2.id

    resp = client.post(f"/titoli/{t1_id}/incassa", data={
        "data_incasso": OGGI.isoformat(), "mezzo_pagamento": "bonifico", "riferimento": "CRO123",
    })
    assert resp.status_code == 302
    with app.app_context():
        t = db.session.get(Title, t1_id)
        assert t.stato == "incassato" and t.mezzo_pagamento == "bonifico"
        assert t.incassato_da == "admin" and t.riferimento_pagamento == "CRO123"
        assert AuditLog.query.filter_by(azione="incasso", entita_id=t1_id).count() == 1

    # Data di incasso futura rifiutata.
    client.post(f"/titoli/{t2_id}/incassa", data={"data_incasso": (OGGI + timedelta(days=3)).isoformat()})
    with app.app_context():
        assert db.session.get(Title, t2_id).stato == "da_incassare"

    client.post(f"/titoli/{t1_id}/annulla-incasso")
    with app.app_context():
        assert db.session.get(Title, t1_id).stato == "da_incassare"

    client.post(f"/titoli/{t2_id}/storna", data={"motivo": "disdetta"})
    with app.app_context():
        t = db.session.get(Title, t2_id)
        assert t.stato == "stornato" and "disdetta" in t.note


def test_incasso_parziale_rifiutato(client, app):
    _, pid = _cliente_e_polizza(app)
    client.post(f"/polizze/{pid}/genera-titoli")
    with app.app_context():
        tid = db.session.get(Policy, pid).titoli[0].id
    resp = client.post(f"/titoli/{tid}/incassa", data={"importo": "600,00", "mezzo_pagamento": "pos"},
                       follow_redirects=True)
    assert "incassi parziali non sono ammessi" in resp.get_data(as_text=True)
    with app.app_context():
        t = db.session.get(Title, tid)
        assert t.stato == "da_incassare" and t.premio_lordo == 1200.0 and t.provvigione == 240.0
    # Senza mezzo di pagamento l'incasso non si registra.
    client.post(f"/titoli/{tid}/incassa", data={})
    with app.app_context():
        assert db.session.get(Title, tid).stato == "da_incassare"
    # Data di incasso futura: rifiutata.
    client.post(f"/titoli/{tid}/incassa", data={
        "mezzo_pagamento": "pos", "data_incasso": (OGGI + timedelta(days=1)).isoformat()})
    with app.app_context():
        assert db.session.get(Title, tid).stato == "da_incassare"
    client.post(f"/titoli/{tid}/incassa", data={"importo": "1.200,00", "mezzo_pagamento": "pos"})
    with app.app_context():
        assert db.session.get(Title, tid).stato == "incassato"


def test_polizza_e_cliente_con_incassi_non_eliminabili(client, app):
    cid, pid = _cliente_e_polizza(app)
    client.post(f"/polizze/{pid}/genera-titoli")
    with app.app_context():
        tid = db.session.get(Policy, pid).titoli[0].id
    client.post(f"/titoli/{tid}/incassa", data={"mezzo_pagamento": "contanti"})
    client.post(f"/polizze/{pid}/elimina")
    client.post(f"/clienti/{cid}/elimina")
    client.post(f"/titoli/{tid}/elimina")
    with app.app_context():
        assert db.session.get(Policy, pid) is not None
        assert db.session.get(Client, cid) is not None
        assert db.session.get(Title, tid) is not None


def test_rinnovo_polizza(client, app):
    cid, pid = _cliente_e_polizza(app, frazionamento="semestrale")
    with app.app_context():
        p = db.session.get(Policy, pid)
        vecchia = p.data_scadenza
        db.session.add(FollowUp(client_id=cid, policy_id=pid, tipo="rinnovo", titolo="Rinnovo",
                                data_scadenza=OGGI, auto_generato=True))
        db.session.commit()
    resp = client.post(f"/polizze/{pid}/rinnova", data={"nuovo_premio": "1300", "genera_titoli": "on"})
    assert resp.status_code == 302
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.data_scadenza == add_months(vecchia, 12)
        assert p.premio_annuo == 1300.0
        assert [t.tipo for t in p.titoli] == ["quietanza", "rata"]
        assert p.titoli[0].data_effetto == vecchia
        assert FollowUp.query.filter_by(policy_id=pid, stato="aperto").count() == 0
        assert AuditLog.query.filter_by(azione="rinnovo", entita_id=pid).count() == 1


def test_rinnovo_rifiuta_scadenza_precedente(client, app):
    _, pid = _cliente_e_polizza(app)
    with app.app_context():
        vecchia = db.session.get(Policy, pid).data_scadenza
    client.post(f"/polizze/{pid}/rinnova", data={"nuova_scadenza": (vecchia - timedelta(days=1)).isoformat()})
    with app.app_context():
        assert db.session.get(Policy, pid).data_scadenza == vecchia


def test_notifiche_titoli_e_chiusura_dopo_incasso(client, app):
    _, pid = _cliente_e_polizza(
        app, data_decorrenza=OGGI - timedelta(days=400), data_scadenza=OGGI + timedelta(days=325),
        frazionamento="annuale",
    )
    # Titolo scaduto da 20 giorni: copertura sospesa.
    with app.app_context():
        p = db.session.get(Policy, pid)
        t = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza",
                  data_effetto=OGGI - timedelta(days=20), premio_lordo=1200.0)
        db.session.add(t)
        db.session.commit()
        tid = t.id
    client.get("/")
    with app.app_context():
        chiave = f"titolo:{tid}:{(OGGI - timedelta(days=20)).isoformat()}:sospesa"
        n = Notification.query.filter_by(dedup_key=chiave).one()
        assert n.livello == "danger" and not n.letta
    client.post(f"/titoli/{tid}/incassa", data={"mezzo_pagamento": "bonifico"})
    with app.app_context():
        assert Notification.query.filter_by(dedup_key=chiave).one().letta


def test_foglio_cassa_ed_estratto_conto(client, app):
    _, pid = _cliente_e_polizza(app, frazionamento="semestrale")
    client.post(f"/polizze/{pid}/genera-titoli")
    with app.app_context():
        ids = [t.id for t in db.session.get(Policy, pid).titoli]
    for tid, mezzo in zip(ids, ("bonifico", "contanti")):
        client.post(f"/titoli/{tid}/incassa", data={"mezzo_pagamento": mezzo})

    pagina = client.get("/titoli/foglio-cassa").get_data(as_text=True)
    assert "€ 1.200,00" in pagina  # totale incassato
    assert "Contanti" in pagina and "Bonifico" in pagina

    csv = client.get("/titoli/foglio-cassa.csv")
    testo = csv.get_data(as_text=True)
    assert testo.startswith("﻿") and ";" in testo and "600,00" in testo

    periodo = {"dal": OGGI.replace(day=1).isoformat(), "al": OGGI.isoformat()}
    pagina = client.get("/titoli/estratto-conto", query_string=periodo).get_data(as_text=True)
    assert "Generali" in pagina and "€ 960,00" in pagina  # netto = 1200 - 20%

    # Senza la conferma dei titoli (ids) non si rimette nulla.
    client.post("/titoli/estratto-conto/rimessa", data={**periodo, "compagnia": "Generali",
                                                         "data_rimessa": OGGI.isoformat()})
    with app.app_context():
        assert all(db.session.get(Title, i).data_rimessa is None for i in ids)
    client.post("/titoli/estratto-conto/rimessa", data={
        **periodo, "compagnia": "Generali", "ids": ids, "data_rimessa": OGGI.isoformat()})
    with app.app_context():
        assert all(db.session.get(Title, i).data_rimessa == OGGI for i in ids)
    # Dopo la rimessa l'incasso non si può più annullare.
    client.post(f"/titoli/{ids[0]}/annulla-incasso")
    with app.app_context():
        assert db.session.get(Title, ids[0]).stato == "incassato"


def test_portafoglio_titoli_viste_ed_export(client, app):
    _, pid = _cliente_e_polizza(app, frazionamento="trimestrale",
                                data_decorrenza=OGGI - timedelta(days=200),
                                data_scadenza=OGGI + timedelta(days=165))
    client.post(f"/polizze/{pid}/genera-titoli")
    for vista in ("da_incassare", "arretrati", "incassati", "stornati", "tutti", "sconosciuta"):
        assert client.get(f"/titoli/?vista={vista}").status_code == 200
    resp = client.get("/titoli/esporta.csv?vista=tutti")
    righe = resp.get_data(as_text=True).strip().splitlines()
    assert len(righe) == 5  # intestazione + 4 rate
