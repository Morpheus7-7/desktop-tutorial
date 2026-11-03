"""Scadenzario: rate del frazionamento da far pagare anche senza titoli emessi."""
from datetime import date, timedelta

from gestionale.agenda import eventi_agenda
from gestionale.models import Client, Policy, db
from gestionale.titoli import add_months, genera_titoli, rate_previste

OGGI = date.today()


def _polizza(app, frazionamento, decorrenza, **kw):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="ACME S.r.l.")
        db.session.add(c)
        db.session.flush()
        p = Policy(client_id=c.id, compagnia="Generali", numero_polizza=f"P-{frazionamento}", ramo="incendio",
                   premio_annuo=1200.0, frazionamento=frazionamento, data_decorrenza=decorrenza,
                   data_scadenza=add_months(decorrenza, 12), stato="attiva", **kw)
        db.session.add(p)
        db.session.commit()
        return p.id


def test_semestralita_ricordata_senza_titoli(client, app):
    # Polizza semestrale decorsa 5 mesi fa: la seconda semestralità scade tra circa un mese.
    pid = _polizza(app, "semestrale", add_months(OGGI, -5))
    with app.app_context():
        p = db.session.get(Policy, pid)
        previste = rate_previste(p, OGGI, OGGI + timedelta(days=90))
        assert [(r["numero"], r["totali"], r["premio"]) for r in previste] == [(2, 2, 600.0)]
        assert previste[0]["data"] == add_months(OGGI, 1)
    pagina = client.get("/scadenzario?giorni=90").get_data(as_text=True)
    assert "Rate del frazionamento da far pagare" in pagina and "rata 2/2" in pagina and "P-semestrale" in pagina


def test_rata_gia_emessa_o_stornata_non_ricordata(app):
    pid = _polizza(app, "trimestrale", add_months(OGGI, -2))
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert len(rate_previste(p, OGGI, OGGI + timedelta(days=365))) == 3  # rate 2, 3 e 4
        titoli = genera_titoli(p)
        titoli[2].stato = "stornato"
        db.session.commit()
        assert rate_previste(p, OGGI - timedelta(days=60), OGGI + timedelta(days=365)) == []


def test_mensile_bimestrale_e_annuale(app):
    with app.app_context():
        pm = db.session.get(Policy, _polizza(app, "mensile", OGGI))
        pb = db.session.get(Policy, _polizza(app, "bimestrale", OGGI))
        pa = db.session.get(Policy, _polizza(app, "annuale", OGGI))
        un_anno = OGGI + timedelta(days=364)
        assert len(rate_previste(pm, OGGI, un_anno)) == 12 and rate_previste(pm, OGGI, un_anno)[0]["premio"] == 100.0
        assert len(rate_previste(pb, OGGI, un_anno)) == 6
        assert rate_previste(pa, OGGI, un_anno) == []  # annuale: basta la scadenza


def test_calendario_con_le_rate_da_far_pagare(client, app):
    _polizza(app, "semestrale", add_months(OGGI, -5))
    with app.test_request_context():
        eventi = [e for e in eventi_agenda(OGGI, OGGI + timedelta(days=90), {"rata"})]
        assert any("da far pagare" in e.titolo and "rata 2/2" in e.dettaglio for e in eventi)
    ics = client.get("/scadenzario.ics?giorni=90").get_data(as_text=True)
    assert "da far pagare" in ics


def test_polizza_disdetta_o_scaduta_non_genera_promemoria(app):
    pid = _polizza(app, "semestrale", add_months(OGGI, -5))
    with app.app_context():
        p = db.session.get(Policy, pid)
        p.stato = "disdetta"
        db.session.commit()
        assert rate_previste(p, OGGI, OGGI + timedelta(days=90)) == []
