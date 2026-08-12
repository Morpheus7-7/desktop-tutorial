"""Follow-up: attività da svolgere con scadenza (chiamate, rinnovi, preventivi…)."""
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import (
    FOLLOWUP_PRIORITIES,
    FOLLOWUP_TYPES,
    Client,
    FollowUp,
    db,
)

bp = Blueprint("followups", __name__, url_prefix="/follow-up")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
def list_followups():
    stato = request.args.get("stato", "aperto")
    query = FollowUp.query
    if stato in ("aperto", "completato", "annullato"):
        query = query.filter_by(stato=stato)
    followups = query.order_by(FollowUp.data_scadenza.asc()).all()
    return render_template("followups/list.html", followups=followups, stato=stato)


@bp.route("/nuovo/<int:client_id>", methods=["POST"])
def new_followup(client_id):
    client = db.get_or_404(Client, client_id)
    titolo = request.form.get("titolo", "").strip()
    scadenza = _parse_date(request.form.get("data_scadenza"))
    if not titolo or not scadenza:
        flash("Titolo e data del follow-up sono obbligatori.", "danger")
        return redirect(url_for("clients.detail", client_id=client.id) + "#followup")
    fu = FollowUp(
        client_id=client.id,
        tipo=request.form.get("tipo", "chiamata"),
        titolo=titolo,
        descrizione=request.form.get("descrizione", "").strip() or None,
        data_scadenza=scadenza,
        priorita=request.form.get("priorita", "media"),
    )
    db.session.add(fu)
    db.session.commit()
    flash(f"Follow-up “{titolo}” pianificato per il {scadenza.strftime('%d/%m/%Y')}.", "success")
    return redirect(url_for("clients.detail", client_id=client.id) + "#followup")


@bp.route("/<int:followup_id>/completa", methods=["POST"])
def complete(followup_id):
    fu = db.get_or_404(FollowUp, followup_id)
    fu.stato = "completato"
    fu.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Follow-up “{fu.titolo}” completato.", "success")
    return _back_to_origin(fu)


@bp.route("/<int:followup_id>/riapri", methods=["POST"])
def reopen(followup_id):
    fu = db.get_or_404(FollowUp, followup_id)
    fu.stato = "aperto"
    fu.completed_at = None
    db.session.commit()
    flash(f"Follow-up “{fu.titolo}” riaperto.", "info")
    return _back_to_origin(fu)


@bp.route("/<int:followup_id>/elimina", methods=["POST"])
def delete(followup_id):
    fu = db.get_or_404(FollowUp, followup_id)
    client_id = fu.client_id
    db.session.delete(fu)
    db.session.commit()
    flash("Follow-up eliminato.", "success")
    if request.form.get("da_lista"):
        return redirect(url_for("followups.list_followups"))
    return redirect(url_for("clients.detail", client_id=client_id) + "#followup")


def _back_to_origin(fu: FollowUp):
    if request.form.get("da_lista"):
        return redirect(url_for("followups.list_followups"))
    return redirect(url_for("clients.detail", client_id=fu.client_id) + "#followup")
