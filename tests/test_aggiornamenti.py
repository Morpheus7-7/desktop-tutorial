"""Controllo e installazione degli aggiornamenti (GitHub Releases)."""
import hashlib
import os
import tempfile

import pytest

from gestionale import __version__, create_app
from gestionale import aggiornamenti as ag
from gestionale.routes import settings as rs

INSTALLATORE = b"MZ finto installatore"
IMPRONTA = hashlib.sha256(INSTALLATORE).hexdigest()


def _release(tag="v99.0.0", con_impronta=True):
    asset = [{"name": ag.NOME_INSTALLATORE, "browser_download_url": "https://example.test/setup.exe"}]
    if con_impronta:
        asset.append({"name": ag.NOME_IMPRONTA, "browser_download_url": "https://example.test/setup.exe.sha256"})
    return {"tag_name": tag, "html_url": "https://example.test/release", "body": "Novità", "assets": asset}


def test_confronto_versioni():
    assert ag.piu_recente("v2.1.1", "2.1.0")
    assert ag.piu_recente("v2.10.0", "2.9.9")
    assert not ag.piu_recente("v2.1", "2.1.0")
    assert not ag.piu_recente("v2.0.9", "2.1.0")
    assert ag.versione_tupla("v3.0.0-beta1") == (3, 0, 0)


def test_leggi_release():
    info = ag.leggi_release(_release(), "2.1.0")
    assert info["versione"] == "99.0.0" and info["installatore"] and info["impronta"]
    assert ag.leggi_release(_release("v1.0.0"), "2.1.0") is None
    assert ag.leggi_release({**_release(), "prerelease": True}, "2.1.0") is None
    # Senza impronta SHA-256 non si offre l'installazione automatica.
    senza = ag.leggi_release(_release(con_impronta=False), "2.1.0")
    assert senza["installatore"] is None and senza["pagina"]


def test_scarica_e_verifica(monkeypatch, tmp_path):
    file = {"https://example.test/setup.exe": INSTALLATORE,
            "https://example.test/setup.exe.sha256": f"{IMPRONTA}  Installa-DealCombined.exe\n".encode()}
    monkeypatch.setattr(ag, "_scarica", lambda url, timeout, limite: file[url])
    info = ag.leggi_release(_release(), "2.1.0")
    percorso = ag.scarica_e_verifica(info, tmp_path)
    assert percorso.read_bytes() == INSTALLATORE

    file["https://example.test/setup.exe"] = b"installatore manomesso"
    with pytest.raises(ag.AggiornamentoNonValido):
        ag.scarica_e_verifica(info, tmp_path)
    file["https://example.test/setup.exe.sha256"] = b"non un hash"
    with pytest.raises(ag.AggiornamentoNonValido):
        ag.scarica_e_verifica(info, tmp_path)


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


def test_pagina_e_avviso_nella_barra(app, monkeypatch):
    client = app.test_client()
    r = client.get("/impostazioni/aggiornamenti")
    assert r.status_code == 200 and __version__ in r.get_data(as_text=True)

    monkeypatch.setattr(ag, "controlla", lambda versione: ag.leggi_release(_release(), versione))
    client.post("/impostazioni/aggiornamenti", data={"azione": "controlla"})
    assert app.config["DC_AGGIORNAMENTO"]["versione"] == "99.0.0"
    pagina = client.get("/").get_data(as_text=True)
    assert "Disponibile la versione 99.0.0" in pagina
    # Fuori dal programma installato su Windows non si installa nulla.
    assert client.post("/impostazioni/aggiornamenti/installa").status_code == 404


def test_errore_di_rete_non_blocca(app, monkeypatch):
    def offline(versione):
        raise OSError("rete assente")

    monkeypatch.setattr(ag, "controlla", offline)
    rs.controlla_aggiornamenti(app)
    assert app.config["DC_AGGIORNAMENTO_ERRORE"] == "rete assente"
    assert app.test_client().get("/impostazioni/aggiornamenti").status_code == 200
