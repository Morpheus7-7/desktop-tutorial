"""Pipeline commerciale: opportunità di vendita (stile CRM assicurativo)."""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import (
    OPPORTUNITY_OPEN_STAGES,
    OPPORTUNITY_STAGES,
    POLICY_BRANCHES,
    Client,
    Opportunity,
    db,
)

bp = Blueprint("opportunities", __name__, url_prefix="/opportunita")

_CHIUSE = {"vinta", "persa"}


def _float_or_none(value):
    try:
        return float(value.replace(",", ".")) if value not in (None, "") else None
    except (ValueError, AttributeError):
        return None


def _apply_form(opp: Opportunity, form) -> None:
    opp.titolo = form.get("titolo", "").strip()
    opp.ramo = form.get("ramo") or None
    opp.premio_stimato = _float_or_none(form.get("premio_stimato"))
    opp.provvigione_perc = _float_or_none(form.get("provvigione_perc"))
    opp.priorita = form.get("priorita", "media")
    opp.note = form.get("note", "").strip() or None
    nuova_fase = form.get("fase")
    if nuova_fase:
        _set_fase(opp, nuova_fase)


def _set_fase(opp: Opportunity, fase: str) -> None:
    valide = {f for f, _ in OPPORTUNITY_STAGES}
    if fase not in valide:
        return
    opp.fase = fase
    opp.chiusa_at = datetime.utcnow() if fase in _CHIUSE else None


@bp.route("/")
def board():
    colonne = []
    for fase, label in OPPORTUNITY_STAGES:
        items = (
            Opportunity.query.filter_by(fase=fase)
            .order_by(Opportunity.updated_at.desc())
            .all()
        )
        colonne.append(
            {
                "fase": fase,
                "label": label,
                "opps": items,
                "valore": sum(o.premio_stimato or 0.0 for o in items),
            }
        )
    aperte = Opportunity.query.filter(Opportunity.fase.in_(OPPORTUNITY_OPEN_STAGES)).count()
    return render_template(
        "opportunities/board.html",
        colonne=colonne,
        stages=OPPORTUNITY_STAGES,
        aperte=aperte,
    )


@bp.route("/nuova", methods=["GET", "POST"])
@bp.route("/nuova/<int:client_id>", methods=["GET", "POST"])
def new_opportunity(client_id=None):
    if request.method == "POST":
        cid = client_id or request.form.get("client_id")
        client = db.get_or_404(Client, int(cid))
        opp = Opportunity(client_id=client.id, origine=request.form.get("origine", "manuale"))
        _apply_form(opp, request.form)
        if not opp.titolo:
            flash("Il titolo dell'opportunità è obbligatorio.", "danger")
        else:
            if not opp.fase:
                opp.fase = "lead"
            db.session.add(opp)
            db.session.commit()
            flash(f"Opportunità «{opp.titolo}» creata.", "success")
            if client_id:
                return redirect(url_for("clients.detail", client_id=client.id) + "#opportunita")
            return redirect(url_for("opportunities.board"))
    client = db.get_or_404(Client, client_id) if client_id else None
    clienti = None if client else Client.query.order_by(Client.ragione_sociale).all()
    return render_template(
        "opportunities/form.html",
        opp=None, client=client, clienti=clienti,
        stages=OPPORTUNITY_STAGES, policy_branches=POLICY_BRANCHES,
    )


@bp.route("/da-gap/<int:client_id>", methods=["POST"])
def from_gap(client_id):
    """Crea un'opportunità a partire da una copertura scoperta dell'analisi."""
    client = db.get_or_404(Client, client_id)
    ramo = request.form.get("ramo") or None
    titolo = request.form.get("titolo") or "Proposta copertura"
    opp = Opportunity(
        client_id=client.id,
        titolo=titolo,
        ramo=ramo,
        fase="lead",
        priorita="alta",
        origine="analisi_rischi",
        note=request.form.get("note") or None,
    )
    db.session.add(opp)
    db.session.commit()
    flash(f"Opportunità «{titolo}» aggiunta alla pipeline.", "success")
    dest = request.form.get("next")
    return redirect(dest or (url_for("clients.detail", client_id=client.id) + "#opportunita"))


@bp.route("/<int:opportunity_id>/fase", methods=["POST"])
def change_stage(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    _set_fase(opp, request.form.get("fase", ""))
    db.session.commit()
    return redirect(request.form.get("next") or url_for("opportunities.board"))


@bp.route("/<int:opportunity_id>/modifica", methods=["GET", "POST"])
def edit_opportunity(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    if request.method == "POST":
        _apply_form(opp, request.form)
        if not opp.titolo:
            flash("Il titolo dell'opportunità è obbligatorio.", "danger")
        else:
            db.session.commit()
            flash("Opportunità aggiornata.", "success")
            return redirect(url_for("opportunities.board"))
    return render_template(
        "opportunities/form.html",
        opp=opp, client=opp.cliente, clienti=None,
        stages=OPPORTUNITY_STAGES, policy_branches=POLICY_BRANCHES,
    )


@bp.route("/<int:opportunity_id>/elimina", methods=["POST"])
def delete_opportunity(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    client_id = opp.client_id
    db.session.delete(opp)
    db.session.commit()
    flash("Opportunità eliminata.", "success")
    dest = request.form.get("next")
    return redirect(dest or url_for("opportunities.board"))
