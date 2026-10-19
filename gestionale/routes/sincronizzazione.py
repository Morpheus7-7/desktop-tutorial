"""Sincronizzazione tra due PC (solo amministratori): vedi gestionale/sincronizzazione.py."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from .. import sincronizzazione as sync
from ..models import AuditLog, db
from ..security import audit, require_admin

bp = Blueprint("sincronizzazione", __name__, url_prefix="/sincronizza")
bp.before_request(require_admin)


@bp.route("/")
def pagina():
    return render_template("sincronizzazione.html", s=sync.situazione())


@bp.route("/cartella", methods=["POST"])
def imposta_cartella():
    try:
        sync.imposta_cartella(request.form.get("cartella") or "")
    except sync.SincronizzazioneError as exc:
        flash(str(exc), "danger")
    else:
        flash("Cartella di sincronizzazione salvata.", "success")
    return redirect(url_for("sincronizzazione.pagina"))


@bp.route("/salva", methods=["POST"])
def salva():
    try:
        esito = sync.esporta(forza=request.form.get("forza") == "1")
    except sync.ConfermaNecessaria as exc:
        return render_template("sincronizzazione.html", s=sync.situazione(), conferma=("salva", str(exc))), 409
    except sync.SincronizzazioneError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("sincronizzazione.pagina"))
    audit("sincronizzazione", "sistema", None, f"Dati salvati per l'altro PC in {esito['percorso']}", commit=True)
    flash(f"Dati salvati in {esito['percorso']}. Sull'altro PC apri «Sincronizza» e premi «Carica dall'altro PC».",
          "success")
    return redirect(url_for("sincronizzazione.pagina"))


@bp.route("/carica", methods=["POST"])
def carica():
    username = g.user.username
    try:
        esito = sync.importa(forza=request.form.get("forza") == "1")
    except sync.ConfermaNecessaria as exc:
        db.session.rollback()
        return render_template("sincronizzazione.html", s=sync.situazione(), conferma=("carica", str(exc))), 409
    except sync.SincronizzazioneError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("sincronizzazione.pagina"))
    pacchetto = esito["pacchetto"]
    db.session.add(AuditLog(
        username=username, azione="sincronizzazione", entita="sistema", ip=request.remote_addr,
        descrizione=(f"Caricati i dati salvati da «{pacchetto.get('pc', 'altro PC')}» "
                     f"(copia di sicurezza: {esito['backup_sicurezza']})")[:500],
    ))
    db.session.commit()
    # Come ogni ripristino, il caricamento disconnette tutti gli utenti.
    g.user = None
    session.clear()
    flash(
        f"Dati dell'altro PC caricati ({pacchetto.get('clienti', 0)} clienti, {pacchetto.get('polizze', 0)} polizze). "
        f"Copia di sicurezza dei dati precedenti: {esito['backup_sicurezza']}. Accedi di nuovo.",
        "success",
    )
    return redirect(url_for("auth.login"))
