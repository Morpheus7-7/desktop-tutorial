"""Test della gestione sinistri."""
import io
from datetime import date, timedelta

from gestionale.models import Claim, ClaimNote, Client, Document, Notification, Policy, db

OGGI = date.today()


def _cliente_polizza(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Officina Bianchi")
        db.session.add(c)
        db.session.flush()
        p = Policy(client_id=c.id, compagnia="UnipolSai", numero_polizza="U-1", ramo="rct_rco",
                   premio_annuo=2000.0, stato="attiva", data_scadenza=OGGI + timedelta(days=200))
        db.session.add(p)
        db.session.commit()
        return c.id, p.id


def _apri(client, cid, pid=None, **extra):
    dati = {"client_id": cid, "policy_id": pid or "", "tipologia": "danni_terzi",
            "data_evento": (OGGI - timedelta(days=2)).isoformat(),
            "data_denuncia": OGGI.isoformat(), "descrizione": "Danno a un cliente in officina"}
    dati.update(extra)
    return client.post("/sinistri/nuovo", data=dati)


def test_apertura_sinistro_numerazione_e_cronologia(client, app):
    cid, pid = _cliente_polizza(app)
    resp = _apri(client, cid, pid, importo_riservato="3.500,00")
    assert resp.status_code == 302
    _apri(client, cid, pid)
    with app.app_context():
        s1, s2 = Claim.query.order_by(Claim.id).all()
        anno = OGGI.year
        assert s1.numero == f"SIN-{anno}-0001" and s2.numero == f"SIN-{anno}-0002"
        assert s1.policy_id == pid and s1.importo_riservato == 3500.0
        assert ClaimNote.query.filter_by(claim_id=s1.id, tipo="stato").count() == 1
    assert client.get(resp.headers["Location"]).status_code == 200
    assert client.get(f"/polizze/{pid}").status_code == 200


def test_validazioni_sinistro(client, app):
    cid, _ = _cliente_polizza(app)
    assert _apri(client, cid, data_evento=(OGGI + timedelta(days=1)).isoformat()).status_code == 400
    assert _apri(client, cid, data_denuncia=(OGGI - timedelta(days=10)).isoformat()).status_code == 400
    assert _apri(client, cid, data_evento="").status_code == 400
    assert _apri(client, cid, importo_liquidato="-5").status_code == 400
    with app.app_context():
        assert Claim.query.count() == 0


def test_polizza_di_altro_cliente_ignorata(client, app):
    cid, _ = _cliente_polizza(app)
    _, pid_altro = _cliente_polizza(app)
    _apri(client, cid, pid_altro)
    with app.app_context():
        assert Claim.query.one().policy_id is None


def test_cambio_stato_liquidazione(client, app):
    cid, pid = _cliente_polizza(app)
    _apri(client, cid, pid, importo_riservato="1000")
    with app.app_context():
        sid = Claim.query.one().id
    # Liquidato senza importo: rifiutato.
    client.post(f"/sinistri/{sid}/stato", data={"stato": "liquidato"})
    with app.app_context():
        assert db.session.get(Claim, sid).stato == "aperto"
    client.post(f"/sinistri/{sid}/stato", data={"stato": "perizia", "commento": "Perito incaricato"})
    client.post(f"/sinistri/{sid}/stato", data={"stato": "liquidato", "importo_liquidato": "800"})
    with app.app_context():
        s = db.session.get(Claim, sid)
        assert s.stato == "liquidato" and not s.aperto
        assert s.importo_liquidato == 800.0 and s.data_chiusura == OGGI and s.data_liquidazione == OGGI
        assert s.costo == 800.0  # la riserva non conta più a sinistro chiuso
        assert s.cliente.rapporto_sp == 40.0
        testi = [e.testo for e in s.eventi]
        assert any("Perito incaricato" in t for t in testi)
    # Riapertura: torna aperto e la data di chiusura si azzera.
    client.post(f"/sinistri/{sid}/stato", data={"stato": "istruttoria"})
    with app.app_context():
        assert db.session.get(Claim, sid).data_chiusura is None


def test_notifica_sinistro_da_denunciare(client, app):
    cid, pid = _cliente_polizza(app)
    _apri(client, cid, pid, data_evento=(OGGI - timedelta(days=5)).isoformat(), data_denuncia="")
    client.get("/")
    with app.app_context():
        s = Claim.query.one()
        chiave = f"sinistro:{s.id}:{s.data_evento.isoformat()}:denuncia:scaduta"
        n = Notification.query.filter_by(dedup_key=chiave).one()
        assert n.livello == "danger" and "1913" in n.messaggio
        sid = s.id
    # Registrando la denuncia la notifica viene chiusa.
    client.post(f"/sinistri/{sid}/modifica", data={
        "policy_id": pid, "tipologia": "danni_terzi",
        "data_evento": (OGGI - timedelta(days=5)).isoformat(), "data_denuncia": OGGI.isoformat(),
    })
    with app.app_context():
        assert Notification.query.filter_by(dedup_key=chiave).one().letta
        assert db.session.get(Claim, sid).denuncia_tardiva


def test_documenti_e_note_del_sinistro(client, app):
    cid, pid = _cliente_polizza(app)
    _apri(client, cid, pid)
    with app.app_context():
        sid = Claim.query.one().id
    resp = client.post(f"/documenti/carica/{cid}", data={
        "file": (io.BytesIO(b"foto danno"), "foto.jpg"), "claim_id": sid, "categoria": "sinistro",
    }, content_type="multipart/form-data")
    assert f"/sinistri/{sid}" in resp.headers["Location"]
    client.post(f"/sinistri/{sid}/nota", data={"testo": "Sollecitata la compagnia"})
    with app.app_context():
        doc = Document.query.one()
        assert doc.claim_id == sid
        assert ClaimNote.query.filter_by(claim_id=sid, tipo="nota").one().username == "admin"
    pagina = client.get(f"/sinistri/{sid}").get_data(as_text=True)
    assert "foto.jpg" in pagina and "Sollecitata la compagnia" in pagina

    client.post(f"/sinistri/{sid}/elimina")
    with app.app_context():
        assert Claim.query.count() == 0
        assert Document.query.one().claim_id is None


def test_lista_ricerca_ed_export_sinistri(client, app):
    cid, pid = _cliente_polizza(app)
    _apri(client, cid, pid, controparte="Mario Neri")
    assert "Mario Neri" in client.get("/sinistri/?q=Neri").get_data(as_text=True)
    assert "SIN-" in client.get("/cerca?q=Neri").get_data(as_text=True)
    assert client.get("/sinistri/?filtro=chiusi").status_code == 200
    csv = client.get("/sinistri/esporta.csv").get_data(as_text=True)
    assert "Officina Bianchi" in csv and "Mario Neri" in csv


def test_eliminazione_cliente_con_polizze_titoli_e_sinistri(client, app):
    import os

    cid, pid = _cliente_polizza(app)
    client.post(f"/polizze/{pid}/genera-titoli")
    _apri(client, cid, pid)
    with app.app_context():
        sid = Claim.query.one().id
    client.post(f"/documenti/carica/{cid}", data={
        "file": (io.BytesIO(b"perizia"), "perizia.pdf"), "claim_id": sid, "policy_id": pid,
    }, content_type="multipart/form-data")
    with app.app_context():
        percorso = os.path.join(app.config["UPLOAD_FOLDER"], Document.query.one().filename)
    assert os.path.exists(percorso)

    resp = client.post(f"/clienti/{cid}/elimina")
    assert resp.status_code == 302
    with app.app_context():
        from gestionale.models import Title

        assert db.session.get(Client, cid) is None
        assert Policy.query.count() == 0 and Title.query.count() == 0
        assert Claim.query.count() == 0 and ClaimNote.query.count() == 0
        assert Document.query.count() == 0
    assert not os.path.exists(percorso)
