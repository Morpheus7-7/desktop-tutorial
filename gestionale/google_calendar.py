"""Collegamento diretto a Google Calendar.

Il programma scrive da solo, in un calendario «Deal Combined» del tuo account
Google, le cose da non perdere:

- scadenze delle polizze (con l'ultimo giorno per la disdetta, se c'è il
  tacito rinnovo), con i promemoria di Calendar ai giorni di preavviso scelti;
- rate da far pagare: quietanze emesse non incassate e rate del frazionamento
  (semestrali, trimestrali, mensili…) non ancora emesse;
- follow-up aperti;
- promemoria delle note, all'ora indicata.

A ogni sincronizzazione gli eventi vengono creati, aggiornati se qualcosa è
cambiato (data, importo, cliente) e tolti quando non servono più (rata
incassata, follow-up fatto, polizza disdetta). Ogni evento ha un
identificativo fisso ricavato dalla sua chiave, così due PC che usano lo
stesso archivio non creano doppioni.

Accesso: OAuth 2.0 per app desktop (ritorno su 127.0.0.1, con PKCE) e il solo
permesso ``calendar.app.created``, che consente di gestire **soltanto i
calendari creati dal programma**: gli altri calendari dell'utente restano
invisibili a Deal Combined. Nessuna libreria esterna: bastano urllib e json.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from .models import CalendarioEvento, FollowUp, Nota, Policy, Settings, Title, db, now

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
NOME_CALENDARIO = "Deal Combined"
FUSO = "Europe/Rome"
# Orizzonte degli eventi: dal passato recente (cose in ritardo) a un anno avanti.
GIORNI_PASSATO = 60
GIORNI_FUTURO = 365
# Google accetta promemoria fino a 4 settimane prima dell'evento.
MAX_MINUTI_PROMEMORIA = 40320
# Una sola sincronizzazione alla volta (pulsante «Aggiorna adesso» e scheduler).
_IN_CORSO = threading.Lock()
# Richieste in sospeso del collegamento (state -> dati), solo in memoria.
_ATTESE: dict[str, dict] = {}
DURATA_ATTESA = 15 * 60


class CalendarError(Exception):
    """Errore comprensibile per l'utente."""


# ----------------------------------------------------------------------
# HTTP (sostituibile nei test)
# ----------------------------------------------------------------------
def _http(metodo: str, url: str, dati: dict | None = None, token: str | None = None,
          modulo: dict | None = None) -> tuple[int, dict]:
    intestazioni = {"Accept": "application/json"}
    corpo = None
    if modulo is not None:
        corpo = urllib.parse.urlencode(modulo).encode()
        intestazioni["Content-Type"] = "application/x-www-form-urlencoded"
    elif dati is not None:
        corpo = json.dumps(dati).encode()
        intestazioni["Content-Type"] = "application/json"
    if token:
        intestazioni["Authorization"] = f"Bearer {token}"
    richiesta = urllib.request.Request(url, data=corpo, method=metodo, headers=intestazioni)
    try:
        with urllib.request.urlopen(richiesta, timeout=20) as risposta:  # noqa: S310 - solo Google
            testo = risposta.read().decode() or "{}"
            return risposta.status, json.loads(testo)
    except urllib.error.HTTPError as exc:
        try:
            dettaglio = json.loads(exc.read().decode() or "{}")
        except ValueError:
            dettaglio = {}
        return exc.code, dettaglio
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CalendarError(f"Google non raggiungibile ({getattr(exc, 'reason', exc)}): controlla la connessione.") from exc


# ----------------------------------------------------------------------
# Collegamento (OAuth per app desktop)
# ----------------------------------------------------------------------
def configurato(s: Settings) -> bool:
    return bool(s.gcal_client_id and s.gcal_client_secret)


def collegato(s: Settings) -> bool:
    return configurato(s) and bool(s.gcal_refresh_token)


def url_autorizzazione(s: Settings, redirect_uri: str) -> str:
    """Pagina di Google in cui l'utente acconsente; il ritorno arriva a redirect_uri."""
    if not configurato(s):
        raise CalendarError("Inserisci prima ID client e segreto client di Google.")
    for chiave in [k for k, v in _ATTESE.items() if v["creata"] < time.time() - DURATA_ATTESA]:
        _ATTESE.pop(chiave, None)
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    sfida = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _ATTESE[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "creata": time.time()}
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": s.gcal_client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": sfida, "code_challenge_method": "S256",
    })


def completa_autorizzazione(s: Settings, state: str | None, codice: str | None) -> None:
    """Scambia il codice di Google con il token di accesso permanente (refresh token)."""
    attesa = _ATTESE.pop(state or "", None)
    if attesa is None or attesa["creata"] < time.time() - DURATA_ATTESA:
        raise CalendarError("Richiesta di collegamento scaduta o non valida: riprova da Impostazioni → Google.")
    if not codice:
        raise CalendarError("Google non ha concesso l'accesso al calendario.")
    stato, risposta = _http("POST", TOKEN_URL, modulo={
        "code": codice, "client_id": s.gcal_client_id, "client_secret": s.gcal_client_secret,
        "redirect_uri": attesa["redirect_uri"], "grant_type": "authorization_code",
        "code_verifier": attesa["verifier"],
    })
    if stato != 200 or not risposta.get("refresh_token"):
        raise CalendarError(f"Collegamento non riuscito: {risposta.get('error_description') or risposta.get('error') or stato}.")
    s.gcal_refresh_token = risposta["refresh_token"]
    s.gcal_errore = None
    db.session.commit()


def scollega(s: Settings) -> None:
    """Revoca il permesso su Google (se raggiungibile) e dimentica il token.
    Gli eventi già scritti restano nel calendario «Deal Combined»."""
    if s.gcal_refresh_token:
        try:
            _http("POST", REVOKE_URL, modulo={"token": s.gcal_refresh_token})
        except CalendarError:
            pass
    s.gcal_refresh_token = None
    s.gcal_calendar_id = None
    s.gcal_errore = None
    CalendarioEvento.query.delete()
    db.session.commit()


def _token_accesso(s: Settings) -> str:
    stato, risposta = _http("POST", TOKEN_URL, modulo={
        "client_id": s.gcal_client_id, "client_secret": s.gcal_client_secret,
        "refresh_token": s.gcal_refresh_token, "grant_type": "refresh_token",
    })
    if stato != 200 or not risposta.get("access_token"):
        if risposta.get("error") == "invalid_grant":
            raise CalendarError("Google ha revocato o fatto scadere l'accesso: ricollega il calendario da "
                                "Impostazioni → Google (se l'app Google è «in prova», pubblicala: vedi la guida).")
        raise CalendarError(f"Accesso a Google non riuscito: {risposta.get('error_description') or risposta.get('error') or stato}.")
    return risposta["access_token"]


# ----------------------------------------------------------------------
# Eventi desiderati
# ----------------------------------------------------------------------
def id_evento(chiave: str) -> str:
    """Identificativo Google fisso per la chiave (caratteri 0-9 a-f, ammessi da Calendar)."""
    return "dc" + hashlib.sha1(chiave.encode()).hexdigest()


def minuti_promemoria(giorni: list[int] | None) -> list[int]:
    """Promemoria di un evento di tutto il giorno alle 9 di N giorni prima.
    Calendar li misura dalla mezzanotte dell'evento e arriva al massimo a 4
    settimane: un preavviso più lungo diventa quello di 4 settimane."""
    minuti = {min(g * 1440 - 9 * 60, MAX_MINUTI_PROMEMORIA) for g in (giorni or []) if g >= 1}
    return sorted(minuti)[:5]


def _giornata(titolo: str, giorno: date, descrizione: str, promemoria_giorni: list[int] | None = None) -> dict:
    override = [{"method": "popup", "minutes": m} for m in minuti_promemoria(promemoria_giorni)]
    return {
        "summary": titolo[:250],
        "description": descrizione,
        "start": {"date": giorno.isoformat()},
        "end": {"date": (giorno + timedelta(days=1)).isoformat()},
        "transparency": "transparent",
        "reminders": {"useDefault": False, "overrides": override},
    }


def _orario(titolo: str, inizio: datetime, descrizione: str, minuti: int = 30) -> dict:
    return {
        "summary": titolo[:250],
        "description": descrizione,
        "start": {"dateTime": inizio.replace(microsecond=0).isoformat(), "timeZone": FUSO},
        "end": {"dateTime": (inizio + timedelta(minutes=minuti)).replace(microsecond=0).isoformat(), "timeZone": FUSO},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
    }


def _euro(valore) -> str:
    from .utils import formatta_euro

    return formatta_euro(valore)


def eventi_desiderati(oggi: date | None = None, base_url: str = "") -> dict[str, dict]:
    """Chiave -> evento Google per tutto ciò che va in calendario adesso."""
    from .titoli import rate_previste_portafoglio

    oggi = oggi or date.today()
    dal, al = oggi - timedelta(days=GIORNI_PASSATO), oggi + timedelta(days=GIORNI_FUTURO)
    s = Settings.get()
    preavvisi = s.giorni_preavviso_scadenze
    preavviso_rate = [s.giorni_preavviso_rate]
    eventi: dict[str, dict] = {}

    def link(percorso: str) -> str:
        # Niente indirizzo del programma (127.0.0.1:porta): dal telefono non si
        # apre e, cambiando porta, riscriverebbe tutti gli eventi.
        return "\n\nScritto da Deal Combined."

    for p in Policy.query.filter(Policy.stato.in_(("attiva", "in_rinnovo")), Policy.data_scadenza.isnot(None),
                                 Policy.data_scadenza >= dal, Policy.data_scadenza <= al):
        cliente = p.cliente.ragione_sociale
        dettagli = (f"Cliente: {cliente}\nCompagnia: {p.compagnia}\nRamo: {p.ramo_label}\n"
                    f"Premio annuo: {_euro(p.premio_annuo)}" + link(f"/polizze/{p.id}"))
        eventi[f"polizza:{p.id}:{p.data_scadenza.isoformat()}"] = _giornata(
            f"Scadenza polizza {p.numero_polizza} · {cliente}", p.data_scadenza, dettagli, preavvisi)
        termine = p.termine_disdetta if p.rinnovo_tacito and not p.disdetta_inviata else None
        if termine and dal <= termine <= al:
            eventi[f"disdetta:{p.id}:{termine.isoformat()}"] = _giornata(
                f"Ultimo giorno per la disdetta · {p.numero_polizza} · {cliente}", termine,
                f"Tacito rinnovo: entro oggi la disdetta, altrimenti la polizza si rinnova.\n{dettagli}", [7])

    for t in Title.query.filter(Title.stato == "da_incassare", Title.premio_lordo > 0,
                                Title.data_effetto >= dal, Title.data_effetto <= al):
        p = t.polizza
        if p is None or not p.attiva:
            continue
        rata = f"Rata {t.rata_label}" if t.rata_label else "Quietanza"
        eventi[f"titolo:{t.id}:{t.data_effetto.isoformat()}"] = _giornata(
            f"{rata} da incassare · {_euro(t.premio_lordo)} · {p.cliente.ragione_sociale}", t.data_effetto,
            f"Polizza {p.numero_polizza} ({p.compagnia}, {p.ramo_label})" + link(f"/polizze/{p.id}"), preavviso_rate)

    for r in rate_previste_portafoglio(max(dal, oggi - timedelta(days=GIORNI_PASSATO)), al):
        p = r["polizza"]
        eventi[f"rata:{p.id}:{r['data'].isoformat()}"] = _giornata(
            f"Rata {r['numero']}/{r['totali']} da far pagare · {_euro(r['premio'])} · {p.cliente.ragione_sociale}",
            r["data"], f"Polizza {p.numero_polizza} ({p.compagnia}, {p.ramo_label})" + link(f"/polizze/{p.id}"),
            preavviso_rate)

    for f in FollowUp.query.filter(FollowUp.stato == "aperto", FollowUp.data_scadenza >= dal,
                                   FollowUp.data_scadenza <= al):
        eventi[f"followup:{f.id}:{f.data_scadenza.isoformat()}"] = _giornata(
            f"{f.tipo_label}: {f.titolo} · {f.cliente.ragione_sociale}", f.data_scadenza,
            (f.descrizione or "") + link(f"/clienti/{f.client_id}"), [1] if f.priorita == "alta" else [])

    inizio = datetime.combine(dal, datetime.min.time())
    # Anche i promemoria già arrivati restano in calendario come traccia del lavoro.
    for n in Nota.query.filter(Nota.promemoria_il.isnot(None), Nota.promemoria_il >= inizio):
        cliente = f" · {n.cliente.ragione_sociale}" if n.cliente else ""
        eventi[f"nota:{n.id}:{n.promemoria_il.isoformat()}"] = _orario(
            f"{n.titolo}{cliente}", n.promemoria_il, (n.testo or "") + link("/note/"))
    return eventi


def _impronta(evento: dict) -> str:
    return hashlib.sha1(json.dumps(evento, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ----------------------------------------------------------------------
# Sincronizzazione
# ----------------------------------------------------------------------
def _assicura_calendario(s: Settings, token: str) -> str:
    if s.gcal_calendar_id:
        stato, _ = _http("GET", f"{API}/calendars/{urllib.parse.quote(s.gcal_calendar_id)}", token=token)
        if stato == 200:
            return s.gcal_calendar_id
        if stato not in (404, 410):
            raise CalendarError(f"Calendario non raggiungibile (errore {stato}).")
        CalendarioEvento.query.delete()  # il calendario è stato eliminato: si ricomincia
    stato, risposta = _http("POST", f"{API}/calendars", {
        "summary": NOME_CALENDARIO, "timeZone": FUSO,
        "description": "Scadenze, rate, follow-up e promemoria scritti da Deal Combined.",
    }, token=token)
    if stato not in (200, 201) or not risposta.get("id"):
        raise CalendarError(f"Non riesco a creare il calendario «{NOME_CALENDARIO}» (errore {stato}).")
    s.gcal_calendar_id = risposta["id"]
    db.session.commit()
    return s.gcal_calendar_id


def sincronizza(base_url: str = "", oggi: date | None = None) -> dict:
    """Allinea il calendario «Deal Combined» ai dati del programma.
    Restituisce quanti eventi ha creato, aggiornato ed eliminato."""
    if not _IN_CORSO.acquire(timeout=120):
        raise CalendarError("Un aggiornamento del calendario è già in corso: riprova tra poco.")
    try:
        return _sincronizza(base_url, oggi)
    finally:
        _IN_CORSO.release()


def _sincronizza(base_url: str, oggi: date | None) -> dict:
    s = Settings.get()
    if not collegato(s):
        raise CalendarError("Google Calendar non è collegato.")
    try:
        token = _token_accesso(s)
        cal = urllib.parse.quote(_assicura_calendario(s, token))
        desiderati = eventi_desiderati(oggi, base_url)
        presenti = {e.chiave: e for e in CalendarioEvento.query.all()}
        conteggio = {"creati": 0, "aggiornati": 0, "eliminati": 0}

        for chiave, evento in desiderati.items():
            impronta = _impronta(evento)
            riga = presenti.get(chiave)
            if riga is not None and riga.impronta == impronta:
                continue
            eid = id_evento(chiave)
            corpo = {**evento, "id": eid, "status": "confirmed"}
            if riga is None:
                stato, risposta = _http("POST", f"{API}/calendars/{cal}/events", corpo, token=token)
                if stato == 409:  # già presente (es. scritto dall'altro PC o eliminato prima): si aggiorna
                    stato, risposta = _http("PUT", f"{API}/calendars/{cal}/events/{eid}", corpo, token=token)
                if stato not in (200, 201):
                    raise CalendarError(f"Evento non scritto ({risposta.get('error', {}).get('message', stato)}).")
                db.session.add(CalendarioEvento(chiave=chiave, event_id=eid, impronta=impronta, aggiornato_at=now()))
                conteggio["creati"] += 1
            else:
                stato, risposta = _http("PUT", f"{API}/calendars/{cal}/events/{eid}", corpo, token=token)
                if stato == 404:
                    stato, risposta = _http("POST", f"{API}/calendars/{cal}/events", corpo, token=token)
                if stato not in (200, 201):
                    raise CalendarError(f"Evento non aggiornato ({risposta.get('error', {}).get('message', stato)}).")
                riga.impronta, riga.aggiornato_at = impronta, now()
                conteggio["aggiornati"] += 1

        for chiave, riga in presenti.items():
            if chiave in desiderati:
                continue
            stato, risposta = _http("DELETE", f"{API}/calendars/{cal}/events/{riga.event_id}", token=token)
            if stato not in (200, 204, 404, 410):
                raise CalendarError(f"Evento non eliminato ({risposta.get('error', {}).get('message', stato)}).")
            db.session.delete(riga)
            conteggio["eliminati"] += 1

        s.gcal_ultima_sync = now()
        s.gcal_errore = None
        db.session.commit()
        return conteggio
    except CalendarError as exc:
        db.session.commit()  # gli eventi già scritti restano registrati: niente doppioni al prossimo giro
        s.gcal_errore = str(exc)[:300]
        db.session.commit()
        raise
