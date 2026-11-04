"""Google Calendar collegato direttamente: consenso OAuth, calendario «Deal Combined»
ed eventi creati, aggiornati e tolti. Google è simulato: niente rete nei test."""
import urllib.parse
from datetime import date, datetime, timedelta

import pytest

from gestionale import google_calendar as gc
from gestionale.models import CalendarioEvento, Client, FollowUp, Nota, Policy, Settings, Title, db
from gestionale.titoli import add_months

OGGI = date.today()


class GoogleFinto:
    """Risponde come le API di Google per token, calendari ed eventi."""

    def __init__(self):
        self.chiamate = []
        self.eventi = {}
        self.calendari = set()
        self.token_valido = True

    def __call__(self, metodo, url, dati=None, token=None, modulo=None):
        self.chiamate.append((metodo, url, dati, modulo))
        if url == gc.TOKEN_URL:
            if modulo["grant_type"] == "authorization_code":
                return 200, {"access_token": "a1", "refresh_token": "r1"}
            if not self.token_valido:
                return 400, {"error": "invalid_grant"}
            return 200, {"access_token": "a2"}
        if url == gc.REVOKE_URL:
            return 200, {}
        percorso = urllib.parse.unquote(url[len(gc.API):])
        if percorso == "/calendars" and metodo == "POST":
            self.calendari.add("cal1")
            return 200, {"id": "cal1"}
        if percorso.startswith("/calendars/") and "/events" not in percorso:
            return (200, {"id": "cal1"}) if percorso.split("/")[2] in self.calendari else (404, {})
        parti = percorso.split("/")  # ['', 'calendars', cal, 'events', (id)]
        if metodo == "POST":
            if dati["id"] in self.eventi:
                return 409, {"error": {"message": "duplicate"}}
            self.eventi[dati["id"]] = dati
            return 200, dati
        if metodo == "PUT":
            self.eventi[parti[4]] = dati
            return 200, dati
        if metodo == "DELETE":
            return (204, {}) if self.eventi.pop(parti[4], None) else (410, {})
        return 404, {}


@pytest.fixture
def google(monkeypatch):
    finto = GoogleFinto()
    monkeypatch.setattr(gc, "_http", finto)
    return finto


def _collega(app, google):
    with app.app_context():
        s = Settings.get()
        s.gcal_client_id, s.gcal_client_secret = "123-abc.apps.googleusercontent.com", "GOCSPX-x"
        db.session.commit()
        url = gc.url_autorizzazione(s, "http://127.0.0.1:5000/impostazioni/google/calendar/ritorno")
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        gc.completa_autorizzazione(s, state, "codice")


def _dati(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Officina Neri S.r.l.")
        db.session.add(c)
        db.session.flush()
        decorrenza = add_months(OGGI, -6) + timedelta(days=5)
        p = Policy(client_id=c.id, compagnia="Generali", numero_polizza="SEM-1", ramo="incendio",
                   premio_annuo=1200.0, frazionamento="semestrale", data_decorrenza=decorrenza,
                   data_scadenza=add_months(decorrenza, 12), stato="attiva")
        f = FollowUp(client_id=c.id, titolo="Chiamare per il rinnovo", data_scadenza=OGGI + timedelta(days=2))
        n = Nota(titolo="Appuntamento in officina", client_id=c.id,
                 promemoria_il=datetime.combine(OGGI + timedelta(days=1), datetime.min.time()).replace(hour=15))
        db.session.add_all([p, f, n])
        db.session.commit()
        return p.id, f.id


def test_consenso_solo_calendari_creati_dal_programma_e_pkce(app, google):
    with app.app_context():
        s = Settings.get()
        with pytest.raises(gc.CalendarError):
            gc.url_autorizzazione(s, "http://127.0.0.1/x")  # credenziali mancanti
        s.gcal_client_id, s.gcal_client_secret = "123-abc.apps.googleusercontent.com", "GOCSPX-x"
        url = gc.url_autorizzazione(s, "http://127.0.0.1:5000/impostazioni/google/calendar/ritorno")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        assert q["scope"] == [gc.SCOPE] and q["code_challenge_method"] == ["S256"] and q["access_type"] == ["offline"]
        with pytest.raises(gc.CalendarError):
            gc.completa_autorizzazione(s, "state-inventato", "codice")
        gc.completa_autorizzazione(s, q["state"][0], "codice")
        assert s.gcal_refresh_token == "r1" and gc.collegato(s)
        scambio = [c for c in google.chiamate if c[3] and c[3].get("grant_type") == "authorization_code"][0]
        assert scambio[3]["code_verifier"]  # PKCE
        with pytest.raises(gc.CalendarError):
            gc.completa_autorizzazione(s, q["state"][0], "codice")  # lo stesso «state» vale una volta sola


def test_sincronizza_crea_aggiorna_e_toglie(app, google):
    pid, fid = _dati(app)
    _collega(app, google)
    with app.app_context():
        esito = gc.sincronizza()
        titoli = sorted(e["summary"] for e in google.eventi.values())
        assert esito["creati"] == len(google.eventi) == CalendarioEvento.query.count()
        assert any(t.startswith("Rata 2/2 da far pagare") for t in titoli)
        assert any(t.startswith("Scadenza polizza SEM-1") for t in titoli)
        assert any("Chiamare per il rinnovo" in t for t in titoli)
        nota = next(e for e in google.eventi.values() if e["summary"].startswith("Appuntamento"))
        assert nota["start"]["dateTime"].endswith("15:00:00") and nota["start"]["timeZone"] == "Europe/Rome"
        # Nessun cambiamento: nessuna scrittura.
        prima = len(google.chiamate)
        assert gc.sincronizza() == {"creati": 0, "aggiornati": 0, "eliminati": 0}
        assert [c[0] for c in google.chiamate[prima:] if "/events" in c[1]] == []
        # Follow-up fatto e rata emessa e incassata: tolti dal calendario.
        db.session.get(FollowUp, fid).stato = "completato"
        p = db.session.get(Policy, pid)
        rata = gc.eventi_desiderati()  # data della rata prevista
        data_rata = date.fromisoformat(next(k for k in rata if k.startswith("rata:")).split(":")[2])
        db.session.add(Title(policy_id=pid, client_id=p.client_id, data_effetto=data_rata, numero_rata=2, rate_totali=2,
                             data_fine_copertura=p.data_scadenza, premio_lordo=600.0, stato="incassato"))
        db.session.commit()
        esito = gc.sincronizza()
        assert esito["eliminati"] == 2
        assert not any("Chiamare" in e["summary"] or e["summary"].startswith("Rata") for e in google.eventi.values())


def test_due_pc_nessun_doppione_e_calendario_ricreato(app, google):
    _dati(app)
    _collega(app, google)
    with app.app_context():
        gc.sincronizza()
        n = len(google.eventi)
        # L'altro PC ha perso il registro degli eventi ma scrive gli stessi identificativi.
        CalendarioEvento.query.delete()
        db.session.commit()
        gc.sincronizza()
        assert len(google.eventi) == n  # 409 → aggiornamento, niente doppioni
        # Calendario eliminato a mano su Google: viene ricreato.
        google.calendari.clear()
        google.eventi.clear()
        gc.sincronizza()
        assert len(google.eventi) == n


def test_accesso_revocato_messaggio_chiaro(app, google):
    _dati(app)
    _collega(app, google)
    google.token_valido = False
    with app.app_context():
        with pytest.raises(gc.CalendarError, match="ricollega"):
            gc.sincronizza()
        assert "ricollega" in Settings.get().gcal_errore


def test_promemoria_alle_9_e_al_massimo_4_settimane():
    assert gc.minuti_promemoria([60, 30, 7]) == [7 * 1440 - 540, gc.MAX_MINUTI_PROMEMORIA]
    assert gc.minuti_promemoria([0]) == []


def test_ritorno_da_google_senza_sessione(app, google, client):
    pid, _ = _dati(app)
    with app.app_context():
        s = Settings.get()
        s.gcal_client_id, s.gcal_client_secret = "123-abc.apps.googleusercontent.com", "GOCSPX-x"
        db.session.commit()
        url = gc.url_autorizzazione(s, "http://localhost/impostazioni/google/calendar/ritorno")
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
    browser = app.test_client()  # il browser esterno non ha la sessione del programma
    pagina = browser.get(f"/impostazioni/google/calendar/ritorno?state={state}&code=c").get_data(as_text=True)
    assert "Google Calendar collegato" in pagina
    pagina = browser.get("/impostazioni/google/calendar/ritorno?state=falso&code=c").get_data(as_text=True)
    assert "non riuscito" in pagina
    # Le altre pagine delle impostazioni restano riservate.
    assert browser.get("/impostazioni/google").status_code == 302


def test_pagina_google_e_credenziali(client, app, google):
    pagina = client.get("/impostazioni/google").get_data(as_text=True)
    assert "Google Calendar collegato" in pagina and "App desktop" in pagina
    r = client.post("/impostazioni/google/calendar", data={"azione": "credenziali", "client_id": "sbagliato"},
                    follow_redirects=True)
    assert "non sembra giusto" in r.get_data(as_text=True)
    client.post("/impostazioni/google/calendar", data={"azione": "credenziali",
                                                        "client_id": "123-abc.apps.googleusercontent.com",
                                                        "client_secret": "GOCSPX-x"})
    r = client.post("/impostazioni/google/calendar", data={"azione": "collega"})
    assert r.status_code == 302 and r.headers["Location"].startswith(gc.AUTH_URL)
