"""Note: diario delle attività, promemoria via email, Google Calendar."""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

from gestionale import create_app, diario, google, mailer, promemoria
from gestionale.models import Client, Nota, Settings, db


@pytest.fixture
def app():
    cartella = tempfile.mkdtemp()
    db_path = os.path.join(cartella, "gestionale.db")
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "UPLOAD_FOLDER": tempfile.mkdtemp(),
        "SECRET_KEY": "test",
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _cliente(app, nome="Rossi Srl"):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale=nome)
        db.session.add(c)
        db.session.commit()
        return c.id


def _gmail(app):
    with app.app_context():
        s = Settings.get()
        s.smtp_host, s.smtp_user, s.mail_from = "smtp.gmail.com", "io@gmail.com", "io@gmail.com"
        db.session.commit()


def test_nuova_nota_con_promemoria_e_diario_per_giorno(app, client):
    cid = _cliente(app)
    domani = date.today() + timedelta(days=1)
    r = client.post("/note/nuova", data={
        "giorno": date.today().isoformat(), "ora": "10:30", "sezione": "chiamate",
        "titolo": "Chiamato Rossi per il rinnovo", "testo": "Vuole il preventivo entro venerdì",
        "client_id": cid, "promemoria_giorno": domani.isoformat(), "promemoria_ora": "09:15",
        "promemoria_email": "1", "next": "/note/",
    })
    assert r.status_code == 302 and r.headers["Location"].endswith("/note/")
    with app.app_context():
        n = Nota.query.one()
        assert (n.sezione, n.ora, n.client_id) == ("chiamate", "10:30", cid)
        assert n.promemoria_il == datetime.combine(domani, datetime.strptime("09:15", "%H:%M").time())
        assert n.promemoria_email and n.promemoria_aperto and not n.promemoria_scaduto
    pagina = client.get("/note/").get_data(as_text=True)
    assert "Oggi" in pagina and "Chiamato Rossi per il rinnovo" in pagina and "Vuole il preventivo" in pagina
    assert "calendar.google.com" in pagina and "Promemoria da fare" in pagina
    # Nella scheda del cliente, scheda «Note»
    assert "Chiamato Rossi per il rinnovo" in client.get(f"/clienti/{cid}").get_data(as_text=True)
    # Nell'agenda di «Oggi»
    assert "Promemoria 09:15" in client.get("/").get_data(as_text=True)


def test_filtri_sezione_cliente_e_ricerca(app, client):
    cid = _cliente(app)
    for titolo, sezione, cliente in (("Preventivo flotta", "preventivi", cid), ("Corso IVASS", "formazione", None)):
        client.post("/note/nuova", data={"titolo": titolo, "sezione": sezione, "client_id": cliente or ""})
    assert "Corso IVASS" not in client.get("/note/?sezione=preventivi").get_data(as_text=True)
    assert "Preventivo flotta" not in client.get(f"/note/?sezione=formazione").get_data(as_text=True)
    assert "Corso IVASS" not in client.get(f"/note/?cliente={cid}").get_data(as_text=True)
    pagina = client.get("/note/?q=ivass").get_data(as_text=True)
    assert "Corso IVASS" in pagina and "Preventivo flotta" not in pagina


def test_validazioni_e_destinazione_sicura(app, client):
    client.post("/note/nuova", data={"titolo": "  ", "sezione": "chiamate"})
    with app.app_context():
        assert Nota.query.count() == 0
    r = client.post("/note/nuova", data={"titolo": "X", "sezione": "inventata", "client_id": "9999",
                                         "ora": "25:99", "next": "//evil.example"})
    assert r.headers["Location"].endswith("/note/")
    with app.app_context():
        n = Nota.query.one()
        assert (n.sezione, n.client_id, n.ora) == ("altro", None, None)


def test_modifica_fatto_ed_elimina(app, client):
    client.post("/note/nuova", data={"titolo": "Richiamare", "promemoria_giorno": "2026-11-03",
                                     "promemoria_ora": "08:00"})
    with app.app_context():
        nid = Nota.query.one().id
    client.post(f"/note/{nid}/fatto")
    with app.app_context():
        assert db.session.get(Nota, nid).promemoria_fatto
    # Spostare il promemoria lo rimette «da fare»
    client.post(f"/note/{nid}/modifica", data={"titolo": "Richiamare", "promemoria_giorno": "2026-11-04",
                                                "promemoria_ora": "08:00"})
    with app.app_context():
        n = db.session.get(Nota, nid)
        assert not n.promemoria_fatto and n.promemoria_il.day == 4 and not n.promemoria_email
    # Togliere la data toglie il promemoria
    client.post(f"/note/{nid}/modifica", data={"titolo": "Richiamare", "promemoria_giorno": ""})
    with app.app_context():
        assert db.session.get(Nota, nid).promemoria_il is None
    assert client.post(f"/note/{nid}/fatto").status_code == 404
    assert client.get(f"/note/{nid}/modifica").status_code == 200
    client.post(f"/note/{nid}/elimina")
    with app.app_context():
        assert Nota.query.count() == 0


def test_eliminare_il_cliente_conserva_le_note(app, client):
    cid = _cliente(app)
    client.post("/note/nuova", data={"titolo": "Incontro", "client_id": cid})
    client.post(f"/clienti/{cid}/elimina")
    with app.app_context():
        n = Nota.query.one()
        assert n.titolo == "Incontro" and n.client_id is None


def test_google_calendar_link_e_ics():
    link = google.link_calendar_ora("Richiamare Rossi", datetime(2026, 11, 3, 9, 15), "dettagli")
    assert "dates=20261103T091500%2F20261103T094500" in link and "ctz=Europe%2FRome" in link
    ics = google.calendario_ics([{"uid": "n1", "titolo": "Richiamare", "inizio": datetime(2026, 11, 3, 9, 15)}],
                                "Deal Combined - Promemoria").decode()
    assert "BEGIN:VALARM" in ics and "TRIGGER:PT0M" in ics
    assert "DTSTART:2026110" in ics and ics.split("DTSTART:")[1][15] == "Z"


def test_ics_dei_promemoria(app, client):
    domani = date.today() + timedelta(days=1)
    client.post("/note/nuova", data={"titolo": "Firma polizza", "promemoria_giorno": domani.isoformat(),
                                     "promemoria_ora": "11:00"})
    r = client.get("/note/promemoria.ics")
    assert r.status_code == 200 and b"Firma polizza" in r.data and b"BEGIN:VALARM" in r.data


def _nota(app, minuti_fa=5, email=True, fatto=False, titolo="Chiama Bianchi"):
    with app.app_context():
        n = Nota(titolo=titolo, sezione="chiamate", promemoria_il=datetime.now() - timedelta(minutes=minuti_fa),
                 promemoria_email=email, promemoria_fatto=fatto)
        db.session.add(n)
        db.session.commit()
        return n.id


def test_email_del_promemoria_una_volta_sola(app, monkeypatch):
    inviati = []
    monkeypatch.setattr(mailer, "invia_al_cliente", lambda a, oggetto, testo, **k: inviati.append((a, oggetto)))
    nid = _nota(app)
    _nota(app, minuti_fa=-30, titolo="Futuro")          # non ancora
    _nota(app, minuti_fa=60 * 7, titolo="Troppo vecchio")  # fuori tempo
    _nota(app, email=False, titolo="Senza email")
    _nota(app, fatto=True, titolo="Già fatto")
    assert diario.invia_promemoria(app) == 0  # email non configurata: nessun invio
    _gmail(app)
    assert diario.invia_promemoria(app) == 1
    assert inviati == [("io@gmail.com", "Promemoria: Chiama Bianchi")]
    assert diario.invia_promemoria(app) == 0  # già inviata (anche da un altro PC)
    with app.app_context():
        assert diario.gia_inviato(app, db.session.get(Nota, nid))


def test_errore_di_invio_si_riprova(app, monkeypatch):
    _gmail(app)
    _nota(app)

    def guasto(*a, **k):
        raise OSError("rete assente")

    monkeypatch.setattr(mailer, "invia_al_cliente", guasto)
    assert diario.invia_promemoria(app) == 0
    inviati = []
    monkeypatch.setattr(mailer, "invia_al_cliente", lambda *a, **k: inviati.append(a))
    assert diario.invia_promemoria(app) == 1 and len(inviati) == 1


def test_in_pausa_le_email_partono_senza_tenere_aperto_il_database(app, monkeypatch):
    _gmail(app)
    _nota(app)
    monkeypatch.setattr(mailer, "invia_al_cliente", lambda *a, **k: None)
    app.config["DC_IN_PAUSA"] = True
    assert diario.invia_promemoria(app) == 1
    with app.app_context():
        assert db.engine.pool.checkedin() == 0


def test_notifica_di_windows_per_il_promemoria(app):
    _nota(app, minuti_fa=1, titolo="Firma Verdi")
    with app.app_context():
        elementi = promemoria.elementi_di_oggi()
    assert [e["tipo"] for e in elementi] == ["nota"]
    a = promemoria.Annunciatore()
    titolo, testo = a.novita(elementi)
    assert titolo == "Promemoria: Firma Verdi" and "Firma Verdi" in testo
    assert a.novita(elementi) is None
