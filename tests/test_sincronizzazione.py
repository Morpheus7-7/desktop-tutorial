"""Sincronizzazione manuale tra due PC con una cartella condivisa (chiavetta, OneDrive…)."""
import zipfile

import pytest

from gestionale import sincronizzazione as sync
from gestionale.models import Client, db

from conftest import ADMIN_PASSWORD, ADMIN_USER, add_user, login, make_app


@pytest.fixture
def due_pc(tmp_path):
    """Due installazioni separate (fisso e portatile) e la cartella condivisa."""
    condivisa = tmp_path / "chiavetta"
    condivisa.mkdir()
    pc = []
    for nome in ("fisso", "portatile"):
        cartella = tmp_path / nome
        cartella.mkdir()
        app = make_app(cartella)
        add_user(app, ADMIN_USER, ADMIN_PASSWORD, ruolo="admin")
        c = app.test_client()
        login(c)
        pc.append((app, c))
    yield pc, str(condivisa)
    for app, _ in pc:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def _nuovo_cliente(c, nome):
    assert c.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": nome}).status_code == 302


def test_salva_su_un_pc_e_carica_sull_altro(due_pc):
    (fisso, cf), (portatile, cp) = due_pc[0]
    cartella = due_pc[1]
    for c in (cf, cp):
        assert c.post("/sincronizza/cartella", data={"cartella": cartella}).status_code == 302
    _nuovo_cliente(cf, "Cliente dal fisso")
    assert cf.post("/sincronizza/salva").status_code == 302
    with zipfile.ZipFile(f"{cartella}/{sync.NOME_PACCHETTO}") as zf:
        assert "gestionale.db" in zf.namelist()
    # Il portatile vede il pacchetto in dashboard e lo carica.
    assert "non ancora caricati su questo PC" in cp.get("/").get_data(as_text=True)
    risposta = cp.post("/sincronizza/carica")
    assert risposta.status_code == 302 and "/accesso" in risposta.headers["Location"]
    with portatile.app_context():
        assert Client.query.filter_by(ragione_sociale="Cliente dal fisso").count() == 1
    # Dopo il caricamento si accede di nuovo; il portatile è allineato.
    login(cp)
    assert "non ancora caricati" not in cp.get("/").get_data(as_text=True)
    assert "allineato" in cp.get("/sincronizza/").get_data(as_text=True)
    # Ora si lavora sul portatile e si torna al fisso.
    _nuovo_cliente(cp, "Cliente dal portatile")
    assert cp.post("/sincronizza/salva").status_code == 302
    assert cf.post("/sincronizza/carica").status_code == 302
    with fisso.app_context():
        assert {c.ragione_sociale for c in Client.query} == {"Cliente dal fisso", "Cliente dal portatile"}


def test_caricare_sopra_modifiche_locali_chiede_conferma(due_pc):
    (fisso, cf), (portatile, cp) = due_pc[0]
    cartella = due_pc[1]
    for c in (cf, cp):
        c.post("/sincronizza/cartella", data={"cartella": cartella})
    cf.post("/sincronizza/salva")
    cp.post("/sincronizza/carica")
    login(cp)
    _nuovo_cliente(cf, "Lavoro sul fisso")
    cf.post("/sincronizza/salva")
    # Intanto sul portatile si è lavorato senza sincronizzare.
    _nuovo_cliente(cp, "Lavoro sul portatile")
    risposta = cp.post("/sincronizza/carica")
    assert risposta.status_code == 409 and "Carica comunque" in risposta.get_data(as_text=True)
    with portatile.app_context():
        assert Client.query.filter_by(ragione_sociale="Lavoro sul portatile").count() == 1
    assert cp.post("/sincronizza/carica", data={"forza": "1"}).status_code == 302
    with portatile.app_context():
        assert Client.query.filter_by(ragione_sociale="Lavoro sul fisso").count() == 1


def test_salvare_sopra_un_pacchetto_non_caricato_chiede_conferma(due_pc):
    (fisso, cf), (portatile, cp) = due_pc[0]
    cartella = due_pc[1]
    for c in (cf, cp):
        c.post("/sincronizza/cartella", data={"cartella": cartella})
    cf.post("/sincronizza/salva")
    risposta = cp.post("/sincronizza/salva")
    assert risposta.status_code == 409 and "Salva comunque" in risposta.get_data(as_text=True)
    assert cp.post("/sincronizza/salva", data={"forza": "1"}).status_code == 302
    # Il pacchetto sovrascritto resta come copia.
    import os
    assert os.path.isfile(os.path.join(cartella, sync.NOME_PRECEDENTE))


def test_cartella_non_valida_e_niente_da_caricare(due_pc, tmp_path):
    (fisso, cf), _ = due_pc[0]
    risposta = cf.post("/sincronizza/cartella", data={"cartella": str(tmp_path / "non-esiste")}, follow_redirects=True)
    assert "non esiste" in risposta.get_data(as_text=True)
    cf.post("/sincronizza/cartella", data={"cartella": due_pc[1]})
    risposta = cf.post("/sincronizza/carica", follow_redirects=True)
    assert "nessun pacchetto" in risposta.get_data(as_text=True)


def test_riservata_agli_amministratori(app, client):
    add_user(app, "operatore", "password-oper-1", ruolo="operatore")
    c = app.test_client()
    login(c, "operatore", "password-oper-1")
    assert c.get("/sincronizza/").status_code == 403
    assert client.get("/sincronizza/").status_code == 200
