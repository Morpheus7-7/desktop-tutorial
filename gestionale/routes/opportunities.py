"""Pipeline commerciale: opportunità di vendita (stile CRM assicurativo)."""
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..models import (
    ESITI_PREVENTIVO,
    ESITI_PREVENTIVO_LABELS,
    OPPORTUNITY_OPEN_STAGES,
    OPPORTUNITY_STAGES,
    POLICY_BRANCHES,
    Client,
    Opportunity,
    Preventivo,
    db,
)
from .documents import ALLOWED_EXTENSIONS, elimina_file, salva_file

bp = Blueprint("opportunities", __name__, url_prefix="/opportunita")

_CHIUSE = {"vinta", "persa"}


def _float_or_none(value):
    """Importi anche all'italiana: «1.250,50», «€ 900», «12%»."""
    from ..import_excel import _numero

    try:
        return _numero(value.strip() if isinstance(value, str) else value)
    except (ValueError, TypeError):
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
    # Il nastro segna la trattativa aperta ferma da più tempo: è quella da muovere.
    ferma = (
        Opportunity.query.filter(Opportunity.fase.in_(OPPORTUNITY_OPEN_STAGES))
        .order_by(Opportunity.updated_at.asc())
        .first()
    )
    giorni_ferma = (datetime.utcnow() - ferma.updated_at).days if ferma and ferma.updated_at else None
    return render_template(
        "opportunities/board.html",
        colonne=colonne,
        stages=OPPORTUNITY_STAGES,
        aperte=aperte,
        ferma=ferma,
        giorni_ferma=giorni_ferma,
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


# ----------------------------------------------------------------------
# Preventivi delle proposte
# ----------------------------------------------------------------------
def _data(valore):
    try:
        return date.fromisoformat(valore) if valore else None
    except ValueError:
        return None


def _torna(opp: Opportunity) -> str:
    dest = request.values.get("next") or ""
    if dest.startswith("/") and not dest.startswith("//") and "\\" not in dest:
        return dest
    return url_for("clients.detail", client_id=opp.client_id) + "#opportunita"


def _compila_preventivo(prev: Preventivo, form) -> None:
    prev.compagnia = (form.get("compagnia") or "").strip()[:120] or None
    prev.descrizione = (form.get("descrizione") or "").strip()[:200] or None
    prev.premio = _float_or_none(form.get("premio"))
    prev.data = _data(form.get("data")) or prev.data or date.today()
    prev.valido_fino = _data(form.get("valido_fino"))
    esito = form.get("esito", "in_attesa")
    prev.esito = esito if esito in ESITI_PREVENTIVO_LABELS else "in_attesa"
    prev.note = (form.get("note") or "").strip() or None


def _allega(prev: Preventivo, opp: Opportunity) -> bool:
    """Salva il file del preventivo tra i documenti del cliente. False se il
    tipo di file non è consentito."""
    file = request.files.get("file")
    if not file or not file.filename:
        return True
    nota = f"Preventivo per «{opp.titolo}»" + (f" · {prev.compagnia}" if prev.compagnia else "")
    doc = salva_file(file, opp.client_id, "preventivo", nota)
    if doc is None:
        return False
    if prev.documento is not None:
        elimina_file(prev.documento)  # sostituito dal nuovo file
    prev.documento = doc
    return True


@bp.route("/<int:opportunity_id>/preventivi/nuovo", methods=["GET", "POST"])
def new_quote(opportunity_id):
    opp = db.get_or_404(Opportunity, opportunity_id)
    prev = Preventivo(data=date.today())
    if request.method == "POST":
        _compila_preventivo(prev, request.form)
        if not (prev.compagnia or prev.premio is not None or request.files.get("file")):
            flash("Indica almeno la compagnia, il premio o il file del preventivo.", "danger")
        elif not _allega(prev, opp):
            flash("Tipo di file non consentito.", "danger")
        else:
            opp.preventivi.append(prev)
            if opp.fase in ("lead", "contatto"):
                _set_fase(opp, "preventivo")  # la proposta passa a «Preventivo inviato»
            if prev.premio is not None and opp.premio_stimato is None:
                opp.premio_stimato = prev.premio
            db.session.commit()
            flash("Preventivo salvato" + (" con il file tra i documenti del cliente." if prev.documento else "."), "success")
            return redirect(_torna(opp))
    return render_template("opportunities/preventivo.html", opp=opp, prev=prev, esiti=ESITI_PREVENTIVO,
                           estensioni=sorted(ALLOWED_EXTENSIONS), prossimo=_torna(opp))


@bp.route("/preventivi/<int:preventivo_id>/modifica", methods=["GET", "POST"])
def edit_quote(preventivo_id):
    prev = db.get_or_404(Preventivo, preventivo_id)
    opp = prev.opportunita
    if request.method == "POST":
        _compila_preventivo(prev, request.form)
        if not _allega(prev, opp):
            flash("Tipo di file non consentito.", "danger")
        else:
            db.session.commit()
            flash("Preventivo aggiornato.", "success")
            return redirect(_torna(opp))
    return render_template("opportunities/preventivo.html", opp=opp, prev=prev, esiti=ESITI_PREVENTIVO,
                           estensioni=sorted(ALLOWED_EXTENSIONS), prossimo=_torna(opp))


@bp.route("/preventivi/<int:preventivo_id>/elimina", methods=["POST"])
def delete_quote(preventivo_id):
    prev = db.get_or_404(Preventivo, preventivo_id)
    opp = prev.opportunita
    if prev.documento is not None and request.form.get("con_file"):
        elimina_file(prev.documento)
    db.session.delete(prev)
    db.session.commit()
    flash("Preventivo eliminato.", "success")
    return redirect(_torna(opp))
