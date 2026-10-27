"""PIN e privacy, PDF delle schede, Gmail/Drive/Calendar, promemoria di Windows."""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

from gestionale import create_app, google, mailer, pdf, privacy, promemoria
from gestionale.models import Client, Document, FollowUp, Policy, SchedaCompilata, Settings, db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "UPLOAD_FOLDER": tempfile.mkdtemp(),
        "SECRET_KEY": "test",
    })
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


# ----------------------------------------------------------------------
# PIN
# ----------------------------------------------------------------------
def test_hash_e_regole_del_pin():
    h = privacy.hash_segreto("4827")
    assert h.startswith("scrypt$") and privacy.verifica_segreto("4827", h)
    assert not privacy.verifica_segreto("4828", h)
    assert not privacy.verifica_segreto("4827", "formato$rotto")
    assert privacy.pin_valido("12a4") and privacy.pin_valido("123")
    assert privacy.pin_valido("1111") and privacy.pin_valido("1234") and privacy.pin_valido("9876")
    assert privacy.pin_valido("4827") is None
    codice = privacy.nuovo_codice_recupero()
    assert len(codice) == 14 and privacy.normalizza_codice(codice.lower().replace("-", " ")) == codice


def _imposta_pin(client, pin="4827"):
    r = client.post("/impostazioni/privacy", data={"azione": "imposta", "pin": pin, "pin_conferma": pin})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    import re

    return re.search(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", html).group(0)


def test_pin_blocca_e_sblocca(app, client):
    assert client.get("/").status_code == 200
    _imposta_pin(client)
    assert client.get("/").status_code == 200  # chi lo imposta resta dentro

    nuovo = app.test_client()
    r = nuovo.get("/clienti/")
    assert r.status_code == 302 and "/sblocca" in r.headers["Location"]
    assert nuovo.post("/sblocca?next=/clienti/", data={"pin": "0000"}).status_code == 200
    r = nuovo.post("/sblocca?next=/clienti/", data={"pin": "4827"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/clienti/")
    assert nuovo.get("/clienti/").status_code == 200
    # «Blocca ora»
    nuovo.post("/blocca")
    assert nuovo.get("/clienti/").status_code == 302


def test_redirect_esterno_rifiutato(client):
    _imposta_pin(client)
    altro = client.application.test_client()
    for dest in ("//evil.example", "https://evil.example", "/\\evil.example"):
        r = altro.post(f"/sblocca?next={dest}", data={"pin": "4827"})
        assert r.headers["Location"] in ("/", "http://localhost/")


def test_tentativi_e_attesa(app, client):
    _imposta_pin(client)
    altro = app.test_client()
    for _ in range(privacy.TENTATIVI_MASSIMI):
        altro.post("/sblocca", data={"pin": "0000"})
    with app.app_context():
        assert Settings.get().pin_attesa_fino > datetime.utcnow()
    # Durante l'attesa anche il PIN giusto non entra.
    altro.post("/sblocca", data={"pin": "4827"})
    assert altro.get("/clienti/").status_code == 302


def test_inattivita_e_finestra_nascosta(app, client):
    _imposta_pin(client)
    with client.session_transaction() as s:
        s["dc_attivita"] = s["dc_attivita"] - 11 * 60  # oltre i 10 minuti predefiniti
    assert client.get("/").status_code == 302

    client.post("/sblocca", data={"pin": "4827"})
    assert client.get("/").status_code == 200
    # Finestra chiusa nella barra: alla riapertura serve di nuovo il PIN.
    app.config["DC_NASCOSTA_ALLE"] = datetime.utcnow().timestamp() + 1
    assert client.get("/").status_code == 302


def test_codice_di_recupero(app, client):
    codice = _imposta_pin(client)
    altro = app.test_client()
    altro.post("/sblocca/recupero", data={"codice": "AAAA-BBBB-CCCC"})
    with app.app_context():
        assert Settings.get().pin_hash
    r = altro.post("/sblocca/recupero", data={"codice": codice.lower()})
    assert r.status_code == 302
    with app.app_context():
        assert Settings.get().pin_hash is None


def test_cambio_pin_richiede_quello_attuale(app, client):
    _imposta_pin(client)
    client.post("/impostazioni/privacy", data={"azione": "rimuovi", "pin_attuale": "0000"})
    with app.app_context():
        assert Settings.get().pin_hash
    client.post("/impostazioni/privacy", data={"azione": "rimuovi", "pin_attuale": "4827"})
    with app.app_context():
        assert Settings.get().pin_hash is None


# ----------------------------------------------------------------------
# PDF, Drive, Gmail, Calendar
# ----------------------------------------------------------------------
STRUTTURA = {"titolo": "Prova", "sezioni": [
    {"titolo": "Dati", "tipo": "campi", "campi": ["Nome"]},
    {"titolo": "Domande", "tipo": "domande", "domande": ["Perché?"]},
    {"titolo": "Controlli", "tipo": "check", "voci": ["Uno", "Due", "Tre"]},
    {"titolo": "Tabella", "tipo": "tabella", "colonne": ["A", "B"], "righe": 3},
]}


def test_pdf_e_nome_file():
    dati = pdf.scheda_pdf("Prova <&>", "Cliente/1", date(2026, 10, 1), "Anna", STRUTTURA,
                          {"s0c0": "Mario", "s1d0": "Perché sì", "s2v1": True, "s3r0k0": "x"})
    assert dati.startswith(b"%PDF") and len(dati) > 1000
    nome = pdf.nome_file("Scheda: a/b", "Rossi*", date(2026, 10, 1))
    assert nome == "2026-10-01 Scheda ab - Rossi.pdf"


def test_salva_in_drive_senza_sovrascrivere(tmp_path):
    p1 = google.salva_in_drive(tmp_path, "Rossi: S.r.l.", "a.pdf", b"1")
    p2 = google.salva_in_drive(tmp_path, "Rossi: S.r.l.", "a.pdf", b"2")
    assert p1.parent == tmp_path / "Deal Combined" / "Clienti" / "Rossi S.r.l"
    assert p2.name == "a (2).pdf" and p1.read_bytes() == b"1"
    with pytest.raises(FileNotFoundError):
        google.salva_in_drive(tmp_path / "manca", "X", "a.pdf", b"")


def test_calendar_link_e_ics():
    link = google.link_calendar("Chiama Rossi", date(2026, 11, 3), "note")
    assert "action=TEMPLATE" in link and "dates=20261103%2F20261104" in link
    ics = google.calendario_ics([{"uid": "f1", "titolo": "Rinnovo, polizza; A", "giorno": date(2026, 11, 3),
                                  "dettagli": "x" * 200}]).decode()
    assert "DTSTART;VALUE=DATE:20261103" in ics and "Rinnovo\\, polizza\\; A" in ics
    assert all(len(r.encode()) <= 75 for r in ics.split("\r\n"))


def test_invio_email_con_allegato(app, monkeypatch):
    inviati = []
    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: inviati.append(msg))
    with app.app_context():
        s = Settings.get()
        with pytest.raises(ValueError):
            mailer.invia_al_cliente("a@b.it", "Oggetto", "Testo", settings=s)
        s.smtp_host, s.mail_from = "smtp.gmail.com", "io@gmail.com"
        with pytest.raises(ValueError):
            mailer.invia_al_cliente("a@b.it\r\nBcc: x@y.it", "O", "T", settings=s)
        mailer.invia_al_cliente("a@b.it", "Oggetto\nfalso", "Testo", [("s.pdf", b"%PDF", "application/pdf")], s)
    msg = inviati[0]
    assert msg["To"] == "a@b.it" and "\n" not in msg["Subject"]
    assert [a.get_filename() for a in msg.iter_attachments()] == ["s.pdf"]


@pytest.fixture
def scheda(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Rossi Srl", email="rossi@example.it")
        db.session.add(c)
        db.session.flush()
        sc = SchedaCompilata(client_id=c.id, scheda_id="prova", titolo="Prova", data_compilazione=date(2026, 10, 1),
                             contenuto={"struttura": STRUTTURA, "valori": {"s0c0": "Mario"}})
        db.session.add(sc)
        db.session.commit()
        return c.id, sc.id


def test_route_pdf_salva_e_invia(app, client, scheda, monkeypatch, tmp_path):
    cid, sid = scheda
    r = client.get(f"/clienti/{cid}/schede/{sid}/pdf")
    assert r.status_code == 200 and r.data.startswith(b"%PDF")

    client.post(f"/clienti/{cid}/schede/{sid}/salva-pdf", data={"dove": "documenti"})
    with app.app_context():
        doc = Document.query.one()
        assert doc.categoria == "scheda" and doc.original_name.endswith(".pdf")

    from gestionale.routes import client_sheets

    monkeypatch.setattr(client_sheets, "cartella_drive", lambda: str(tmp_path))
    client.post(f"/clienti/{cid}/schede/{sid}/salva-pdf", data={"dove": "drive"})
    assert list((tmp_path / "Deal Combined" / "Clienti" / "Rossi Srl").glob("*.pdf"))

    html = client.get(f"/clienti/{cid}/schede/{sid}/invia").get_data(as_text=True)
    assert 'value="rossi@example.it"' in html
    inviati = []
    monkeypatch.setattr(mailer, "invia_al_cliente", lambda *a, **k: inviati.append(a))
    r = client.post(f"/clienti/{cid}/schede/{sid}/invia",
                    data={"destinatario": "rossi@example.it", "oggetto": "O", "testo": "T"})
    assert r.status_code == 302 and inviati[0][3][0][2] == "application/pdf"


def test_impostazioni_google_e_ics_followup(app, client, tmp_path):
    app.config["DC_CONFIG_FILE"] = str(tmp_path / "config.json")
    client.post("/impostazioni/google", data={"azione": "drive", "cartella_drive": str(tmp_path)})
    assert str(tmp_path) in (tmp_path / "config.json").read_text()
    client.post("/impostazioni/google", data={"azione": "gmail", "gmail": "io@gmail.com",
                                              "password": "abcd efgh ijkl mnop"})
    with app.app_context():
        s = Settings.get()
        assert (s.smtp_host, s.smtp_password, s.mail_from) == ("smtp.gmail.com", "abcdefghijklmnop", "io@gmail.com")
        c = Client(tipo="azienda", ragione_sociale="Bianchi")
        db.session.add(c)
        db.session.flush()
        db.session.add(FollowUp(client_id=c.id, titolo="Chiamare", data_scadenza=date(2026, 11, 3)))
        db.session.commit()
    r = client.get("/follow-up/calendario.ics")
    assert r.status_code == 200 and b"BEGIN:VEVENT" in r.data and b"Chiamare" in r.data


# ----------------------------------------------------------------------
# Promemoria di Windows
# ----------------------------------------------------------------------
def test_promemoria_e_annunciatore(app):
    oggi = date(2026, 10, 27)
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Verdi")
        db.session.add(c)
        db.session.flush()
        db.session.add_all([
            FollowUp(client_id=c.id, titolo="Ieri", data_scadenza=oggi - timedelta(days=1)),
            FollowUp(client_id=c.id, titolo="Domani", data_scadenza=oggi + timedelta(days=1)),
            FollowUp(client_id=c.id, titolo="Fatto", data_scadenza=oggi, stato="completato"),
            Policy(client_id=c.id, compagnia="Generali", numero_polizza="9", data_scadenza=oggi + timedelta(days=3)),
            Policy(client_id=c.id, compagnia="Generali", numero_polizza="10", data_scadenza=oggi + timedelta(days=30)),
        ])
        db.session.commit()
        elementi = promemoria.elementi_di_oggi(oggi)
    assert [e["tipo"] for e in elementi] == ["followup", "polizza"]
    titolo, testo = promemoria.messaggio(elementi)
    assert titolo == "Oggi: 1 follow-up da fare (1 in ritardo), 1 polizza in scadenza"
    assert "Ieri · Verdi" in testo

    a = promemoria.Annunciatore()
    assert a.novita(elementi, oggi)
    assert a.novita(elementi, oggi) is None  # niente di nuovo: nessuna notifica
    assert a.novita(elementi, oggi + timedelta(days=1))  # il giorno dopo si ricorda di nuovo
    assert promemoria.messaggio([]) is None


def test_icona_della_barra():
    pytest.importorskip("PIL")
    from gestionale import tray

    img = tray.immagine_icona(32)
    assert img.size == (32, 32) and img.getpixel((12, 26)) == (29, 59, 48, 255)


def test_mostra_finestra_richiede_intestazione(app, client):
    assert client.post("/impostazioni/mostra").status_code == 404
    chiamate = []
    app.config["DC_MOSTRA"] = lambda: chiamate.append(1)
    assert client.post("/impostazioni/mostra").status_code == 404
    assert client.post("/impostazioni/mostra", headers={"X-DC-Azione": "mostra"}).status_code == 204
