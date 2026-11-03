"""Archivio documenti organizzato in cartelle."""
import io

from gestionale.models import Client, Document, db


def _cliente(app, tipo="privato", nome="Anna Russo"):
    with app.app_context():
        c = Client(tipo=tipo, ragione_sociale=nome)
        db.session.add(c)
        db.session.commit()
        return c.id


def _carica(client, cid, nome, **dati):
    return client.post(f"/documenti/carica/{cid}", data={"file": (io.BytesIO(b"%PDF-1.4"), nome), **dati},
                       content_type="multipart/form-data")


def test_documenti_nella_cartella_del_tipo(client, app):
    cid = _cliente(app)
    _carica(client, cid, "ci.pdf", categoria="carta_identita")
    _carica(client, cid, "patente.pdf", categoria="patente")
    _carica(client, cid, "polizza.pdf", categoria="polizza")
    with app.app_context():
        cartelle = {c["chiave"]: [d.original_name for d in c["documenti"]]
                    for c in db.session.get(Client, cid).cartelle_documenti}
    assert sorted(cartelle["personali"]) == ["ci.pdf", "patente.pdf"]
    assert cartelle["polizze"] == ["polizza.pdf"]
    # Un privato non ha la cartella «Documenti azienda», un'azienda sì.
    assert "azienda" not in cartelle
    with app.app_context():
        aid = _cliente(app, "azienda", "ACME S.r.l.")
        assert "azienda" in {c["chiave"] for c in db.session.get(Client, aid).cartelle_documenti}
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Documenti personali" in pagina and "Carica in «Documenti personali»" in pagina


def test_cartella_personale_e_spostamento(client, app):
    cid = _cliente(app)
    _carica(client, cid, "mutuo.pdf", categoria="altro", cartella="  Pratica   mutuo/2025 ")
    with app.app_context():
        doc = Document.query.one()
        assert doc.cartella == "Pratica mutuo 2025" and doc.cartella_nome == "Pratica mutuo 2025"
        did = doc.id
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Pratica mutuo 2025" in pagina
    # Spostato nella cartella del tipo «Visura camerale».
    assert client.post(f"/documenti/{did}/sposta", data={"categoria": "visura", "cartella": ""}).status_code == 302
    with app.app_context():
        doc = db.session.get(Document, did)
        assert (doc.categoria, doc.cartella, doc.cartella_chiave) == ("visura", None, "azienda")


def test_archivio_filtra_per_cartella(client, app):
    cid = _cliente(app)
    _carica(client, cid, "ci.pdf", categoria="carta_identita")
    _carica(client, cid, "foto.jpg", categoria="foto")
    _carica(client, cid, "nota.pdf", categoria="altro", cartella="Varie")
    pagina = client.get("/documenti/?cartella=personali").get_data(as_text=True)
    assert "ci.pdf" in pagina and "foto.jpg" not in pagina
    pagina = client.get("/documenti/?cartella=personale:Varie").get_data(as_text=True)
    assert "nota.pdf" in pagina and "ci.pdf" not in pagina
    assert "Cartelle create da voi" in client.get("/documenti/").get_data(as_text=True)


def test_vecchie_categorie_restano_valide(app):
    with app.app_context():
        for categoria, cartella in (("identita", "personali"), ("visura", "azienda"), ("sinistro", "sinistri"),
                                    ("privacy", "compliance"), ("sconosciuta", "altro")):
            assert Document(categoria=categoria).cartella_chiave == cartella
