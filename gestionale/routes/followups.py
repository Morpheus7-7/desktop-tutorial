"""Follow-up: attività da svolgere con scadenza (chiamate, rinnovi, preventivi…)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import (
    FOLLOWUP_PRIORITIES,
    FOLLOWUP_TYPES,
    Client,
    FollowUp,
    db,
    now,
)
from ..notifications import elimina_notifiche, segna_lette
from ..security import safe_next
from ..utils import leggi_data, paginate, parse_int

bp = Blueprint("followups", __name__, url_prefix="/follow-up")


@bp.route("/")
def list_followups():
    stato = request.args.get("stato", "aperto")
    query = FollowUp.query
    if stato in ("aperto", "completato", "annullato"):
        query = query.filter_by(stato=stato)
    pagination = paginate(query.order_by(FollowUp.data_scadenza.asc(), FollowUp.id.asc()))
    return render_template(
        "followups/list.html", pagination=pagination, followups=pagination.items, stato=stato
    )


@bp.route("/nuovo/<int:client_id>", methods=["POST"])
def new_followup(client_id):
    client = db.get_or_404(Client, client_id)
    titolo = (request.form.get("titolo") or "").strip()[:200]
    errori: list[str] = []
    scadenza = leggi_data(request.form, "data_scadenza", "Data del follow-up", errori, obbligatoria=True)
    if not titolo:
        errori.append("Il titolo del follow-up è obbligatorio.")
    if errori:
        for e in errori:
            flash(e, "danger")
        return redirect(
            safe_next(request.form.get("next")) or url_for("clients.detail", client_id=client.id) + "#followup"
        )
    tipo = request.form.get("tipo")
    priorita = request.form.get("priorita")
    policy_id = parse_int(request.form.get("policy_id"))
    fu = FollowUp(
        client_id=client.id,
        policy_id=policy_id if policy_id in [p.id for p in client.polizze] else None,
        tipo=tipo if tipo in dict(FOLLOWUP_TYPES) else "altro",
        titolo=titolo,
        descrizione=request.form.get("descrizione", "").strip() or None,
        data_scadenza=scadenza,
        priorita=priorita if priorita in dict(FOLLOWUP_PRIORITIES) else "media",
    )
    db.session.add(fu)
    db.session.commit()
    flash(f"Follow-up “{titolo}” pianificato per il {scadenza.strftime('%d/%m/%Y')}.", "success")
    return redirect(
        safe_next(request.form.get("next")) or url_for("clients.detail", client_id=client.id) + "#followup"
    )


@bp.route("/<int:followup_id>/completa", methods=["POST"])
def complete(followup_id):
    fu = db.get_or_404(FollowUp, followup_id)
    fu.stato = "completato"
    fu.completed_at = now()
    segna_lette(f"followup:{fu.id}:")
    db.session.commit()
    flash(f"Follow-up “{fu.titolo}” completato.", "success")
    return _back_to_origin(fu)


@bp.route("/<int:followup_id>/riapri", methods=["POST"])
def reopen(followup_id):
    fu = db.get_or_404(FollowUp, followup_id)
    fu.stato = "aperto"
    fu.completed_at = None
    # Le notifiche ripartono da zero (es. di nuovo «in ritardo»).
    elimina_notifiche(f"followup:{fu.id}:")
    db.session.commit()
    flash(f"Follow-up “{fu.titolo}” riaperto.", "info")
    return _back_to_origin(fu)


@bp.route("/<int:followup_id>/elimina", methods=["POST"])
def delete(followup_id):
    fu = db.get_or_404(FollowUp, followup_id)
    torna = _back_to_origin(fu)  # prima dell'eliminazione (serve il cliente)
    elimina_notifiche(f"followup:{fu.id}:")
    db.session.delete(fu)
    db.session.commit()
    flash("Follow-up eliminato.", "success")
    return torna


def _back_to_origin(fu: FollowUp):
    destinazione = safe_next(request.form.get("next"))
    if destinazione:
        return redirect(destinazione)
    if request.form.get("da_lista"):
        return redirect(url_for("followups.list_followups"))
    return redirect(url_for("clients.detail", client_id=fu.client_id) + "#followup")
