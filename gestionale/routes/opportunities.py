"""Pipeline commerciale: opportunità di vendita (stile CRM assicurativo)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import (
    FOLLOWUP_PRIORITIES,
    OPPORTUNITY_OPEN_STAGES,
    OPPORTUNITY_STAGES,
    POLICY_BRANCHES,
    Client,
    Opportunity,
    db,
    now,
)
from ..security import audit, safe_next
from ..utils import leggi_importo, parse_int

bp = Blueprint("opportunities", __name__, url_prefix="/opportunita")

_CHIUSE = {"vinta", "persa"}


def _apply_form(opp: Opportunity, form) -> list[str]:
    """Copia i campi del form nell'opportunità e restituisce gli errori."""
    errori: list[str] = []
    opp.titolo = (form.get("titolo") or "").strip()[:200]
    ramo = form.get("ramo") or None
    opp.ramo = ramo if ramo in dict(POLICY_BRANCHES) else None
    opp.premio_stimato = leggi_importo(form, "premio_stimato", "Premio stimato", errori, minimo=0)
    opp.provvigione_perc = leggi_importo(form, "provvigione_perc", "Provvigione %", errori, minimo=0, massimo=100)
    priorita = form.get("priorita")
    opp.priorita = priorita if priorita in dict(FOLLOWUP_PRIORITIES) else "media"
    opp.note = (form.get("note") or "").strip() or None
    nuova_fase = form.get("fase")
    if nuova_fase:
        _set_fase(opp, nuova_fase)
    if not opp.titolo:
        errori.append("Il titolo dell'opportunità è obbligatorio.")
    return errori


def _set_fase(opp: Opportunity, fase: str) -> None:
    valide = {f for f, _ in OPPORTUNITY_STAGES}
    if fase not in valide:
        return
    if fase in _CHIUSE:
        # La data di chiusura resta quella originale se la fase non cambia.
        if opp.fase != fase or opp.chiusa_at is None:
            opp.chiusa_at = now()
    else:
        opp.chiusa_at = None
    opp.fase = fase


def _render_form(opp, client, valori=None):
    clienti = None if client else Client.query.order_by(Client.ragione_sociale).all()
    return render_template(
        "opportunities/form.html",
        opp=opp, client=client, clienti=clienti, valori=valori,
        stages=OPPORTUNITY_STAGES, policy_branches=POLICY_BRANCHES, priorities=FOLLOWUP_PRIORITIES,
    )


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
    client = db.get_or_404(Client, client_id) if client_id else None
    if request.method == "POST":
        cid = client_id or parse_int(request.form.get("client_id"), minimo=1)
        if not cid:
            flash("Seleziona il cliente dell'opportunità.", "danger")
            return _render_form(None, None, request.form), 400
        cliente = db.get_or_404(Client, cid)
        opp = Opportunity(client_id=cliente.id, origine=(request.form.get("origine") or "manuale")[:40], fase="lead")
        errori = _apply_form(opp, request.form)
        if errori:
            for e in errori:
                flash(e, "danger")
            return _render_form(None, client, request.form), 400
        db.session.add(opp)
        db.session.flush()
        audit("crea", "opportunita", opp.id, f"Nuova opportunità «{opp.titolo}» per «{cliente.ragione_sociale}»")
        db.session.commit()
        flash(f"Opportunità «{opp.titolo}» creata.", "success")
        if client_id:
            return redirect(url_for("clients.detail", client_id=cliente.id) + "#opportunita")
        return redirect(url_for("opportunities.board"))
    return _render_form(None, client)


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
    dest = safe_next(request.form.get("next"))
    return redirect(dest or (url_for("clients.detail", client_id=client.id) + "#opportunita"))


@bp.route("/<int:opportunity_id>/fase", methods=["POST"])
def change_stage(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    _set_fase(opp, request.form.get("fase", ""))
    db.session.commit()
    return redirect(safe_next(request.form.get("next")) or url_for("opportunities.board"))


@bp.route("/<int:opportunity_id>/modifica", methods=["GET", "POST"])
def edit_opportunity(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    if request.method == "POST":
        with db.session.no_autoflush:
            errori = _apply_form(opp, request.form)
        if errori:
            db.session.rollback()
            for e in errori:
                flash(e, "danger")
            opp = db.session.get(Opportunity, opportunity_id)
            return _render_form(opp, opp.cliente, request.form), 400
        audit("modifica", "opportunita", opp.id, f"Modificata opportunità «{opp.titolo}» ({opp.fase_label})")
        db.session.commit()
        flash("Opportunità aggiornata.", "success")
        return redirect(url_for("opportunities.board"))
    return _render_form(opp, opp.cliente)


@bp.route("/<int:opportunity_id>/elimina", methods=["POST"])
def delete_opportunity(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    audit("elimina", "opportunita", opp.id, f"Eliminata opportunità «{opp.titolo}»")
    db.session.delete(opp)
    db.session.commit()
    flash("Opportunità eliminata.", "success")
    dest = safe_next(request.form.get("next"))
    return redirect(dest or url_for("opportunities.board"))
