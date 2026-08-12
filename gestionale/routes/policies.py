"""Gestione polizze."""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import (
    PAYMENT_FREQUENCIES,
    POLICY_BRANCHES,
    POLICY_STATUSES,
    Client,
    Policy,
    db,
)

bp = Blueprint("policies", __name__, url_prefix="/polizze")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_float(value):
    try:
        return float(value.replace(",", ".")) if value not in (None, "") else None
    except (ValueError, AttributeError):
        return None


def _populate_from_form(policy: Policy, form) -> None:
    policy.compagnia = form.get("compagnia", "").strip()
    policy.numero_polizza = form.get("numero_polizza", "").strip()
    policy.ramo = form.get("ramo", "altro")
    policy.massimale = _parse_float(form.get("massimale"))
    policy.premio_annuo = _parse_float(form.get("premio_annuo"))
    policy.frazionamento = form.get("frazionamento", "annuale")
    policy.data_decorrenza = _parse_date(form.get("data_decorrenza"))
    policy.data_scadenza = _parse_date(form.get("data_scadenza"))
    policy.tacito_rinnovo = bool(form.get("tacito_rinnovo"))
    policy.stato = form.get("stato", "attiva")
    policy.note = form.get("note", "").strip() or None


@bp.route("/")
def list_policies():
    ramo = request.args.get("ramo", "")
    stato = request.args.get("stato", "")
    query = Policy.query
    if ramo:
        query = query.filter_by(ramo=ramo)
    if stato:
        query = query.filter_by(stato=stato)
    polizze = query.order_by(
        Policy.data_scadenza.is_(None), Policy.data_scadenza.asc()
    ).all()
    return render_template(
        "policies/list.html",
        polizze=polizze,
        ramo=ramo,
        stato=stato,
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
    )


@bp.route("/nuova/<int:client_id>", methods=["POST"])
def new_policy(client_id):
    client = db.get_or_404(Client, client_id)
    policy = Policy(client_id=client.id)
    _populate_from_form(policy, request.form)
    if not policy.compagnia or not policy.numero_polizza:
        flash("Compagnia e numero polizza sono obbligatori.", "danger")
    else:
        db.session.add(policy)
        db.session.commit()
        flash(f"Polizza {policy.numero_polizza} registrata.", "success")
    return redirect(url_for("clients.detail", client_id=client.id) + "#polizze")


@bp.route("/<int:policy_id>/modifica", methods=["GET", "POST"])
def edit_policy(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    if request.method == "POST":
        _populate_from_form(policy, request.form)
        if not policy.compagnia or not policy.numero_polizza:
            flash("Compagnia e numero polizza sono obbligatori.", "danger")
        else:
            db.session.commit()
            flash("Polizza aggiornata.", "success")
            return redirect(
                url_for("clients.detail", client_id=policy.client_id) + "#polizze"
            )
    return render_template(
        "policies/form.html",
        policy=policy,
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
    )


@bp.route("/<int:policy_id>/elimina", methods=["POST"])
def delete_policy(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    client_id = policy.client_id
    for doc in policy.documenti:
        doc.policy_id = None
    db.session.delete(policy)
    db.session.commit()
    flash("Polizza eliminata.", "success")
    return redirect(url_for("clients.detail", client_id=client_id) + "#polizze")
