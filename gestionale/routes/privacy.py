"""PIN all'apertura, blocco per inattività, impostazioni privacy."""
from datetime import datetime, timedelta

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, session, url_for,
)

from .. import privacy
from ..models import Settings, db

bp = Blueprint("privacy", __name__)

LIBERI = {"privacy.unlock", "privacy.recover", "static", "settings.shutdown",
          "settings.in_use", "settings.open_anyway", "settings.show_window"}


def _pin_attivo() -> bool:
    return bool(Settings.get().pin_hash)


def _sicuro(dest: str | None) -> str:
    if dest and dest.startswith("/") and not dest.startswith("//") and "\\" not in dest:
        return dest
    return url_for("main.dashboard")


@bp.before_app_request
def richiedi_pin():
    """Con il PIN attivo ogni pagina richiede lo sblocco, che scade dopo
    i minuti di inattività scelti."""
    if request.endpoint in LIBERI or request.endpoint is None:
        return None
    s = Settings.get()
    if not s.pin_hash:
        return None
    adesso = datetime.utcnow().timestamp()
    ultima = session.get("dc_attivita")
    limite = max(1, s.blocco_minuti or 10) * 60
    # Finestra chiusa nella barra: alla riapertura si chiede di nuovo il PIN.
    nascosta_alle = current_app.config.get("DC_NASCOSTA_ALLE") or 0
    if (not session.get("dc_sbloccato") or ultima is None or adesso - ultima > limite
            or ultima < nascosta_alle):
        session.pop("dc_sbloccato", None)
        destinazione = request.full_path if request.method == "GET" else url_for("main.dashboard")
        return redirect(url_for("privacy.unlock", next=destinazione.rstrip("?")))
    session["dc_attivita"] = adesso
    return None


@bp.app_context_processor
def pin_nei_template():
    try:
        s = Settings.get()
        return {"dc_pin_minuti": (s.blocco_minuti or 10) if s.pin_hash else None}
    except Exception:  # noqa: BLE001 - per esempio prima che il database esista
        return {"dc_pin_minuti": None}


@bp.route("/sblocca", methods=["GET", "POST"])
def unlock():
    s = Settings.get()
    dest = _sicuro(request.values.get("next"))
    if not s.pin_hash:
        return redirect(dest)
    attesa = s.pin_attesa_fino and s.pin_attesa_fino > datetime.utcnow()
    if request.method == "POST" and not attesa:
        if privacy.verifica_segreto(request.form.get("pin", ""), s.pin_hash):
            s.pin_tentativi = 0
            s.pin_attesa_fino = None
            db.session.commit()
            session["dc_sbloccato"] = True
            session["dc_attivita"] = datetime.utcnow().timestamp()
            return redirect(dest)
        s.pin_tentativi = (s.pin_tentativi or 0) + 1
        if s.pin_tentativi >= privacy.TENTATIVI_MASSIMI:
            s.pin_tentativi = 0
            s.pin_attesa_fino = datetime.utcnow() + timedelta(seconds=privacy.ATTESA_SECONDI)
            attesa = True
        db.session.commit()
        if not attesa:
            flash("PIN errato.", "danger")
    secondi = int((s.pin_attesa_fino - datetime.utcnow()).total_seconds()) + 1 if attesa else 0
    return render_template("privacy/sblocca.html", dest=dest, secondi=secondi)


@bp.route("/sblocca/recupero", methods=["GET", "POST"])
def recover():
    s = Settings.get()
    if request.method == "POST":
        codice = privacy.normalizza_codice(request.form.get("codice", ""))
        if s.pin_recupero_hash and privacy.verifica_segreto(codice, s.pin_recupero_hash):
            s.pin_hash = s.pin_recupero_hash = None
            s.pin_tentativi = 0
            s.pin_attesa_fino = None
            db.session.commit()
            session["dc_sbloccato"] = True
            session["dc_attivita"] = datetime.utcnow().timestamp()
            flash("PIN rimosso con il codice di recupero. Impostane uno nuovo.", "warning")
            return redirect(url_for("privacy.settings"))
        flash("Codice di recupero non valido.", "danger")
    return render_template("privacy/recupero.html")


@bp.route("/blocca", methods=["POST"])
def lock_now():
    session.pop("dc_sbloccato", None)
    return redirect(url_for("privacy.unlock"))


@bp.route("/impostazioni/privacy", methods=["GET", "POST"])
def settings():
    s = Settings.get()
    codice_nuovo = None
    if request.method == "POST":
        azione = request.form.get("azione")
        if s.pin_hash and not privacy.verifica_segreto(request.form.get("pin_attuale", ""), s.pin_hash):
            flash("Il PIN attuale non è corretto.", "danger")
            return redirect(url_for("privacy.settings"))
        if azione == "imposta":
            pin, conferma = request.form.get("pin", ""), request.form.get("pin_conferma", "")
            errore = privacy.pin_valido(pin) or (None if pin == conferma else "I due PIN non coincidono.")
            if errore:
                flash(errore, "danger")
                return redirect(url_for("privacy.settings"))
            codice_nuovo = privacy.nuovo_codice_recupero()
            s.pin_hash = privacy.hash_segreto(pin)
            s.pin_recupero_hash = privacy.hash_segreto(codice_nuovo)
            session["dc_sbloccato"] = True
            session["dc_attivita"] = datetime.utcnow().timestamp()
        elif azione == "minuti":
            try:
                s.blocco_minuti = min(240, max(1, int(request.form.get("blocco_minuti", 10))))
            except ValueError:
                pass
            flash("Tempo di blocco aggiornato.", "success")
        elif azione == "rimuovi":
            s.pin_hash = s.pin_recupero_hash = None
            flash("PIN rimosso.", "success")
        db.session.commit()
        if not codice_nuovo:
            return redirect(url_for("privacy.settings"))
    return render_template(
        "privacy/impostazioni.html", s=s, codice_nuovo=codice_nuovo,
        cifratura=privacy.stato_cifratura(current_app.config.get("UPLOAD_FOLDER", ".")),
    )
