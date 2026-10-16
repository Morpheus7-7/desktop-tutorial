"""Test della pagina Impostazioni: automatismi, limiti dei campi numerici,
download del backup senza copie in %TEMP% e indicazioni sui backup."""
import io
import os
import tempfile
import zipfile
from datetime import timedelta

from gestionale import backup, mailer
from gestionale.models import AuditLog, Notification, Settings, db, now


def _settings(app):
    with app.app_context():
        s = Settings.get()
        return {c: getattr(s, c) for c in (
            "rinnovo_tacito_automatico", "emissione_quietanze_automatica", "anticipo_quietanze_giorni",
            "scadenza_automatica", "tolleranza_scadenza_giorni", "smtp_port", "intervallo_minuti",
            "backup_conservati",
        )}


def test_pagina_mostra_automatismi_e_avviso_scheduler(client):
    pagina = client.get("/impostazioni/").get_data(as_text=True)
    assert 'id="tab-automatismi"' in pagina
    assert "Rinnovo tacito automatico" in pagina and "anniversario" in pagina
    assert "tolleranza" in pagina.lower()
    # Nei test lo scheduler non è avviato: la pagina lo segnala.
    assert "Controlli automatici non attivi" in pagina


def test_salva_automatismi_con_registro(client, app):
    resp = client.post("/impostazioni/automatismi", data={
        "rinnovo_tacito_automatico": "on", "anticipo_quietanze_giorni": "45",
        "tolleranza_scadenza_giorni": "10",
    }, follow_redirects=True)
    assert "Impostazioni degli automatismi salvate" in resp.get_data(as_text=True)
    valori = _settings(app)
    assert valori["rinnovo_tacito_automatico"] is True
    assert valori["emissione_quietanze_automatica"] is False
    assert valori["scadenza_automatica"] is False
    assert valori["anticipo_quietanze_giorni"] == 45 and valori["tolleranza_scadenza_giorni"] == 10
    with app.app_context():
        voce = AuditLog.query.filter(AuditLog.descrizione.like("Automatismi aggiornati%")).one()
        assert "Anticipo emissione quietanze: 30 giorni → 45 giorni" in voce.descrizione
        assert "Emissione automatica delle quietanze: attivo → disattivato" in voce.descrizione

    # Nessuna modifica: nessuna nuova voce nel registro.
    client.post("/impostazioni/automatismi", data={
        "rinnovo_tacito_automatico": "on", "anticipo_quietanze_giorni": "45",
        "tolleranza_scadenza_giorni": "10",
    })
    with app.app_context():
        assert AuditLog.query.filter(AuditLog.descrizione.like("Automatismi aggiornati%")).count() == 1


def test_automatismi_valori_fuori_limite_rifiutati(client, app):
    prima = _settings(app)
    for anticipo, tolleranza in (("121", "30"), ("30", "181"), ("-1", "30"), ("abc", "30"), ("30", "1e3")):
        resp = client.post("/impostazioni/automatismi", data={
            "anticipo_quietanze_giorni": anticipo, "tolleranza_scadenza_giorni": tolleranza,
        }, follow_redirects=True)
        assert "inserisci un numero intero tra" in resp.get_data(as_text=True)
    assert _settings(app) == prima
    # Campo vuoto: valore predefinito.
    client.post("/impostazioni/automatismi", data={
        "rinnovo_tacito_automatico": "on", "emissione_quietanze_automatica": "on", "scadenza_automatica": "on",
        "anticipo_quietanze_giorni": "", "tolleranza_scadenza_giorni": "0",
    })
    valori = _settings(app)
    assert valori["anticipo_quietanze_giorni"] == 30 and valori["tolleranza_scadenza_giorni"] == 0


def test_email_porta_e_intervallo_con_limiti(client, app):
    prima = _settings(app)
    for porta, intervallo in (("0", "30"), ("70000", "30"), ("587", "0"), ("587", "100000")):
        resp = client.post("/impostazioni/", data={
            "smtp_host": "smtp.test.it", "smtp_port": porta, "intervallo_minuti": intervallo,
        }, follow_redirects=True)
        assert "inserisci un numero intero tra" in resp.get_data(as_text=True)
    with app.app_context():
        assert Settings.get().smtp_host in (None, "")  # niente salvataggi parziali
    assert _settings(app) == prima
    client.post("/impostazioni/", data={"smtp_host": "smtp.test.it", "smtp_port": "465", "intervallo_minuti": "1440"})
    valori = _settings(app)
    assert valori["smtp_port"] == 465 and valori["intervallo_minuti"] == 1440


def test_backup_conservati_con_limiti(client, app):
    for valore in ("0", "366", "dieci"):
        client.post("/impostazioni/backup/opzioni", data={"backup_automatico": "on", "backup_conservati": valore})
    assert _settings(app)["backup_conservati"] == 14
    client.post("/impostazioni/backup/opzioni", data={"backup_automatico": "on", "backup_conservati": "7"})
    assert _settings(app)["backup_conservati"] == 7


def test_download_backup_senza_copie_in_temp(client, app, tmp_path, monkeypatch):
    systemp = tmp_path / "systemp"
    systemp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(systemp))

    def _vietato(*a, **k):  # il vecchio codice creava un file con nome in %TEMP%
        raise AssertionError("mkstemp non deve essere usato per il download")

    monkeypatch.setattr(tempfile, "mkstemp", _vietato)
    resp = client.post("/impostazioni/backup/scarica")
    assert resp.status_code == 200 and resp.mimetype == "application/zip"
    dati = resp.data
    resp.close()
    assert zipfile.is_zipfile(io.BytesIO(dati))
    assert os.listdir(systemp) == []
    # Nessun residuo di lavoro nella cartella dei backup.
    cartella = app.config["BACKUP_FOLDER"]
    residui = [n for n in os.listdir(cartella) if n.startswith(".")] if os.path.isdir(cartella) else []
    assert residui == []


def test_elenco_mostra_copie_pre_ripristino_e_data_futura(client, app):
    with app.app_context():
        backup.backup_automatico(forza=True)
        backup._salva_in_cartella(backup.PREFISSO_PRE_RIPRISTINO + backup.PREFISSO_FILE)
        s = Settings.get()
        s.ultimo_backup_at = now() + timedelta(days=200)
        db.session.commit()
    pagina = client.get("/impostazioni/").get_data(as_text=True)
    assert "copia pre-ripristino" in pagina
    assert "pre_ripristino_backup_gestionale_" in pagina
    assert "La data dell'ultimo backup è nel futuro" in pagina


def test_invia_ora_mentre_un_altro_invio_e_in_corso(client, app, monkeypatch):
    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: None)
    monkeypatch.setattr(mailer, "ATTESA_INVIO_S", 0.05)
    with app.app_context():
        s = Settings.get()
        s.email_attive, s.smtp_host, s.mail_to = True, "smtp.example.com", "a@example.com"
        db.session.add(Notification(tipo="info", livello="info", messaggio="X", dedup_key="lock1"))
        db.session.commit()
    assert mailer._invio_lock.acquire()  # invio in corso (es. scheduler)
    try:
        resp = client.post("/impostazioni/invia-ora", follow_redirects=True)
    finally:
        mailer._invio_lock.release()
    assert "già in corso un altro invio" in resp.get_data(as_text=True)
    with app.app_context():
        assert Notification.query.filter_by(inviata_email=True).count() == 0
