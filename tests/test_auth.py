"""Test di sessioni, accesso, redirect sicuri, sola consultazione, utenti e registro.

Coprono in particolare:
- la revoca delle sessioni (uscita, cambio/reset password, disattivazione,
  cambio di ruolo, ripristino) anche per chi ha una copia del cookie;
- ``safe_next`` contro gli open redirect;
- il blocco dopo troppi tentativi, anche con richieste in parallelo, e i
  messaggi d'errore che non rivelano quali utenti esistono;
- il profilo in sola consultazione, che non apre i moduli di modifica;
- il filtro per data del registro attività.
"""
import html
import re
import threading
from datetime import date, datetime, timedelta

import pytest
from conftest import ADMIN_PASSWORD, ADMIN_USER, add_user, login
from flask import url_for

from gestionale import security
from gestionale.models import AuditLog, Claim, Client, Policy, User, db, now
from gestionale.routes.auth import MSG_ACCESSO_NEGATO
from gestionale.security import (
    MAX_TENTATIVI_LOGIN,
    PUBLIC_ENDPOINTS,
    READONLY_ALLOWED_POST,
    invalida_tutte_le_sessioni,
    safe_next,
)
from gestionale.titoli import genera_titoli

OGGI = date.today()


# ----------------------------------------------------------------------
# Supporto
# ----------------------------------------------------------------------
def _clona_sessione(app, client):
    """Un secondo browser con una copia del cookie di sessione (es. cookie rubato)."""
    cookie = client.get_cookie("session")
    assert cookie is not None, "nessun cookie di sessione da copiare"
    copia = app.test_client()
    copia.set_cookie("session", cookie.value, domain=cookie.domain)
    return copia


def _connesso(c) -> bool:
    """True se il client ha ancora una sessione valida."""
    resp = c.get("/clienti/")
    if resp.status_code == 200:
        return True
    assert resp.status_code == 302 and "/accesso" in resp.headers["Location"]
    return False


def _messaggi(resp) -> list[str]:
    """Messaggi flash mostrati nella pagina (testo, senza escape HTML)."""
    return [html.unescape(m).strip()
            for m in re.findall(r'role="alert">([^<]*)<', resp.get_data(as_text=True))]


def _id(app, username):
    with app.app_context():
        return User.query.filter_by(username=username).one().id


def _utente(app, username):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        db.session.expunge(user)
        return user


def _client_di(app, username, password):
    c = app.test_client()
    assert login(c, username, password).status_code == 302, f"accesso di {username} non riuscito"
    return c


# ----------------------------------------------------------------------
# Sessione legata all'utente
# ----------------------------------------------------------------------
def test_sessione_permanente_con_versione_e_impronta(client, app):
    with client.session_transaction() as s:
        assert s.permanent
        assert s["user_id"] == _id(app, ADMIN_USER)
        assert s["ver"] == _utente(app, ADMIN_USER).sessione_versione
        assert len(s["impronta"]) == 32


def test_logout_invalida_anche_le_copie_del_cookie(client, app):
    copia = _clona_sessione(app, client)
    assert _connesso(copia)
    versione = _utente(app, ADMIN_USER).sessione_versione
    resp = client.post("/esci")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    assert not _connesso(client)
    # La copia del cookie non vale più: si torna all'accesso con un avviso.
    resp = copia.get("/clienti/")
    assert resp.status_code == 302 and "/accesso?next=" in resp.headers["Location"]
    assert "Sessione scaduta: accedi di nuovo." in _messaggi(copia.get(resp.headers["Location"]))
    assert _utente(app, ADMIN_USER).sessione_versione == versione + 1
    # Si può comunque accedere di nuovo.
    assert login(client).status_code == 302 and _connesso(client)


def test_cambio_password_chiude_tutte_le_sessioni(client, app):
    copia = _clona_sessione(app, client)
    resp = client.post("/profilo/password", data={
        "attuale": ADMIN_PASSWORD, "nuova": "nuova-password-9", "conferma": "nuova-password-9",
    })
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    assert "Password aggiornata: accedi di nuovo con la nuova password." in _messaggi(
        client.get(resp.headers["Location"])
    )
    assert not _connesso(client)
    assert not _connesso(copia)
    assert login(client, ADMIN_USER, ADMIN_PASSWORD).status_code == 200
    assert login(client, ADMIN_USER, "nuova-password-9").status_code == 302


def test_cambio_password_errato_non_chiude_la_sessione(client, app):
    resp = client.post("/profilo/password", data={
        "attuale": "sbagliata-1", "nuova": "nuova-password-9", "conferma": "nuova-password-9",
    })
    assert resp.status_code == 200
    assert "La password attuale non è corretta." in _messaggi(resp)
    assert _connesso(client)
    # Password attuale giusta ma nuova non valida: errore, contatore azzerato.
    resp = client.post("/profilo/password", data={"attuale": ADMIN_PASSWORD, "nuova": "corta", "conferma": "corta"})
    assert resp.status_code == 200 and _connesso(client)
    assert _utente(app, ADMIN_USER).tentativi_falliti == 0


def test_cambio_password_troppi_errori_blocca_e_disconnette(client, app):
    copia = _clona_sessione(app, client)
    for _ in range(MAX_TENTATIVI_LOGIN - 1):
        resp = client.post("/profilo/password", data={
            "attuale": "tentativo-1", "nuova": "nuova-password-9", "conferma": "nuova-password-9",
        })
        assert resp.status_code == 200
    resp = client.post("/profilo/password", data={
        "attuale": "tentativo-1", "nuova": "nuova-password-9", "conferma": "nuova-password-9",
    })
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    assert not _connesso(client) and not _connesso(copia)
    assert _utente(app, ADMIN_USER).bloccato
    # Nemmeno la password giusta funziona finché dura il blocco.
    assert login(client).status_code == 200


def test_reset_password_da_admin_chiude_le_sessioni_dell_utente(client, app):
    uid = add_user(app, "mario", "password-mario-1")
    mario = _client_di(app, "mario", "password-mario-1")
    copia = _clona_sessione(app, mario)
    resp = client.post(f"/utenti/{uid}/modifica", data={
        "ruolo": "operatore", "attivo": "on", "password": "reimpostata-22", "conferma": "reimpostata-22",
    })
    assert resp.status_code == 302
    assert not _connesso(mario) and not _connesso(copia)
    assert login(mario, "mario", "reimpostata-22").status_code == 302
    # L'amministratore che ha fatto il reset resta connesso.
    assert _connesso(client)


def test_disattivazione_chiude_le_sessioni(client, app):
    uid = add_user(app, "mario", "password-mario-1")
    mario = _client_di(app, "mario", "password-mario-1")
    versione = _utente(app, "mario").sessione_versione
    client.post(f"/utenti/{uid}/modifica", data={"ruolo": "operatore"})  # attivo non spuntato
    assert not _utente(app, "mario").attivo
    assert _utente(app, "mario").sessione_versione > versione
    assert not _connesso(mario)
    assert login(mario, "mario", "password-mario-1").status_code == 200


def test_cambio_ruolo_chiude_le_sessioni(client, app):
    uid = add_user(app, "mario", "password-mario-1", ruolo="admin")
    mario = _client_di(app, "mario", "password-mario-1")
    assert mario.get("/utenti/").status_code == 200
    client.post(f"/utenti/{uid}/modifica", data={"ruolo": "operatore", "attivo": "on"})
    # Il vecchio cookie non resta amministratore fino all'uscita.
    assert not _connesso(mario)
    mario = _client_di(app, "mario", "password-mario-1")
    assert mario.get("/utenti/").status_code == 403


def test_modifica_senza_cambi_di_ruolo_stato_o_password_non_disconnette(client, app):
    uid = add_user(app, "mario", "password-mario-1")
    mario = _client_di(app, "mario", "password-mario-1")
    client.post(f"/utenti/{uid}/modifica", data={"ruolo": "operatore", "attivo": "on", "nome": "Mario Rossi"})
    assert _utente(app, "mario").nome == "Mario Rossi"
    assert _connesso(mario)


def test_cookie_vecchio_formato_non_valido(client, app):
    """Un cookie con il solo user_id (versioni precedenti o falsificato) non basta più."""
    with client.session_transaction() as s:
        for chiave in ("ver", "impronta"):
            s.pop(chiave)
    assert not _connesso(client)


def test_sessione_dopo_ripristino_con_utenti_diversi(client, app):
    """Dopo un ripristino lo stesso id può essere un altro utente: il cookie non vale più."""
    mario_id = add_user(app, "mario", "password-mario-1")
    mario = _client_di(app, "mario", "password-mario-1")
    with app.app_context():
        # Simula il database di un'altra installazione: l'id di mario è un admin diverso.
        user = db.session.get(User, mario_id)
        user.username, user.ruolo = "boss2", "admin"
        user.set_password("password-boss-2")
        db.session.commit()
    assert mario.get("/utenti/").status_code == 302
    assert not _connesso(mario)


def test_invalida_tutte_le_sessioni(client, app):
    add_user(app, "mario", "password-mario-1")
    mario = _client_di(app, "mario", "password-mario-1")
    with app.app_context():
        invalida_tutte_le_sessioni()
        db.session.commit()
    assert not _connesso(client)
    assert not _connesso(mario)


def test_post_con_sessione_revocata_torna_all_accesso_con_un_solo_avviso(client, app):
    copia = _clona_sessione(app, client)
    client.post("/esci")
    resp = copia.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Dopo uscita"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    assert _messaggi(copia.get("/accesso")) == ["Sessione scaduta: accedi di nuovo."]
    with app.app_context():
        assert Client.query.filter_by(ragione_sociale="Dopo uscita").count() == 0


# ----------------------------------------------------------------------
# safe_next: solo percorsi relativi di questa applicazione
# ----------------------------------------------------------------------
@pytest.mark.parametrize("target", [
    "/",
    "/clienti/",
    "/clienti/3",
    "/clienti/3?tab=polizze#titoli",
    "/polizze/?q=a%2Fb&page=2",
    "/cerca?q=//non-un-host",
    "/notifiche/?",
    "/percorso:con-due-punti",
    "/http://solo-un-percorso",
    "/%2F%2Fcodificato",
])
def test_safe_next_accetta_percorsi_relativi(target):
    assert safe_next(target, "/default") == target


@pytest.mark.parametrize("target", [
    None,
    "",
    123,
    "clienti/",
    " /clienti/",
    "//evil.example",
    "//evil.example/finto-login",
    "///evil.example",
    "////evil.example",
    "/\\evil.example",
    "/\\/evil.example",
    "\\\\evil.example",
    "\\/evil.example",
    "/clienti\\..\\..\\evil",
    "http://evil.example/",
    "https://evil.example/clienti/",
    "http://localhost/clienti/",
    "https://localhost/clienti/",
    "http://localhost//evil.example",
    "http://127.0.0.1:5000//evil.example/finto-login",
    "//localhost//evil.example",
    "http://localhost/\\evil.example",
    "http:/evil.example",
    "http:evil.example",
    "javascript:alert(1)",
    "JavaScript:alert(document.cookie)",
    "data:text/html,<script>alert(1)</script>",
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r\n/evil.example",
    "/\x00/evil.example",
    "/clienti/\x1b",
    "/clienti/\x7f",
    "/clienti/\x85",
    "\x00/clienti/",
])
def test_safe_next_rifiuta_url_esterni_e_ambigui(app, target):
    with app.test_request_context("/", base_url="http://localhost"):
        assert safe_next(target, "/default") == "/default"
        assert safe_next(target) is None


@pytest.mark.parametrize("next_param", [
    "http://localhost//evil.example",
    "//localhost//evil.example",
    "http://localhost/\\evil.example",
    "/\\evil.example",
    "https://evil.example/",
])
def test_login_ignora_next_pericolosi(anon_client, next_param):
    resp = anon_client.post(
        "/accesso", query_string={"next": next_param},
        data={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_login_segue_next_relativo(anon_client):
    resp = anon_client.post(
        "/accesso", query_string={"next": "/clienti/?q=rossi"},
        data={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
    )
    assert resp.headers["Location"] == "/clienti/?q=rossi"


# ----------------------------------------------------------------------
# Accesso: blocco, messaggi generici, tempi uniformi
# ----------------------------------------------------------------------
def test_blocco_dopo_tentativi_ripetuti(app, anon_client):
    for i in range(MAX_TENTATIVI_LOGIN):
        resp = login(anon_client, ADMIN_USER, f"sbagliata-{i}")
        assert resp.status_code == 200
    utente = _utente(app, ADMIN_USER)
    assert utente.bloccato and utente.tentativi_falliti == 0
    # Con il blocco attivo nemmeno la password giusta entra, e il messaggio è lo stesso.
    resp = login(anon_client)
    assert resp.status_code == 200
    assert _messaggi(resp) == [MSG_ACCESSO_NEGATO]
    with app.app_context():
        assert AuditLog.query.filter_by(azione="login_fallito").count() == MAX_TENTATIVI_LOGIN + 1


def test_blocco_temporaneo_poi_si_entra(app, anon_client):
    for i in range(MAX_TENTATIVI_LOGIN):
        login(anon_client, ADMIN_USER, f"sbagliata-{i}")
    with app.app_context():
        user = User.query.filter_by(username=ADMIN_USER).one()
        assert user.bloccato
        user.bloccato_fino = now() - timedelta(seconds=1)  # blocco scaduto
        db.session.commit()
    assert login(anon_client).status_code == 302
    utente = _utente(app, ADMIN_USER)
    assert utente.tentativi_falliti == 0 and utente.bloccato_fino is None


def test_accesso_riuscito_azzera_il_contatore(app, anon_client):
    for i in range(MAX_TENTATIVI_LOGIN - 1):
        login(anon_client, ADMIN_USER, f"sbagliata-{i}")
    assert _utente(app, ADMIN_USER).tentativi_falliti == MAX_TENTATIVI_LOGIN - 1
    assert login(anon_client).status_code == 302
    assert _utente(app, ADMIN_USER).tentativi_falliti == 0


def test_messaggio_identico_per_ogni_errore(app):
    add_user(app, "ex", "password-ex-1", attivo=False)
    add_user(app, "bloccato", "password-blo-1", bloccato_fino=now() + timedelta(minutes=10))
    casi = {
        "utente inesistente": ("nessuno-cosi", "qualunque-1"),
        "password errata": (ADMIN_USER, "sbagliata-1"),
        "utente disattivato": ("ex", "password-ex-1"),
        "account bloccato (password giusta)": ("bloccato", "password-blo-1"),
        "account bloccato (password errata)": ("bloccato", "sbagliata-1"),
        "username lunghissimo": ("x" * 500, "qualunque-1"),
    }
    for caso, (username, password) in casi.items():
        resp = login(app.test_client(), username, password)
        assert resp.status_code == 200, caso
        assert _messaggi(resp) == [MSG_ACCESSO_NEGATO], caso
        testo = resp.get_data(as_text=True)
        assert "riprova tra" not in testo, caso


def test_verifica_fittizia_per_utenti_inesistenti_disattivati_e_bloccati(app, monkeypatch):
    """Per gli account che non possono entrare si calcola comunque un hash (tempi uguali)."""
    add_user(app, "ex", "password-ex-1", attivo=False)
    add_user(app, "bloccato", "password-blo-1", bloccato_fino=now() + timedelta(minutes=10))
    fittizie, vere = [], []
    originale_fittizia = security.check_password_hash
    originale_vera = User.check_password
    monkeypatch.setattr(security, "check_password_hash",
                        lambda h, p: fittizie.append(1) or originale_fittizia(h, p))
    monkeypatch.setattr(User, "check_password", lambda self, p: vere.append(1) or originale_vera(self, p))
    for username in ("nessuno-cosi", "ex", "bloccato"):
        fittizie.clear()
        vere.clear()
        login(app.test_client(), username, "password-qualunque-1")
        assert fittizie == [1], username
        assert vere == [], username
    fittizie.clear()
    login(app.test_client(), ADMIN_USER, "sbagliata-1")
    assert fittizie == [] and vere == [1]


def test_blocco_atomico_con_richieste_parallele(app, monkeypatch):
    """Con molte richieste in parallelo si verificano al massimo MAX_TENTATIVI_LOGIN password."""
    import time

    verifiche = []
    lock = threading.Lock()
    originale = User.check_password

    def lenta(self, password):
        with lock:
            verifiche.append(password)
        time.sleep(0.05)  # simula scrypt: le richieste si sovrappongono
        return originale(self, password)

    monkeypatch.setattr(User, "check_password", lenta)
    stati, errori = [], []
    partenza = threading.Barrier(12)

    def tentativo(i):
        try:
            c = app.test_client()
            partenza.wait()
            stati.append(login(c, ADMIN_USER, f"sbagliata-{i}").status_code)
        except Exception as exc:  # noqa: BLE001 - riportato sotto
            errori.append(exc)

    threads = [threading.Thread(target=tentativo, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errori
    assert stati == [200] * 12
    assert len(verifiche) <= MAX_TENTATIVI_LOGIN
    assert _utente(app, ADMIN_USER).bloccato
    with app.app_context():
        assert AuditLog.query.filter_by(azione="login_fallito").count() == 12


def test_username_nel_registro_troncato_e_ripulito(app, anon_client):
    username = "\x1b[31m" + "b" * 300 + "\x00\r\n"
    login(anon_client, username, "qualunque-1")
    with app.app_context():
        voce = AuditLog.query.filter_by(azione="login_fallito").one()
    nome = re.search(r"«(.*)»", voce.descrizione, re.S).group(1)
    assert len(nome) <= 60
    assert not re.search(r"[\x00-\x1f\x7f]", voce.descrizione)


# ----------------------------------------------------------------------
# Profilo in sola consultazione
# ----------------------------------------------------------------------
@pytest.fixture
def lettore(app):
    add_user(app, "lettore", "password-let-1", ruolo="consultazione")
    return _client_di(app, "lettore", "password-let-1")


def _dati_di_prova(app, client):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="ACME S.r.l.")
        db.session.add(c)
        db.session.flush()
        p = Policy(client_id=c.id, compagnia="Generali", numero_polizza="P-1", ramo="incendio",
                   premio_annuo=1200.0, frazionamento="annuale", stato="attiva",
                   data_decorrenza=OGGI - timedelta(days=30), data_scadenza=OGGI + timedelta(days=335))
        db.session.add(p)
        db.session.flush()
        titoli = genera_titoli(p)
        db.session.commit()
        cid, pid, tid = c.id, p.id, titoli[0].id
    resp = client.post("/sinistri/nuovo", data={
        "client_id": cid, "policy_id": pid, "tipologia": "danni_terzi",
        "data_evento": (OGGI - timedelta(days=2)).isoformat(), "data_denuncia": OGGI.isoformat(),
        "descrizione": "Danno di prova",
    })
    assert resp.status_code == 302
    client.post(f"/opportunita/nuova/{cid}", data={"titolo": "Cyber risk", "fase": "lead"})
    with app.app_context():
        sid = Claim.query.one().id
    return cid, pid, tid, sid


# Pagine escluse dalle verifiche di sola lettura perché rotte indipendentemente
# dai permessi (a3b1ea1: manca il template titles/forecast.html).
PAGINE_ROTTE: set[str] = set()


def _endpoint_moduli(app):
    """Endpoint con moduli di inserimento/modifica: la route accetta sia GET sia POST."""
    return sorted(
        {r.endpoint for r in app.url_map.iter_rules()
         if {"GET", "POST"} <= r.methods
         and r.endpoint not in PUBLIC_ENDPOINTS
         and r.endpoint not in READONLY_ALLOWED_POST}
    )


def test_consultazione_non_apre_i_moduli_di_modifica(app, lettore):
    moduli = _endpoint_moduli(app)
    attesi = {"clients.new_client", "clients.edit_client", "policies.edit_policy", "titles.edit",
              "claims.new_claim", "claims.edit_claim", "opportunities.new_opportunity",
              "opportunities.edit_opportunity"}
    assert attesi <= set(moduli)
    regole = [r for r in app.url_map.iter_rules() if r.endpoint in moduli]
    with app.test_request_context():
        urls = [url_for(r.endpoint, **{arg: 1 for arg in r.arguments}) for r in regole]
    for url in urls:
        resp = lettore.get(url)
        assert resp.status_code == 403, url
        assert "sola consultazione" in resp.get_data(as_text=True), url


def test_consultazione_moduli_reali_vietati_ma_liste_e_schede_visibili(app, client, lettore):
    cid, pid, tid, sid = _dati_di_prova(app, client)
    vietati = ["/clienti/nuovo", f"/clienti/{cid}/modifica", f"/polizze/{pid}/modifica",
               f"/titoli/{tid}/modifica", "/sinistri/nuovo", f"/sinistri/nuovo?client_id={cid}",
               f"/sinistri/{sid}/modifica", "/opportunita/nuova", f"/opportunita/nuova/{cid}"]
    for url in vietati:
        assert lettore.get(url).status_code == 403, url
        assert client.get(url).status_code == 200, url  # l'operatore/admin li apre
    consentiti = ["/", "/clienti/", f"/clienti/{cid}", "/polizze/", f"/polizze/{pid}", "/titoli/",
                  "/titoli/foglio-cassa", "/titoli/estratto-conto",
                  "/sinistri/", f"/sinistri/{sid}", "/documenti/", "/opportunita/", "/follow-up/",
                  "/notifiche/", "/scadenzario", "/statistiche", "/cerca?q=ACME",
                  "/clienti/esporta.csv", "/polizze/esporta.csv", "/sinistri/esporta.csv",
                  "/titoli/esporta.csv", "/profilo/password"]
    for url in consentiti:
        assert lettore.get(url).status_code == 200, url


def test_consultazione_tutte_le_pagine_di_sola_lettura_restano_aperte(app, lettore):
    """Ogni GET senza parametri e senza modulo (fuori dall'amministrazione) resta accessibile."""
    regole = [r for r in app.url_map.iter_rules()
              if "GET" in r.methods and "POST" not in r.methods and not r.arguments
              and not r.endpoint.startswith(("static", "settings.", "users.", "audit.", "sincronizzazione."))
              and r.endpoint not in PAGINE_ROTTE]
    assert len(regole) > 10
    with app.test_request_context():
        urls = [url_for(r.endpoint) for r in regole]
    for url in urls:
        assert lettore.get(url).status_code == 200, url


def test_consultazione_post_rifiutato_torna_alla_pagina_precedente(app, lettore):
    dati = {"tipo": "azienda", "ragione_sociale": "Non salvare"}
    resp = lettore.post("/clienti/nuovo", data=dati, headers={"Referer": "http://localhost/clienti/?q=x"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/clienti/?q=x"
    for referer in ("http://localhost//evil.example", "https://evil.example/clienti/", "javascript:alert(1)"):
        resp = lettore.post("/clienti/nuovo", data=dati, headers={"Referer": referer})
        assert resp.headers["Location"] == "/", referer
    with app.app_context():
        assert Client.query.filter_by(ragione_sociale="Non salvare").count() == 0
    # Uscita e cambio password restano consentiti.
    assert lettore.get("/profilo/password").status_code == 200
    assert lettore.post("/esci").status_code == 302


# ----------------------------------------------------------------------
# Gestione utenti
# ----------------------------------------------------------------------
def test_admin_che_si_declassa_va_alla_dashboard(client, app):
    add_user(app, "admin2", "password-adm-2", ruolo="admin")
    admin_id = _id(app, ADMIN_USER)
    resp = client.post(f"/utenti/{admin_id}/modifica", data={"ruolo": "operatore", "attivo": "on"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/"
    pagina = client.get("/")
    assert pagina.status_code == 200  # la sessione corrente resta valida con il nuovo ruolo
    assert "non hai più accesso alla gestione utenti" in pagina.get_data(as_text=True)
    assert client.get("/utenti/").status_code == 403
    assert _utente(app, ADMIN_USER).ruolo == "operatore"


def test_admin_che_si_disattiva_viene_disconnesso(client, app):
    add_user(app, "admin2", "password-adm-2", ruolo="admin")
    admin_id = _id(app, ADMIN_USER)
    resp = client.post(f"/utenti/{admin_id}/modifica", data={"ruolo": "admin"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    assert not _connesso(client)
    assert not _utente(app, ADMIN_USER).attivo


def test_admin_che_reimposta_la_propria_password_resta_connesso(client, app):
    copia = _clona_sessione(app, client)
    admin_id = _id(app, ADMIN_USER)
    resp = client.post(f"/utenti/{admin_id}/modifica", data={
        "ruolo": "admin", "attivo": "on", "password": "altra-password-3", "conferma": "altra-password-3",
    })
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/utenti/")
    assert _connesso(client)
    assert not _connesso(copia)


@pytest.mark.parametrize("dati", [
    {"ruolo": "operatore", "attivo": "on"},
    {"ruolo": "consultazione", "attivo": "on"},
    {"ruolo": "admin"},  # disattivato
])
def test_ultimo_admin_non_si_puo_togliere_e_i_dati_restano(client, app, dati):
    admin_id = _id(app, ADMIN_USER)
    resp = client.post(f"/utenti/{admin_id}/modifica", data={**dati, "nome": "Nuovo Nome"})
    assert resp.status_code == 400
    testo = resp.get_data(as_text=True)
    assert "almeno un amministratore attivo" in testo
    assert 'value="Nuovo Nome"' in testo  # il valore digitato non va perso
    utente = _utente(app, ADMIN_USER)
    assert utente.ruolo == "admin" and utente.attivo and utente.nome == "Amministratore"
    assert _connesso(client)


def test_ultimo_admin_ricontrollato_dentro_la_transazione(client, app, monkeypatch):
    """Se il controllo preliminare viene superato (es. corsa tra due admin), il
    ricontrollo dopo il flush impedisce comunque di restare senza amministratori."""
    from gestionale.routes import users

    monkeypatch.setattr(users, "_altri_admin_attivi", lambda user: 1)
    admin_id = _id(app, ADMIN_USER)
    resp = client.post(f"/utenti/{admin_id}/modifica", data={"ruolo": "operatore", "attivo": "on"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith(f"/utenti/{admin_id}/modifica")
    assert _utente(app, ADMIN_USER).ruolo == "admin"
    assert _connesso(client)


@pytest.mark.parametrize("username", ["u" * 61, "nome\x00nullo", "a\tb", ""])
def test_nuovo_utente_username_non_valido(client, app, username):
    resp = client.post("/utenti/nuovo", data={
        "username": username, "ruolo": "operatore", "password": "password-giu-1", "conferma": "password-giu-1",
    })
    assert resp.status_code == 400
    with app.app_context():
        assert User.query.count() == 1


# ----------------------------------------------------------------------
# Registro attività
# ----------------------------------------------------------------------
def _voce(app, quando, descrizione):
    with app.app_context():
        db.session.add(AuditLog(username="admin", azione="modifica", entita="cliente",
                                entita_id=7, descrizione=descrizione, created_at=quando))
        db.session.commit()


def test_registro_filtro_al_include_tutto_il_giorno(client, app):
    _voce(app, datetime(2026, 3, 9, 23, 59, 59), "voce-giorno-prima")
    _voce(app, datetime(2026, 3, 10, 0, 0, 0), "voce-mezzanotte")
    _voce(app, datetime(2026, 3, 10, 23, 59, 59, 999000), "voce-sera-tardi")
    _voce(app, datetime(2026, 3, 11, 0, 0, 1), "voce-giorno-dopo")
    for url in ("/registro/?dal=2026-03-10&al=2026-03-10", "/registro/esporta.csv?dal=2026-03-10&al=2026-03-10",
                "/registro/?dal=10/03/2026&al=10/03/2026"):
        testo = client.get(url).get_data(as_text=True)
        assert "voce-mezzanotte" in testo and "voce-sera-tardi" in testo, url
        assert "voce-giorno-prima" not in testo and "voce-giorno-dopo" not in testo, url
    # Estremi invertiti: vengono scambiati.
    testo = client.get("/registro/?dal=2026-03-11&al=2026-03-10").get_data(as_text=True)
    assert "voce-sera-tardi" in testo and "voce-giorno-dopo" in testo
    assert "voce-giorno-prima" not in testo


@pytest.mark.parametrize("query", [
    "al=9999-12-31",
    "dal=0001-01-01&al=9999-12-31",
    "al=2100-12-31",
    "dal=31/12/9999",
    "al=non-una-data",
    "page=99999999999999999999999",
    "page=-3",
    "entita_id=99999999999999999999999",
    "entita_id=-5",
    "entita_id=abc",
])
def test_registro_parametri_estremi_non_danno_errore(client, query):
    assert client.get(f"/registro/?{query}").status_code == 200
    assert client.get(f"/registro/esporta.csv?{query}").status_code == 200


def test_registro_filtro_entita_id_e_testo_letterale(client, app):
    _voce(app, datetime(2026, 3, 10, 9, 0), "sconto del 10% applicato")
    _voce(app, datetime(2026, 3, 10, 9, 5), "altra modifica")
    testo = client.get("/registro/?q=%25").get_data(as_text=True)
    assert "sconto del 10% applicato" in testo and "altra modifica" not in testo
    testo = client.get("/registro/?entita_id=7").get_data(as_text=True)
    assert "sconto del 10% applicato" in testo and "altra modifica" in testo
    testo = client.get("/registro/?entita_id=8").get_data(as_text=True)
    assert "sconto del 10% applicato" not in testo


# ----------------------------------------------------------------------
# Header di sicurezza
# ----------------------------------------------------------------------
def test_content_security_policy_sulle_pagine_html(client, anon_client):
    for resp in (client.get("/"), anon_client.get("/accesso")):
        csp = resp.headers["Content-Security-Policy"]
        for direttiva in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'self'",
                          "base-uri 'self'", "form-action 'self'"):
            assert direttiva in csp
    assert "Content-Security-Policy" not in client.get("/clienti/esporta.csv").headers
