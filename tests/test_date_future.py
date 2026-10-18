"""Test delle date future: periodi di polizza, disdetta, automatismi, previsione
incassi, agenda/calendario e delle correzioni emerse dalla verifica."""
import io
import re
from datetime import date, timedelta

from flask import template_rendered

from gestionale.agenda import _ics_piega, eventi_agenda
from gestionale.automatismi import emetti_quietanze, rinnova_taciti, scadi_polizze
from gestionale.models import (
    AuditLog,
    Claim,
    Client,
    FollowUp,
    Notification,
    Opportunity,
    Policy,
    Settings,
    Title,
    db,
)
from gestionale.notifications import aggiungi_notifica
from gestionale.routes.titles import calcola_previsione
from gestionale.titoli import add_months, genera_titoli, periodi_polizza

OGGI = date.today()


def _cliente(app, nome="ACME S.r.l."):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale=nome)
        db.session.add(c)
        db.session.commit()
        return c.id


def _polizza(app, client_id=None, **kw):
    client_id = client_id or _cliente(app)
    with app.app_context():
        dati = dict(
            client_id=client_id, compagnia="Generali", numero_polizza=f"P-{kw.pop('n', 1)}", ramo="incendio",
            premio_annuo=1200.0, provvigione_perc=20.0, frazionamento="annuale",
            data_decorrenza=OGGI - timedelta(days=30), data_scadenza=add_months(OGGI - timedelta(days=30), 12),
            stato="attiva",
        )
        dati.update(kw)
        p = Policy(**dati)
        db.session.add(p)
        db.session.commit()
        return p.id


class _Contesti:
    """Raccoglie i contesti dei template resi durante una richiesta."""

    def __init__(self, app):
        self.app, self.elenco = app, []

    def __enter__(self):
        template_rendered.connect(self._registra, self.app)
        return self.elenco

    def __exit__(self, *exc):
        template_rendered.disconnect(self._registra, self.app)

    def _registra(self, sender, template, context, **extra):
        self.elenco.append((template.name, context))


# ----------------------------------------------------------------------
# Periodi di polizza e generazione dei titoli
# ----------------------------------------------------------------------
def test_periodi_poliennale_e_rateo(app):
    pid = _polizza(app, data_decorrenza=date(2026, 11, 15), data_scadenza=date(2029, 12, 31))
    with app.app_context():
        periodi = periodi_polizza(db.session.get(Policy, pid))
    assert periodi[0] == (date(2026, 11, 15), date(2026, 12, 31))  # rateo iniziale
    assert periodi[1:] == [
        (date(2026, 12, 31), date(2027, 12, 31)),
        (date(2027, 12, 31), date(2028, 12, 31)),
        (date(2028, 12, 31), date(2029, 12, 31)),
    ]


def test_rateo_pro_rata_e_perfezionamento(app):
    pid = _polizza(app, data_decorrenza=date(2026, 11, 15), data_scadenza=date(2027, 12, 31),
                   frazionamento="semestrale")
    with app.app_context():
        p = db.session.get(Policy, pid)
        titoli = genera_titoli(p, date(2026, 11, 15), date(2026, 12, 31))
        assert len(titoli) == 1 and titoli[0].tipo == "perfezionamento"
        # 46 giorni su 365: 1200 * 46 / 365 = 151,23
        assert titoli[0].premio_lordo == 151.23
        assert titoli[0].data_fine_copertura == date(2026, 12, 31)


def test_genera_titoli_di_un_annualita_futura(client, app):
    decorrenza = OGGI - timedelta(days=10)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 36))
    seconda = add_months(decorrenza, 12)
    client.post(f"/polizze/{pid}/genera-titoli", data={"inizio": seconda.isoformat()})
    with app.app_context():
        titoli = db.session.get(Policy, pid).titoli
        assert [t.data_effetto for t in titoli] == [seconda]
        assert titoli[0].tipo == "quietanza"
    # Un inizio che non corrisponde a un'annualità viene rifiutato; l'emissione
    # automatica non crea mai da sé il primo premio (già iniziato) della polizza.
    client.post(f"/polizze/{pid}/genera-titoli", data={"inizio": (seconda + timedelta(days=3)).isoformat()})
    with app.app_context():
        effetti = sorted(t.data_effetto for t in db.session.get(Policy, pid).titoli)
        assert effetti == [seconda]


def test_polizza_non_ancora_in_vigore(client, app):
    cid = _cliente(app)
    decorrenza = OGGI + timedelta(days=20)
    pid = _polizza(app, cid, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12))
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.non_ancora_in_vigore and p.stato_effettivo == "non_in_vigore"
        assert p not in db.session.get(Client, cid).polizze_attive
    pagina = client.get(f"/polizze/{pid}").get_data(as_text=True)
    assert "non è ancora in vigore" in pagina and "tra 20 giorni" in pagina
    elenco = client.get("/polizze/?stato=non_in_vigore").get_data(as_text=True)
    assert "P-1" in elenco


# ----------------------------------------------------------------------
# Disdetta
# ----------------------------------------------------------------------
def test_disdetta_alla_scadenza_e_annullo(client, app):
    decorrenza = OGGI - timedelta(days=200)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 24),
                   tacito_rinnovo=True, preavviso_disdetta_giorni=60)
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p, add_months(decorrenza, 12), add_months(decorrenza, 24))  # annualità futura
        db.session.commit()
        assert p.termine_disdetta == p.data_scadenza - timedelta(days=60)
    client.post(f"/polizze/{pid}/disdetta", data={"data_disdetta": OGGI.isoformat(), "effetto": "scadenza"})
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.data_disdetta == OGGI and p.stato == "attiva" and p.disdetta_inviata
        assert not p.disdetta_tardiva
        # Le rate fino alla scadenza restano dovute: nessuno storno.
        assert all(t.stato != "stornato" for t in p.titoli)
    pagina = client.get(f"/polizze/{pid}").get_data(as_text=True)
    assert "Disdetta inviata il" in pagina
    client.post(f"/polizze/{pid}/annulla-disdetta")
    with app.app_context():
        assert db.session.get(Policy, pid).data_disdetta is None


def test_disdetta_futura_rifiutata_e_immediata_storna(client, app):
    pid = _polizza(app, frazionamento="trimestrale")
    with app.app_context():
        genera_titoli(db.session.get(Policy, pid))
        db.session.commit()
    client.post(f"/polizze/{pid}/disdetta", data={
        "data_disdetta": (OGGI + timedelta(days=1)).isoformat(), "effetto": "scadenza"})
    with app.app_context():
        assert db.session.get(Policy, pid).data_disdetta is None
    client.post(f"/polizze/{pid}/disdetta", data={
        "data_disdetta": OGGI.isoformat(), "effetto": "immediato", "data_cessazione": OGGI.isoformat(),
        "motivo": "vendita del bene"})
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.stato == "disdetta"
        future = [t for t in p.titoli if t.data_effetto >= OGGI]
        assert future and all(t.stato == "stornato" and "vendita del bene" in t.note for t in future)


# ----------------------------------------------------------------------
# Rinnovo
# ----------------------------------------------------------------------
def test_rinnovo_pluriennale_richiede_conferma(client, app):
    pid = _polizza(app)
    with app.app_context():
        vecchia = db.session.get(Policy, pid).data_scadenza
    tre_anni = add_months(vecchia, 36)
    client.post(f"/polizze/{pid}/rinnova", data={"nuova_scadenza": tre_anni.isoformat(), "genera_titoli": "on"})
    with app.app_context():
        assert db.session.get(Policy, pid).data_scadenza == vecchia
    client.post(f"/polizze/{pid}/rinnova", data={
        "nuova_scadenza": tre_anni.isoformat(), "genera_titoli": "on", "pluriennale": "on"})
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.data_scadenza == tre_anni
        # Solo la prima annualità rinnovata: le altre all'anniversario.
        assert [t.data_effetto for t in p.titoli] == [vecchia]
        assert p.titoli[0].data_fine_copertura == add_months(vecchia, 12)


def test_rinnovo_oltre_dieci_anni_rifiutato(client, app):
    pid = _polizza(app)
    with app.app_context():
        vecchia = db.session.get(Policy, pid).data_scadenza
    client.post(f"/polizze/{pid}/rinnova", data={
        "nuova_scadenza": add_months(vecchia, 12 * 11).isoformat(), "pluriennale": "on"})
    with app.app_context():
        assert db.session.get(Policy, pid).data_scadenza == vecchia


# ----------------------------------------------------------------------
# Automatismi (con una data «oggi» simulata)
# ----------------------------------------------------------------------
def test_rinnovo_tacito_automatico(app):
    scadenza = OGGI - timedelta(days=2)
    pid = _polizza(app, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza, tacito_rinnovo=True)
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p, add_months(scadenza, -12), scadenza)
        db.session.commit()
        assert rinnova_taciti(OGGI, Settings.get()) == 1
        db.session.commit()
        p = db.session.get(Policy, pid)
        assert p.data_scadenza == add_months(scadenza, 12)
        nuove = [t for t in p.titoli if t.data_effetto == scadenza]
        assert len(nuove) == 1 and nuove[0].tipo == "quietanza"
        assert AuditLog.query.filter_by(username="sistema", azione="rinnovo").count() == 1
        # Idempotente: un secondo giro non rinnova di nuovo.
        assert rinnova_taciti(OGGI, Settings.get()) == 0


def test_rinnovo_tacito_disattivabile_e_rispetta_la_disdetta(app):
    scadenza = OGGI - timedelta(days=2)
    pid = _polizza(app, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza, tacito_rinnovo=True,
                   data_disdetta=scadenza - timedelta(days=90))
    with app.app_context():
        assert rinnova_taciti(OGGI, Settings.get()) == 0
        db.session.get(Policy, pid).data_disdetta = None
        impostazioni = Settings.get()
        impostazioni.rinnovo_tacito_automatico = False
        assert rinnova_taciti(OGGI, impostazioni) == 0


def test_emissione_quietanze_all_anniversario(app):
    decorrenza = OGGI - timedelta(days=350)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 36))
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p, decorrenza, add_months(decorrenza, 12))
        db.session.commit()
        impostazioni = Settings.get()
        impostazioni.anticipo_quietanze_giorni = 30
        assert emetti_quietanze(OGGI, impostazioni) == 1
        db.session.commit()
        effetti = sorted(t.data_effetto for t in db.session.get(Policy, pid).titoli)
        assert effetti == [decorrenza, add_months(decorrenza, 12)]
        assert emetti_quietanze(OGGI, impostazioni) == 0


def test_scadenza_automatica_dopo_la_tolleranza(app):
    scadenza = OGGI - timedelta(days=40)
    pid = _polizza(app, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza)
    pid_tacita = _polizza(app, n=2, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza,
                          tacito_rinnovo=True)
    with app.app_context():
        impostazioni = Settings.get()
        impostazioni.tolleranza_scadenza_giorni = 60
        assert scadi_polizze(OGGI, impostazioni) == 0
        impostazioni.tolleranza_scadenza_giorni = 30
        assert scadi_polizze(OGGI, impostazioni) == 1
        db.session.commit()
        assert db.session.get(Policy, pid).stato == "scaduta"
        assert db.session.get(Policy, pid_tacita).stato == "attiva"  # la gestisce il rinnovo tacito


# ----------------------------------------------------------------------
# Previsione incassi
# ----------------------------------------------------------------------
def test_previsione_emesse_e_stimate(client, app):
    decorrenza = OGGI - timedelta(days=200)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12),
                   frazionamento="semestrale")
    with app.app_context():
        genera_titoli(db.session.get(Policy, pid))
        db.session.commit()
        dati = calcola_previsione(12, oggi=OGGI)
    rate = [decorrenza, add_months(decorrenza, 6)]
    rinnovo = add_months(decorrenza, 12)
    fine_orizzonte = add_months(OGGI.replace(day=1), 12)
    assert dati["totale_emessi"] == 600.0 * sum(1 for d in rate if OGGI <= d < fine_orizzonte)
    assert dati["arretrati"] == 600.0 * sum(1 for d in rate if d < OGGI)
    # Il rinnovo stimato: rate semestrali da 600 € dentro l'orizzonte.
    attese = [d for d in (rinnovo, add_months(rinnovo, 6)) if OGGI <= d < fine_orizzonte]
    assert dati["totale_stimati"] == 600.0 * len(attese)
    pagina = client.get("/titoli/previsione?mesi=12").get_data(as_text=True)
    assert "Previsione incassi" in pagina and "Quietanze stimate" in pagina
    csv = client.get("/titoli/previsione.csv").get_data(as_text=True)
    assert csv.startswith("﻿") and "Rate stimate" in csv


def test_previsione_esclude_le_polizze_disdette(app):
    decorrenza = OGGI - timedelta(days=200)
    _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12),
             data_disdetta=OGGI - timedelta(days=1))
    with app.app_context():
        assert calcola_previsione(24, oggi=OGGI)["totale_stimati"] == 0.0


# ----------------------------------------------------------------------
# Estratto conto: arretrati dei periodi precedenti e annullo rimessa
# ----------------------------------------------------------------------
def test_estratto_conto_include_incassi_precedenti_non_rimessi(client, app):
    pid = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        t = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza", data_effetto=OGGI - timedelta(days=90),
                  premio_lordo=500.0, provvigione=100.0, stato="incassato",
                  data_incasso=OGGI - timedelta(days=80), mezzo_pagamento="bonifico")
        db.session.add(t)
        db.session.commit()
        tid = t.id
    periodo = {"dal": (OGGI - timedelta(days=5)).isoformat(), "al": OGGI.isoformat()}
    with _Contesti(app) as contesti:
        client.get("/titoli/estratto-conto", query_string=periodo)
    ctx = dict(contesti)["titles/statement.html"]
    riga = ctx["righe"][0]
    assert riga["numero"] == 0 and riga["arretrato_precedente"] == 400.0 and riga["ids"] == [tid]
    client.post("/titoli/estratto-conto/rimessa", data={
        **periodo, "compagnia": "Generali", "ids": [tid], "data_rimessa": OGGI.isoformat()})
    with app.app_context():
        assert db.session.get(Title, tid).data_rimessa == OGGI
    # Data della rimessa futura: rifiutata (dopo l'annullo).
    client.post("/titoli/estratto-conto/annulla-rimessa", data={"compagnia": "Generali",
                                                                "data_rimessa": OGGI.isoformat()})
    with app.app_context():
        assert db.session.get(Title, tid).data_rimessa is None
    client.post("/titoli/estratto-conto/rimessa", data={
        **periodo, "compagnia": "Generali", "ids": [tid], "data_rimessa": (OGGI + timedelta(days=2)).isoformat()})
    with app.app_context():
        assert db.session.get(Title, tid).data_rimessa is None


# ----------------------------------------------------------------------
# Agenda e calendario
# ----------------------------------------------------------------------
def test_agenda_e_calendario_ics(client, app):
    cid = _cliente(app, "Rossi S.r.l.")
    decorrenza = OGGI + timedelta(days=10)
    _polizza(app, cid, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12))
    scadenza = OGGI + timedelta(days=50)
    _polizza(app, cid, n=2, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza,
             tacito_rinnovo=True, preavviso_disdetta_giorni=30)
    with app.app_context():
        c = db.session.get(Client, cid)
        c.documento_scadenza = OGGI + timedelta(days=15)
        db.session.add(Claim(client_id=cid, numero="SIN-T-1", tipologia="altro", stato="aperto",
                             data_evento=OGGI - timedelta(days=1)))
        db.session.commit()
    # La prima richiesta esegue anche gli automatismi (es. il follow-up di rinnovo
    # della polizza a tacito rinnovo, che arriva prima del termine di disdetta).
    pagina = client.get("/scadenzario?giorni=60").get_data(as_text=True)
    assert "Agenda: altre scadenze" in pagina and "Termine disdetta" in pagina
    with app.test_request_context():
        eventi = eventi_agenda(OGGI, OGGI + timedelta(days=60))
    tipi = {e.tipo for e in eventi}
    assert {"decorrenza", "disdetta", "documento", "denuncia", "scadenza", "followup"} <= tipi
    disdetta = next(e for e in eventi if e.tipo == "disdetta")
    assert disdetta.data == scadenza - timedelta(days=30)
    followup = next(e for e in eventi if e.tipo == "followup")
    assert followup.data <= disdetta.data  # il promemoria arriva prima del termine
    assert [e.data for e in eventi] == sorted(e.data for e in eventi)

    resp = client.get("/scadenzario.ics?giorni=60")
    assert resp.mimetype == "text/calendar"
    testo = resp.get_data(as_text=True)
    assert testo.startswith("BEGIN:VCALENDAR\r\n") and testo.rstrip().endswith("END:VCALENDAR")
    assert testo.count("BEGIN:VEVENT") == len(eventi)
    assert f"DTSTART;VALUE=DATE:{decorrenza:%Y%m%d}" in testo
    assert all(len(r.encode("utf-8")) <= 75 for r in testo.split("\r\n"))


def test_ics_piega_righe_lunghe():
    righe = _ics_piega("SUMMARY:" + "è" * 100)
    assert len(righe) > 1 and all(len(r.encode("utf-8")) <= 75 for r in righe)
    assert all(r.startswith(" ") for r in righe[1:])
    assert "".join(r[1:] if i else r for i, r in enumerate(righe)) == "SUMMARY:" + "è" * 100


# ----------------------------------------------------------------------
# Sinistri
# ----------------------------------------------------------------------
def test_nuovo_sinistro_senza_data_denuncia_predefinita(client, app):
    cid = _cliente(app)
    pagina = client.get(f"/sinistri/nuovo?client_id={cid}").get_data(as_text=True)
    assert 'name="data_denuncia" min="1900-01-01"' in pagina
    assert f'value="{OGGI.isoformat()}"' not in pagina.split('name="data_denuncia"')[1].split(">")[0]


def test_sinistro_date_future_e_liquidato_senza_importo(client, app):
    cid = _cliente(app)
    pid = _polizza(app, cid)
    evento = (OGGI - timedelta(days=5)).isoformat()
    resp = client.post("/sinistri/nuovo", data={
        "client_id": cid, "policy_id": pid, "tipologia": "danni_terzi", "data_evento": evento,
        "data_denuncia": (OGGI + timedelta(days=30)).isoformat(), "luogo": "Milano"})
    assert resp.status_code == 400 and "Milano" in resp.get_data(as_text=True)
    with app.app_context():
        assert Claim.query.count() == 0
    client.post("/sinistri/nuovo", data={"client_id": cid, "policy_id": pid, "tipologia": "danni_terzi",
                                         "data_evento": evento})
    with app.app_context():
        s = Claim.query.one()
        sid = s.id
        s.stato, s.importo_liquidato, s.data_liquidazione = "liquidato", 4000.0, OGGI
        db.session.commit()
    resp = client.post(f"/sinistri/{sid}/modifica", data={
        "policy_id": pid, "tipologia": "danni_terzi", "data_evento": evento, "importo_liquidato": ""})
    assert resp.status_code == 400
    with app.app_context():
        assert db.session.get(Claim, sid).importo_liquidato == 4000.0


def test_sinistro_riaperto_rigenera_le_notifiche(client, app):
    cid = _cliente(app)
    client.post("/sinistri/nuovo", data={"client_id": cid, "tipologia": "altro",
                                         "data_evento": (OGGI - timedelta(days=6)).isoformat()})
    client.get("/")
    with app.app_context():
        sid = Claim.query.one().id
        assert Notification.query.filter(Notification.dedup_key.like(f"sinistro:{sid}:%denuncia:scaduta")).count() == 1
    client.post(f"/sinistri/{sid}/stato", data={"stato": "respinto"})
    client.post(f"/sinistri/{sid}/stato", data={"stato": "aperto"})
    client.get("/")
    with app.app_context():
        n = Notification.query.filter(Notification.dedup_key.like(f"sinistro:{sid}:%denuncia:scaduta")).one()
        assert not n.letta


def test_numero_sinistro_non_riutilizzato(client, app):
    cid = _cliente(app)
    dati = {"client_id": cid, "tipologia": "altro", "data_evento": OGGI.isoformat()}
    client.post("/sinistri/nuovo", data=dati)
    with app.app_context():
        primo = Claim.query.one()
        numero, sid = primo.numero, primo.id
    client.post(f"/sinistri/{sid}/elimina")
    client.post("/sinistri/nuovo", data=dati)
    with app.app_context():
        assert Claim.query.one().numero != numero


def test_avvisi_copertura_alla_data_evento(client, app):
    cid = _cliente(app)
    decorrenza = OGGI - timedelta(days=10)
    pid = _polizza(app, cid, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12))
    resp = client.post("/sinistri/nuovo", data={
        "client_id": cid, "policy_id": pid, "tipologia": "altro",
        "data_evento": (decorrenza - timedelta(days=3)).isoformat()}, follow_redirects=True)
    assert "precedente alla decorrenza" in resp.get_data(as_text=True)


# ----------------------------------------------------------------------
# Opportunità, follow-up, paginazione, notifiche
# ----------------------------------------------------------------------
def test_opportunita_validazione_e_data_chiusura(client, app):
    cid = _cliente(app)
    resp = client.post(f"/opportunita/nuova/{cid}", data={"titolo": "Cyber", "provvigione_perc": "250",
                                                          "premio_stimato": "1.500,00"})
    assert resp.status_code == 400 and "1.500,00" in resp.get_data(as_text=True)
    client.post(f"/opportunita/nuova/{cid}", data={"titolo": "Cyber", "premio_stimato": "1.500,00",
                                                   "fase": "vinta", "priorita": "inventata"})
    with app.app_context():
        o = Opportunity.query.one()
        assert o.premio_stimato == 1500.0 and o.priorita == "media"
        chiusa, oid = o.chiusa_at, o.id
        assert chiusa is not None
    client.post(f"/opportunita/{oid}/modifica", data={"titolo": "Cyber risk", "fase": "vinta"})
    with app.app_context():
        o = db.session.get(Opportunity, oid)
        assert o.titolo == "Cyber risk" and o.chiusa_at == chiusa


def test_followup_riaperto_e_lista_mantiene_la_pagina(client, app):
    cid = _cliente(app)
    with app.app_context():
        fu = FollowUp(client_id=cid, tipo="chiamata", titolo="Richiamare", data_scadenza=OGGI - timedelta(days=2))
        db.session.add(fu)
        db.session.commit()
        fid = fu.id
    client.get("/")
    client.post(f"/follow-up/{fid}/completa", data={"da_lista": "1"})
    with app.app_context():
        assert Notification.query.filter(Notification.dedup_key.like(f"followup:{fid}:%")).count() >= 1
    resp = client.post(f"/follow-up/{fid}/riapri", data={"next": "/follow-up/?stato=completato&page=1"})
    assert resp.headers["Location"].endswith("/follow-up/?stato=completato&page=1")
    with app.app_context():
        assert Notification.query.filter(Notification.dedup_key.like(f"followup:{fid}:%")).count() == 0
    client.get("/")
    with app.app_context():
        assert Notification.query.filter(Notification.dedup_key.like(f"followup:{fid}:%")).count() == 1


def test_paginazione_oltre_l_ultima_pagina(client, app):
    with app.app_context():
        for i in range(3):
            db.session.add(Client(tipo="azienda", ragione_sociale=f"Cliente {i}"))
        db.session.commit()
    pagina = client.get("/clienti/?page=99").get_data(as_text=True)
    assert "Cliente 0" in pagina


def test_notifica_senza_punto_doppio(app):
    with app.app_context():
        aggiungi_notifica("test", "info", "Scade la polizza di Rossi S.r.l..", "/", "test:punto")
        db.session.commit()
        assert Notification.query.filter_by(dedup_key="test:punto").one().messaggio.endswith("S.r.l.")


def test_dashboard_mostra_solo_scadenze_future(client, app):
    with app.app_context():
        Settings.get().scadenza_automatica = False  # la polizza scaduta resta «attiva»
        db.session.commit()
    scaduta = OGGI - timedelta(days=400)
    _polizza(app, data_decorrenza=add_months(scaduta, -12), data_scadenza=scaduta, n=9)
    imminente = OGGI + timedelta(days=10)
    _polizza(app, data_decorrenza=add_months(imminente, -12), data_scadenza=imminente, n=10)
    with _Contesti(app) as contesti:
        client.get("/")
    ctx = dict(contesti)["dashboard.html"]
    numeri = [p.numero_polizza for p in ctx["prossime_scadenze"]]
    assert numeri == ["P-10"]
    assert ctx["stats"]["polizze_scadute"] >= 1


# ----------------------------------------------------------------------
# Moduli che conservano i dati dopo un errore
# ----------------------------------------------------------------------
def test_modifica_polizza_con_errore_conserva_i_dati(client, app):
    pid = _polizza(app)
    resp = client.post(f"/polizze/{pid}/modifica", data={
        "compagnia": "Allianz", "numero_polizza": "P-NUOVO", "premio_annuo": "abc", "stato": "attiva"})
    assert resp.status_code == 400
    pagina = resp.get_data(as_text=True)
    assert 'value="abc"' in pagina and 'value="P-NUOVO"' in pagina
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.compagnia == "Generali" and p.premio_annuo == 1200.0


def test_nuova_polizza_con_errore_riapre_la_scheda_cliente(client, app):
    cid = _cliente(app)
    resp = client.post(f"/polizze/nuova/{cid}", data={
        "compagnia": "Allianz", "numero_polizza": "AB-77", "ramo": "auto", "tacito_rinnovo": "on",
        "data_decorrenza": OGGI.isoformat(), "data_scadenza": add_months(OGGI, 12).isoformat()})
    assert resp.status_code == 400
    pagina = resp.get_data(as_text=True)
    assert "RC auto" in pagina and 'value="AB-77"' in pagina and 'data-tab-iniziale="polizze"' in pagina
    with app.app_context():
        assert Policy.query.count() == 0


def test_filtri_dei_template(app):
    with app.app_context():
        filtri = app.jinja_env.filters
        assert filtri["num_input"](1234.5) == "1234,50" and filtri["num_input"](None) == ""
        assert [filtri["giorni"](g) for g in (0, 1, -1, 5, -3)] == [
            "oggi", "domani", "da ieri", "tra 5 giorni", "da 3 giorni"]
        plurale = app.jinja_env.globals["plurale"]
        assert plurale(1, "titolo", "titoli") == "1 titolo" and plurale(3, "titolo", "titoli") == "3 titoli"


def test_csp_senza_script_inline_e_template_senza_gestori(client, app):
    import pathlib
    import re
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "script-src 'self';" in csp and "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    cartella = pathlib.Path(app.root_path) / "templates"
    for f in cartella.rglob("*.html"):
        testo = f.read_text()
        assert not re.search(r"\son[a-z]+\s*=\s*\"", testo), f"gestore inline in {f.name}"
        assert not re.search(r"<script(?![^>]*\bsrc=)", testo), f"script inline in {f.name}"


# ----------------------------------------------------------------------
# Verifica finale: emissione automatica, rinnovi, disdette, vita, migrazioni
# ----------------------------------------------------------------------
def test_storno_non_viene_riemesso_dall_automatismo(client, app):
    decorrenza = OGGI - timedelta(days=355)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 24))
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p, decorrenza, add_months(decorrenza, 12))
        db.session.commit()
    client.get("/")  # emissione automatica della seconda annualità (anticipo 30 gg)
    with app.app_context():
        seconda = [t for t in db.session.get(Policy, pid).titoli if t.data_effetto == add_months(decorrenza, 12)]
        assert len(seconda) == 1
        tid = seconda[0].id
    client.post(f"/titoli/{tid}/storna", data={"motivo": "sostituita"})
    client.get("/")
    client.get(f"/polizze/{pid}")
    with app.app_context():
        seconda = [t for t in db.session.get(Policy, pid).titoli if t.data_effetto == add_months(decorrenza, 12)]
        assert [t.stato for t in seconda] == ["stornato"]


def test_spostare_la_scadenza_non_duplica_il_premio(client, app):
    decorrenza = OGGI - timedelta(days=30)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 12))
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p)
        db.session.commit()
        nuova = p.data_scadenza + timedelta(days=1)
    resp = client.post(f"/polizze/{pid}/modifica", data={
        "compagnia": "Generali", "numero_polizza": "P-1", "ramo": "incendio", "stato": "attiva",
        "premio_annuo": "1200", "frazionamento": "annuale",
        "data_decorrenza": decorrenza.isoformat(), "data_scadenza": nuova.isoformat()},
        follow_redirects=True)
    assert "verifica che i titoli già emessi" in resp.get_data(as_text=True)
    client.get("/")
    with app.app_context():
        titoli = [t for t in db.session.get(Policy, pid).titoli if t.stato != "stornato"]
        assert sum(t.premio_lordo for t in titoli) == 1200.0


def test_rinnovo_di_13_mesi_rateo_senza_doppio_premio(client, app):
    pid = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p)
        db.session.commit()
        vecchia = p.data_scadenza
    nuova = add_months(vecchia, 13)
    client.post(f"/polizze/{pid}/rinnova", data={"nuova_scadenza": nuova.isoformat(), "genera_titoli": "on"})
    client.get("/")
    with app.app_context():
        nuovi = sorted((t for t in db.session.get(Policy, pid).titoli if t.data_effetto >= vecchia),
                       key=lambda t: t.data_effetto)
        # Rateo di un mese + annualità piena: nessuna sovrapposizione.
        assert [t.data_effetto for t in nuovi] == [vecchia, add_months(vecchia, 1)]
        assert nuovi[1].premio_lordo == 1200.0 and 90 < nuovi[0].premio_lordo < 110


def test_rinnovo_di_polizza_scaduta_da_anni_genera_tutte_le_annualita(client, app):
    with app.app_context():
        Settings.get().scadenza_automatica = False
        db.session.commit()
    vecchia = add_months(OGGI, -30)
    pid = _polizza(app, data_decorrenza=add_months(vecchia, -12), data_scadenza=vecchia)
    nuova = add_months(vecchia, 36)
    client.post(f"/polizze/{pid}/rinnova", data={
        "nuova_scadenza": nuova.isoformat(), "genera_titoli": "on", "pluriennale": "on"})
    with app.app_context():
        effetti = sorted(t.data_effetto for t in db.session.get(Policy, pid).titoli)
        assert effetti == [vecchia, add_months(vecchia, 12), add_months(vecchia, 24)]


def test_disdetta_poliennale_alla_scadenza_mantiene_le_annualita(app):
    decorrenza = OGGI - timedelta(days=350)
    pid = _polizza(app, data_decorrenza=decorrenza, data_scadenza=add_months(decorrenza, 36),
                   data_disdetta=OGGI - timedelta(days=1))
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p, decorrenza, add_months(decorrenza, 12))
        db.session.commit()
        assert emetti_quietanze(OGGI, Settings.get()) == 1
        db.session.commit()
        dati = calcola_previsione(24, oggi=OGGI)
        # Previsione: l'ultima annualità (prima della scadenza) sì, il rinnovo no.
        assert dati["totale_emessi"] == 1200.0 and dati["totale_stimati"] == 1200.0


def test_cessazione_futura_e_annullo_disdetta(client, app):
    pid = _polizza(app, frazionamento="semestrale")
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p)
        db.session.commit()
        scadenza = p.data_scadenza
        seconda = add_months(p.data_decorrenza, 6)
    cessazione = seconda - timedelta(days=1)
    client.post(f"/polizze/{pid}/disdetta", data={
        "data_disdetta": OGGI.isoformat(), "effetto": "immediato", "data_cessazione": cessazione.isoformat()})
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.data_scadenza == cessazione and p.scadenza_originale == scadenza
        assert [t.stato for t in p.titoli if t.data_effetto == seconda] == ["stornato"]
        assert scadi_polizze(cessazione + timedelta(days=1), Settings.get()) == 1
        db.session.commit()
        assert db.session.get(Policy, pid).stato == "disdetta"
    client.post(f"/polizze/{pid}/annulla-disdetta")
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert p.stato == "attiva" and p.data_scadenza == scadenza and p.data_disdetta is None
        assert [t.stato for t in p.titoli if t.data_effetto == seconda] == ["da_incassare"]


def test_rc_auto_mai_rinnovata_tacitamente(app):
    scadenza = OGGI - timedelta(days=2)
    pid = _polizza(app, ramo="auto", tacito_rinnovo=True,
                   data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza)
    with app.app_context():
        assert rinnova_taciti(OGGI, Settings.get()) == 0
        p = db.session.get(Policy, pid)
        assert not p.rinnovo_tacito and p.termine_disdetta is None


def test_vita_esclusa_dall_art_1901(app):
    pid = _polizza(app, ramo="vita")
    with app.app_context():
        p = db.session.get(Policy, pid)
        t = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza",
                  data_effetto=OGGI - timedelta(days=40), premio_lordo=500.0)
        db.session.add(t)
        db.session.commit()
        assert t.arretrato and not t.copertura_sospesa and t.data_risoluzione is None
        assert not t.sospende_alla_data(OGGI)


def test_copertura_sospesa_fino_al_giorno_del_pagamento(app):
    pid = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        effetto = OGGI - timedelta(days=60)
        t = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza", data_effetto=effetto,
                  premio_lordo=500.0, stato="incassato", data_incasso=OGGI - timedelta(days=10))
        db.session.add(t)
        db.session.commit()
        assert t.inizio_sospensione == effetto + timedelta(days=16)
        assert not t.sospende_alla_data(effetto + timedelta(days=15))
        assert t.sospende_alla_data(effetto + timedelta(days=16))
        assert t.sospende_alla_data(OGGI - timedelta(days=10))  # giorno del pagamento
        assert not t.sospende_alla_data(OGGI - timedelta(days=9))


def test_annualita_29_febbraio_piena():
    from gestionale.titoli import annualita_piena, premio_periodo
    assert annualita_piena(date(2027, 2, 28), date(2028, 2, 29))
    assert premio_periodo(1000.0, date(2027, 2, 28), date(2028, 2, 29)) == 1000.0


def test_migrazione_chiavi_titoli_e_sinistri(app):
    from gestionale import _migra_chiavi_notifiche
    pid = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        t = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza",
                  data_effetto=OGGI - timedelta(days=20), premio_lordo=500.0)
        s = Claim(client_id=p.client_id, numero="SIN-M-1", tipologia="altro", stato="aperto",
                  data_evento=OGGI - timedelta(days=10))
        db.session.add_all([t, s])
        db.session.flush()
        for chiave in (f"titolo:{t.id}:sospesa", f"sinistro:{s.id}:denuncia", f"sinistro:{s.id}:aperto:180"):
            db.session.add(Notification(tipo="x", livello="info", messaggio="m", dedup_key=chiave, letta=True))
        db.session.commit()
        _migra_chiavi_notifiche()
        chiavi = {n.dedup_key for n in Notification.query.all()}
        assert f"titolo:{t.id}:{t.data_effetto.isoformat()}:sospesa" in chiavi
        assert f"sinistro:{s.id}:{s.data_evento.isoformat()}:denuncia:scaduta" in chiavi
        assert f"sinistro:{s.id}:{s.data_evento.isoformat()}:aperto:180" in chiavi


def test_titolo_manuale_con_errore_conserva_i_dati(client, app):
    pid = _polizza(app)
    resp = client.post(f"/titoli/nuovo/{pid}", data={
        "tipo": "rata", "data_effetto": OGGI.isoformat(), "premio_lordo": "100",
        "provvigione": "150", "note": "regolazione lunga"})
    assert resp.status_code == 400
    pagina = resp.get_data(as_text=True)
    assert 'value="regolazione lunga"' in pagina and "collapse mb-3 show" in pagina


def test_preavviso_vuoto_torna_al_predefinito(client, app):
    pid = _polizza(app, tacito_rinnovo=True, preavviso_disdetta_giorni=90)
    with app.app_context():
        p = db.session.get(Policy, pid)
        dati = {"compagnia": "Generali", "numero_polizza": "P-1", "ramo": "incendio", "stato": "attiva",
                "premio_annuo": "1200", "frazionamento": "annuale", "tacito_rinnovo": "on",
                "preavviso_disdetta_giorni": "",
                "data_decorrenza": p.data_decorrenza.isoformat(), "data_scadenza": p.data_scadenza.isoformat()}
    client.post(f"/polizze/{pid}/modifica", data=dati)
    with app.app_context():
        assert db.session.get(Policy, pid).preavviso_disdetta == 30


def test_operatore_non_incassa_nei_mesi_chiusi(app):
    from conftest import add_user, login
    from gestionale.utils import inizio_mese
    pid = _polizza(app)
    with app.app_context():
        genera_titoli(db.session.get(Policy, pid))
        db.session.commit()
        tid = db.session.get(Policy, pid).titoli[0].id
    add_user(app, "operatore1", "password-op-1")
    operatore = app.test_client()
    login(operatore, "operatore1", "password-op-1")
    mese_scorso = inizio_mese(OGGI) - timedelta(days=1)
    operatore.post(f"/titoli/{tid}/incassa", data={"mezzo_pagamento": "pos", "data_incasso": mese_scorso.isoformat()})
    with app.app_context():
        assert db.session.get(Title, tid).stato == "da_incassare"
    operatore.post(f"/titoli/{tid}/incassa", data={"mezzo_pagamento": "pos", "data_incasso": OGGI.isoformat()})
    with app.app_context():
        assert db.session.get(Title, tid).stato == "incassato"


def test_modifica_titolo_con_data_gia_usata_non_da_500(client, app):
    pid = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        primo = genera_titoli(p)[0]
        db.session.flush()
        altro = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza", numero_rata=1,
                      data_effetto=add_months(primo.data_effetto, 12), premio_lordo=1200.0)
        db.session.add(altro)
        db.session.commit()
        effetto_primo, altro_id = primo.data_effetto, altro.id
    resp = client.post(f"/titoli/{altro_id}/modifica", data={
        "tipo": "quietanza", "data_effetto": effetto_primo.isoformat(), "premio_lordo": "1200"})
    assert resp.status_code == 400 and "ha già una rata con questa data" in resp.get_data(as_text=True)


# ----------------------------------------------------------------------
# Verifica finale (secondo giro): accessi, clienti, sinistri, dashboard
# ----------------------------------------------------------------------
def test_nomi_utente_accentati(client, app):
    from conftest import add_user
    from gestionale.cli import reimposta_password
    add_user(app, "Èrica", "password-erica-1")
    nuovo = app.test_client()
    resp = nuovo.post("/accesso", data={"username": "èrica", "password": "password-erica-1"})
    assert resp.status_code == 302
    # Duplicato che differisce solo per maiuscola accentata: rifiutato.
    resp = client.post("/utenti/nuovo", data={"username": "ÈRICA", "ruolo": "operatore",
                                              "password": "password-x-1234", "conferma": "password-x-1234"})
    assert resp.status_code == 400
    with app.app_context():
        assert "«Èrica»" in reimposta_password("èrica", "nuova-password-1")


def test_nome_utente_sistema_riservato(client, app):
    resp = client.post("/utenti/nuovo", data={"username": "Sistema", "ruolo": "operatore",
                                              "password": "password-x-1234", "conferma": "password-x-1234"})
    assert resp.status_code == 400 and "riservato" in resp.get_data(as_text=True)


def test_ripristino_limite_alto_solo_per_amministratori(tmp_path):
    from conftest import add_user, make_app
    app = make_app(tmp_path, CSRF_ENABLED=True)  # come in produzione: il token CSRF si legge dal form
    add_user(app, "operatore1", "password-op-1")
    operatore = app.test_client()
    with operatore.session_transaction() as sessione:
        sessione["_csrf"] = "tok"
    operatore.post("/accesso", data={"username": "operatore1", "password": "password-op-1", "csrf_token": "tok"})
    with operatore.session_transaction() as sessione:
        sessione["_csrf"] = "tok"
    corpo = b"x" * (25 * 1024 * 1024)
    resp = operatore.post("/impostazioni/backup/ripristina",
                          data={"csrf_token": "tok", "archivio": (io.BytesIO(corpo), "b.zip")},
                          content_type="multipart/form-data")
    # Oltre i 20 MB ordinari: rifiutato subito, senza leggere il corpo fino a 512 MB.
    assert resp.status_code == 413
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_parametro_endpoint_non_rompe_le_liste(client, app):
    for url in ("/polizze/?endpoint=1", "/sinistri/?endpoint=1", "/titoli/?endpoint=1", "/registro/?endpoint=1",
                "/clienti/?endpoint=x&_external=1"):
        assert client.get(url).status_code == 200, url


def test_dipendente_mantiene_la_mansione(client, app):
    pagina = client.get("/clienti/nuovo").get_data(as_text=True)
    assert re.search(r'data-tipi="dipendente"[^>]*>\s*<label class="form-label" for="cf-mansione">Mansione', pagina)
    client.post("/clienti/nuovo", data={"tipo": "dipendente", "ragione_sociale": "Marco Verdi",
                                        "mansione": "Capo officina", "datore_lavoro": "Acme S.p.A."})
    with app.app_context():
        c = Client.query.filter_by(ragione_sociale="Marco Verdi").one()
        assert (c.professione, c.datore_lavoro) == ("Capo officina", "Acme S.p.A.")


def test_questionario_in_scadenza_non_mancante(client, app):
    cid = _cliente(app)
    with app.app_context():
        c = db.session.get(Client, cid)
        c.data_adeguatezza = add_months(OGGI, -12) + timedelta(days=10)
        db.session.commit()
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    sezione = pagina.split("Questionario di adeguatezza")[1][:300]
    assert "mancante" not in sezione and "scade il" in sezione


def test_togliere_la_data_di_denuncia_riattiva_il_promemoria(client, app):
    cid = _cliente(app)
    evento = (OGGI - timedelta(days=10)).isoformat()
    client.post("/sinistri/nuovo", data={"client_id": cid, "tipologia": "altro", "data_evento": evento})
    client.get("/")
    with app.app_context():
        sid = Claim.query.one().id
    client.post(f"/sinistri/{sid}/modifica", data={"tipologia": "altro", "data_evento": evento,
                                                   "data_denuncia": OGGI.isoformat()})
    client.post(f"/sinistri/{sid}/modifica", data={"tipologia": "altro", "data_evento": evento})
    client.get("/")
    with app.app_context():
        n = Notification.query.filter(Notification.dedup_key.like(f"sinistro:{sid}:%denuncia:scaduta")).one()
        assert not n.letta


def test_dashboard_arretrati_senza_rimborsi(client, app):
    pid = _polizza(app)
    with app.app_context():
        p = db.session.get(Policy, pid)
        db.session.add_all([
            Title(policy_id=pid, client_id=p.client_id, tipo="quietanza", data_effetto=OGGI - timedelta(days=5),
                  premio_lordo=1000.0),
            Title(policy_id=pid, client_id=p.client_id, tipo="appendice", data_effetto=OGGI - timedelta(days=5),
                  premio_lordo=-200.0),
        ])
        db.session.commit()
    with _Contesti(app) as contesti:
        client.get("/")
    stats = dict(contesti)["dashboard.html"]["stats"]
    assert stats["titoli_arretrati"] == 1 and stats["importo_arretrati"] == 1000.0


def test_eliminare_il_cliente_toglie_le_notifiche_degli_automatismi(client, app):
    cid = _cliente(app)
    pid = _polizza(app, cid)
    with app.app_context():
        db.session.add(Notification(tipo="automatismo", livello="info", messaggio="m", link=f"/polizze/{pid}",
                                    dedup_key=f"automatismo:tacito:{pid}:2026-01-01"))
        db.session.commit()
    client.post(f"/clienti/{cid}/elimina")
    with app.app_context():
        assert Notification.query.filter(Notification.dedup_key.like("automatismo:%")).count() == 0


def test_agenda_decorrenza_di_oggi(app):
    _polizza(app, data_decorrenza=OGGI, data_scadenza=add_months(OGGI, 12))
    with app.test_request_context():
        assert any(e.tipo == "decorrenza" and e.data == OGGI for e in eventi_agenda(OGGI, OGGI + timedelta(days=5)))


def test_rapporto_sp_con_base_negativa(client, app):
    pid = _polizza(app, ramo="furto")
    with app.app_context():
        p = db.session.get(Policy, pid)
        db.session.add(Title(policy_id=pid, client_id=p.client_id, tipo="appendice",
                             data_effetto=OGGI - timedelta(days=5), premio_lordo=-50.0))
        db.session.add(Claim(client_id=p.client_id, policy_id=pid, numero="SIN-SP-1", tipologia="furto",
                             stato="aperto", data_evento=OGGI - timedelta(days=3), importo_riservato=100.0))
        db.session.commit()
    with _Contesti(app) as contesti:
        client.get("/statistiche")
    ctx = dict(contesti)["analytics.html"]
    furto = next(r for r in ctx["rami"] if r["ramo"] == "furto")
    assert furto["rapporto_sp"] is None and ctx["rapporto_sp"] is None


def test_appendice_non_attiva_l_emissione_automatica(client, app):
    pid = _polizza(app, data_decorrenza=OGGI - timedelta(days=120),
                   data_scadenza=add_months(OGGI - timedelta(days=120), 12))
    client.post(f"/titoli/nuovo/{pid}", data={"tipo": "appendice", "data_effetto": OGGI.isoformat(),
                                              "premio_lordo": "350,00"})
    client.get("/")
    with app.app_context():
        p = db.session.get(Policy, pid)
        assert [t.tipo for t in p.titoli] == ["appendice"] and not p.copertura_sospesa


def test_risoluzione_gia_avvenuta_ha_un_messaggio_proprio(client, app):
    pid = _polizza(app, data_decorrenza=OGGI - timedelta(days=400), data_scadenza=OGGI + timedelta(days=330))
    with app.app_context():
        p = db.session.get(Policy, pid)
        t = Title(policy_id=pid, client_id=p.client_id, tipo="quietanza",
                  data_effetto=OGGI - timedelta(days=300), premio_lordo=600.0)
        db.session.add(t)
        db.session.commit()
        tid = t.id
    client.get("/")
    with app.app_context():
        chiavi = {n.dedup_key for n in Notification.query.filter(Notification.dedup_key.like(f"titolo:{tid}:%"))}
        assert any(k.endswith(":risolta") for k in chiavi)
        assert not any(k.endswith(":risoluzione") for k in chiavi)


def test_scadenza_automatica_chiude_il_follow_up_di_rinnovo(app):
    scadenza = OGGI - timedelta(days=40)
    pid = _polizza(app, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza)
    with app.app_context():
        p = db.session.get(Policy, pid)
        db.session.add(FollowUp(client_id=p.client_id, policy_id=pid, tipo="rinnovo", titolo="Rinnovo",
                                data_scadenza=scadenza - timedelta(days=15), auto_generato=True))
        db.session.commit()
        assert scadi_polizze(OGGI, Settings.get()) == 1
        db.session.commit()
        assert FollowUp.query.filter_by(policy_id=pid, stato="aperto").count() == 0


def test_quietanza_anticipata_per_tacito_rinnovo_certo(app):
    scadenza = OGGI + timedelta(days=10)
    pid = _polizza(app, data_decorrenza=add_months(scadenza, -12), data_scadenza=scadenza,
                   tacito_rinnovo=True, preavviso_disdetta_giorni=30)
    with app.app_context():
        p = db.session.get(Policy, pid)
        genera_titoli(p, add_months(scadenza, -12), scadenza)
        db.session.commit()
        assert emetti_quietanze(OGGI, Settings.get()) == 1
        db.session.commit()
        assert any(t.data_effetto == scadenza and t.tipo == "quietanza" for t in db.session.get(Policy, pid).titoli)
        # Al rinnovo tacito la quietanza non viene duplicata.
        assert rinnova_taciti(scadenza, Settings.get()) == 1
        db.session.commit()
        assert sum(1 for t in db.session.get(Policy, pid).titoli if t.data_effetto == scadenza) == 1
