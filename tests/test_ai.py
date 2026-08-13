"""Test dell'analisi assistita da AI (SDK Anthropic simulato, nessuna rete)."""
import json
import os
import sys
import tempfile
import types

import pytest

from gestionale import create_app
from gestionale import ai_analysis
from gestionale.models import Client, RiskAnalysis, Settings, db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    upload_dir = tempfile.mkdtemp()
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": upload_dir,
            "SECRET_KEY": "test",
        }
    )
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "AI_MODELLO", "AI_ATTIVA"):
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------- configurazione
def test_ai_config_env_override(app, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    monkeypatch.setenv("AI_MODELLO", "claude-sonnet-5")
    monkeypatch.setenv("AI_ATTIVA", "true")
    with app.app_context():
        cfg = ai_analysis.ai_config()
        assert cfg["api_key"] == "sk-env"
        assert cfg["modello"] == "claude-sonnet-5"
        assert cfg["attiva"] is True


def test_ai_non_disponibile_senza_chiave(app):
    with app.app_context():
        s = Settings.get()
        s.ai_attiva = True
        db.session.commit()
        # SDK assente in ambiente di test e nessuna chiave -> non disponibile
        assert ai_analysis.ai_disponibile() is False


# --------------------------------------------------------------- SDK simulato
def _fake_anthropic(catch, payload):
    """Crea un finto modulo anthropic la cui risposta contiene `payload` (dict)."""
    mod = types.ModuleType("anthropic")

    class _Block:
        type = "text"
        text = json.dumps(payload, ensure_ascii=False)

    class _Resp:
        stop_reason = "end_turn"
        content = [_Block()]

    class _Messages:
        def create(self, **kwargs):
            catch.update(kwargs)
            return _Resp()

    class _Client:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    mod.Anthropic = _Client
    return mod


def test_analizza_cliente_ai_parsing(app, monkeypatch):
    catch = {}
    payload = {
        "riepilogo": "Attività con rischi cyber e incendio.",
        "rischi": [
            {"nome": "Cyber", "descrizione": "Vendite online",
             "severita": "alta", "coperture": ["Cyber Risk"],
             "spunto_trattativa": "Un titolare pensava non capitasse..."},
        ],
    }
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic(catch, payload))
    with app.app_context():
        s = Settings.get()
        s.ai_attiva = True
        s.anthropic_api_key = "sk-test"
        s.ai_modello = "claude-opus-5"
        db.session.commit()
        c = Client(tipo="azienda", ragione_sociale="ACME",
                   descrizione_attivita="e-commerce con magazzino")
        db.session.add(c)
        db.session.commit()

        res = ai_analysis.analizza_cliente_ai(c, c.descrizione_attivita)
        assert res["fonte"] == "ai"
        assert res["modello"] == "claude-opus-5"
        assert res["sintesi"]["rischi_rilevati"] == 1
        assert res["rischi"][0]["nome"] == "Cyber"
        # Il modello richiesto è quello configurato
        assert catch["model"] == "claude-opus-5"


def test_analizza_solleva_se_disattivata(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="X", descrizione_attivita="y")
        db.session.add(c)
        db.session.commit()
        with pytest.raises(RuntimeError):
            ai_analysis.analizza_cliente_ai(c, "y")  # ai_attiva=False di default


# --------------------------------------------------------------- route + storico
def test_route_ai_salva_analisi(client, app, monkeypatch):
    # Sostituiamo l'intera funzione: la route deve salvare fonte='ai'.
    def fake_analizza(cliente, testo, settings=None):
        return {
            "fonte": "ai", "modello": "claude-opus-5",
            "riepilogo": "ok", "rischi": [{"nome": "R", "descrizione": "d",
             "severita": "media", "coperture": ["C"], "spunto_trattativa": "s"}],
            "sintesi": {"rischi_rilevati": 1},
        }
    monkeypatch.setattr(ai_analysis, "analizza_cliente_ai", fake_analizza)

    client.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "AI Srl",
                "descrizione_attivita": "attività di test", "analizza_subito": ""},
                follow_redirects=True)
    with app.app_context():
        cid = Client.query.filter_by(ragione_sociale="AI Srl").first().id

    resp = client.post(f"/clienti/{cid}/analisi-ai",
                       data={"descrizione": "attività di test"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        a = RiskAnalysis.query.filter_by(client_id=cid, fonte="ai").first()
        assert a is not None
        assert a.is_ai is True
    # Il report AI si apre correttamente
    with app.app_context():
        aid = RiskAnalysis.query.filter_by(client_id=cid).first().id
    assert client.get(f"/clienti/{cid}/analisi/{aid}").status_code == 200


def test_route_ai_gestisce_errore(client, app, monkeypatch):
    def boom(cliente, testo, settings=None):
        raise RuntimeError("Chiave API mancante")
    monkeypatch.setattr(ai_analysis, "analizza_cliente_ai", boom)

    client.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Err Srl",
                "descrizione_attivita": "x", "analizza_subito": ""}, follow_redirects=True)
    with app.app_context():
        cid = Client.query.filter_by(ragione_sociale="Err Srl").first().id
    resp = client.post(f"/clienti/{cid}/analisi-ai",
                       data={"descrizione": "x"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Chiave API mancante".encode() in resp.data
    with app.app_context():
        assert RiskAnalysis.query.filter_by(client_id=cid).count() == 0


# --------------------------------------------------------------- impostazioni
def test_settings_salva_ai(client, app):
    client.post("/impostazioni/", data={
        "smtp_host": "", "smtp_port": "587", "smtp_security": "tls",
        "mail_to": "", "intervallo_minuti": "30",
        "ai_attiva": "on", "anthropic_api_key": "sk-abc", "ai_modello": "claude-sonnet-5",
    }, follow_redirects=True)
    with app.app_context():
        s = Settings.get()
        assert s.ai_attiva is True
        assert s.anthropic_api_key == "sk-abc"
        assert s.ai_modello == "claude-sonnet-5"

    # Chiave vuota non cancella quella salvata
    client.post("/impostazioni/", data={
        "smtp_port": "587", "smtp_security": "tls", "intervallo_minuti": "30",
        "ai_attiva": "on", "anthropic_api_key": "", "ai_modello": "claude-sonnet-5",
    }, follow_redirects=True)
    with app.app_context():
        assert Settings.get().anthropic_api_key == "sk-abc"
