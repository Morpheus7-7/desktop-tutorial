"""Rate da far pagare in «Oggi», nelle notifiche e nei promemoria; preavvisi scelti in Impostazioni."""
from datetime import date, timedelta

from gestionale import promemoria
from gestionale.models import Client, Notification, Policy, Settings, Title, db
from gestionale.notifications import generate_notifications
from gestionale.titoli import add_months

OGGI = date.today()


def _polizza(app, frazionamento="semestrale", decorrenza=None, **kw):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Officina Neri S.r.l.")
        db.session.add(c)
        db.session.flush()
        decorrenza = decorrenza or (add_months(OGGI, -6) + timedelta(days=5))
        p = Policy(client_id=c.id, compagnia="Generali", numero_polizza="SEM-1", ramo="incendio",
                   premio_annuo=1200.0, frazionamento=frazionamento, data_decorrenza=decorrenza,
                   data_scadenza=add_months(decorrenza, 12), stato="attiva", **kw)
        db.session.add(p)
        db.session.commit()
        return p.id


def test_rata_frazionata_in_oggi_e_nelle_notifiche(client, app):
    # Semestrale: la seconda rata scade tra 5 giorni e non c'è ancora il titolo.
    _polizza(app)
    pagina = client.get("/").get_data(as_text=True)
    assert "Rata 2/2 da far pagare" in pagina and "Polizza SEM-1" in pagina
    with app.app_context():
        generate_notifications()
        assert Notification.query.filter(Notification.dedup_key.like("rata_prevista:%")).count() == 1
        elementi = promemoria.elementi_di_oggi()
        assert any(e["tipo"] == "rata" for e in elementi)
        titolo, _ = promemoria.messaggio(elementi, nuove=set())
        assert "1 rata da incassare" in titolo


def test_quietanza_arretrata_in_ritardo_con_incassa(client, app):
    pid = _polizza(app, frazionamento="annuale", decorrenza=add_months(OGGI, -1))
    with app.app_context():
        p = db.session.get(Policy, pid)
        db.session.add(Title(policy_id=pid, client_id=p.client_id, data_effetto=OGGI - timedelta(days=10),
                             data_fine_copertura=OGGI + timedelta(days=355), premio_lordo=1200.0, stato="da_incassare"))
        db.session.commit()
    pagina = client.get("/").get_data(as_text=True)
    assert "Quietanza da incassare" in pagina and "In ritardo" in pagina and "Incassa" in pagina


def test_preavvisi_scelti_in_impostazioni(client, app):
    r = client.post("/impostazioni/automatismi", data={
        "anticipo_quietanze_giorni": "30", "tolleranza_scadenza_giorni": "30",
        "preavvisi_scadenze": "45; 10", "preavviso_rate_giorni": "20"})
    assert r.status_code == 302
    with app.app_context():
        s = Settings.get()
        assert s.giorni_preavviso_scadenze == [45, 10] and s.giorni_preavviso_rate == 20
    # Polizza annuale in scadenza tra 40 giorni: avviso alla soglia dei 45 giorni.
    _polizza(app, frazionamento="annuale", decorrenza=add_months(OGGI, -12) + timedelta(days=40))
    with app.app_context():
        generate_notifications()
        assert Notification.query.filter(Notification.dedup_key.like("polizza:%:45")).count() == 1
    r = client.post("/impostazioni/automatismi", data={
        "anticipo_quietanze_giorni": "30", "tolleranza_scadenza_giorni": "30",
        "preavvisi_scadenze": "presto", "preavviso_rate_giorni": "20"}, follow_redirects=True)
    assert "Preavvisi delle scadenze" in r.get_data(as_text=True)
    with app.app_context():
        assert Settings.get().giorni_preavviso_scadenze == [45, 10]  # niente salvato con l'errore
