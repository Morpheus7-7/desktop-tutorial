"""Accademia commerciale: percorso formativo, quiz, obiezioni, scenari e schede."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import academy as ac
from ..models import AcademyProgress, Client, QuizAttempt, db

bp = Blueprint("academy", __name__, url_prefix="/accademia")


def _completate() -> set[str]:
    return {p.lezione_id for p in AcademyProgress.query.all()}


def _migliori_quiz() -> dict[str, QuizAttempt]:
    migliori: dict[str, QuizAttempt] = {}
    for t in QuizAttempt.query.order_by(QuizAttempt.created_at).all():
        if t.modulo_id not in migliori or t.percentuale > migliori[t.modulo_id].percentuale:
            migliori[t.modulo_id] = t
    return migliori


def _modulo_or_404(modulo_id: str) -> dict:
    modulo = ac.get_modulo(modulo_id)
    if modulo is None:
        abort(404)
    return modulo


@bp.route("/")
def index():
    completate = _completate()
    migliori = _migliori_quiz()
    moduli = []
    for m in ac.MODULI:
        fatte = sum(1 for lez in m["lezioni"] if lez["id"] in completate)
        moduli.append({"m": m, "fatte": fatte, "totale": len(m["lezioni"]), "quiz": migliori.get(m["id"])})
    totale_lezioni = len(ac.tutte_le_lezioni())
    # Prossima lezione da studiare: la prima non completata nel percorso.
    prossima = next(((m, lez) for m, lez in ac.tutte_le_lezioni() if lez["id"] not in completate), None)
    return render_template(
        "academy/index.html",
        moduli=moduli,
        completate=len(completate & ac.lezione_ids()),
        totale_lezioni=totale_lezioni,
        quiz_superati=sum(1 for t in migliori.values() if t.percentuale >= 70),
        prossima=prossima,
        pillola=ac.pillola_del_giorno(),
        categorie=ac.CATEGORIE_OBIEZIONI_LABELS,
    )


@bp.route("/modulo/<modulo_id>")
def module(modulo_id):
    modulo = _modulo_or_404(modulo_id)
    idx = ac.MODULI.index(modulo)
    return render_template(
        "academy/module.html",
        modulo=modulo,
        completate=_completate(),
        miglior_quiz=_migliori_quiz().get(modulo_id),
        precedente=ac.MODULI[idx - 1] if idx > 0 else None,
        successivo=ac.MODULI[idx + 1] if idx + 1 < len(ac.MODULI) else None,
        tecniche=[t for t in ac.TECNICHE if t["modulo"] == modulo_id],
        schede=[s for s in ac.SCHEDE if s["modulo"] == modulo_id],
        livelli=ac.LIVELLI_EVIDENZA,
    )


@bp.route("/lezione/<lezione_id>/completa", methods=["POST"])
def toggle_lesson(lezione_id):
    if lezione_id not in ac.lezione_ids():
        abort(404)
    esistente = AcademyProgress.query.filter_by(lezione_id=lezione_id).first()
    if esistente:
        db.session.delete(esistente)
    else:
        db.session.add(AcademyProgress(lezione_id=lezione_id))
    db.session.commit()
    modulo_id = next(m["id"] for m, lez in ac.tutte_le_lezioni() if lez["id"] == lezione_id)
    return redirect(url_for("academy.module", modulo_id=modulo_id) + f"#{lezione_id}")


@bp.route("/modulo/<modulo_id>/quiz", methods=["GET", "POST"])
def quiz(modulo_id):
    modulo = _modulo_or_404(modulo_id)
    esito = None
    if request.method == "POST":
        esito = ac.valuta_quiz(modulo, request.form)
        db.session.add(QuizAttempt(modulo_id=modulo_id, punteggio=esito["punteggio"], totale=esito["totale"]))
        db.session.commit()
        flash(f"Quiz completato: {esito['punteggio']} risposte corrette su {esito['totale']}.",
              "success" if esito["punteggio"] * 10 >= esito["totale"] * 7 else "warning")
    tentativi = (
        QuizAttempt.query.filter_by(modulo_id=modulo_id)
        .order_by(QuizAttempt.created_at.desc()).limit(5).all()
    )
    return render_template("academy/quiz.html", modulo=modulo, esito=esito, tentativi=tentativi)


@bp.route("/obiezioni")
def objections():
    q = request.args.get("q", "")
    categoria = request.args.get("categoria", "")
    return render_template(
        "academy/objections.html",
        obiezioni=ac.cerca_obiezioni(q, categoria),
        q=q, categoria=categoria,
        categorie=ac.CATEGORIE_OBIEZIONI,
        categorie_labels=ac.CATEGORIE_OBIEZIONI_LABELS,
    )


@bp.route("/allenamento")
def drill():
    obiezione = ac.get_obiezione(request.args.get("id", "")) or ac.obiezione_casuale(request.args.get("dopo"))
    return render_template(
        "academy/drill.html",
        o=obiezione,
        categorie_labels=ac.CATEGORIE_OBIEZIONI_LABELS,
    )


@bp.route("/tecniche")
def techniques():
    fasi = []
    for t in ac.TECNICHE:
        if t["fase"] not in fasi:
            fasi.append(t["fase"])
    return render_template(
        "academy/techniques.html",
        tecniche=ac.TECNICHE, fasi=fasi,
        moduli={m["id"]: m for m in ac.MODULI},
    )


@bp.route("/scenari")
def scenarios():
    return render_template("academy/scenarios.html", scenari=ac.SCENARI)


@bp.route("/scenari/<scenario_id>")
def scenario(scenario_id):
    s = ac.get_scenario(scenario_id)
    if s is None:
        abort(404)
    return render_template(
        "academy/scenario.html",
        s=s,
        obiezioni=[ac.get_obiezione(oid) for oid in s["obiezioni"]],
    )


@bp.route("/schede")
def sheets():
    return render_template(
        "academy/sheets.html",
        schede=ac.SCHEDE,
        moduli={m["id"]: m for m in ac.MODULI},
    )


@bp.route("/schede/<scheda_id>")
def sheet(scheda_id):
    scheda = ac.get_scheda(scheda_id)
    if scheda is None:
        abort(404)
    cliente = None
    cid = request.args.get("cliente", type=int)
    if cid:
        cliente = db.session.get(Client, cid)
    return render_template("academy/sheet.html", scheda=scheda, cliente=cliente)
