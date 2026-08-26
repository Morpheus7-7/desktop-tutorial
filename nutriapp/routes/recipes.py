"""Ricettario: ricette con ingredienti collegati agli alimenti, quindi con i valori
nutrizionali calcolati e non scritti a mano."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from .. import forms
from ..models import Alimento, CATEGORIE_RICETTA, IngredienteRicetta, Ricetta, db
from ..nutrition import nutrienti_ricetta
from ..security import nutrizionista_required

bp = Blueprint("recipes", __name__, url_prefix="/ricette")


@bp.route("/")
@nutrizionista_required
def elenco():
    q = (request.args.get("q") or "").strip()
    categoria = request.args.get("categoria") or ""
    query = Ricetta.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Ricetta.titolo.ilike(like), Ricetta.tags.ilike(like)))
    if categoria:
        query = query.filter_by(categoria=categoria)
    ricette = query.order_by(Ricetta.titolo).all()

    schede = []
    for ricetta in ricette:
        _, per_porzione = nutrienti_ricetta(ricetta)
        schede.append({"ricetta": ricetta, "per_porzione": per_porzione})

    return render_template(
        "recipes/list.html",
        schede=schede,
        q=q,
        categoria=categoria,
        categorie=CATEGORIE_RICETTA,
    )


def _leggi_form(ricetta: Ricetta) -> None:
    f = request.form
    ricetta.titolo = forms.testo(f.get("titolo"), 200) or ricetta.titolo
    ricetta.categoria = forms.testo(f.get("categoria"), 60)
    ricetta.descrizione = forms.testo(f.get("descrizione"))
    ricetta.procedimento = forms.testo(f.get("procedimento"))
    ricetta.tempo_minuti = forms.intero(f.get("tempo_minuti"))
    ricetta.porzioni = forms.intero(f.get("porzioni")) or 1
    ricetta.tags = forms.testo(f.get("tags"), 250)
    ricetta.pubblicata = forms.flag(f.get("pubblicata"))
    ricetta.assegna_slug()


@bp.route("/nuova", methods=["GET", "POST"])
@nutrizionista_required
def nuova():
    if request.method == "POST":
        titolo = forms.testo(request.form.get("titolo"), 200)
        if not titolo:
            flash("Serve il titolo della ricetta.", "warning")
        else:
            ricetta = Ricetta(titolo=titolo)
            _leggi_form(ricetta)
            db.session.add(ricetta)
            db.session.commit()
            flash("Ricetta creata: ora aggiungi gli ingredienti.", "success")
            return redirect(url_for("recipes.dettaglio", ricetta_id=ricetta.id))

    return render_template(
        "recipes/form.html", ricetta=None, categorie=CATEGORIE_RICETTA, alimenti=[]
    )


@bp.route("/<int:ricetta_id>", methods=["GET", "POST"])
@nutrizionista_required
def dettaglio(ricetta_id: int):
    ricetta = db.get_or_404(Ricetta, ricetta_id)
    if request.method == "POST":
        _leggi_form(ricetta)
        db.session.commit()
        flash("Ricetta aggiornata.", "success")
        return redirect(url_for("recipes.dettaglio", ricetta_id=ricetta.id))

    totale, per_porzione = nutrienti_ricetta(ricetta)
    return render_template(
        "recipes/form.html",
        ricetta=ricetta,
        categorie=CATEGORIE_RICETTA,
        alimenti=Alimento.query.order_by(Alimento.nome_it, Alimento.nome).all(),
        totale=totale,
        per_porzione=per_porzione,
    )


@bp.route("/<int:ricetta_id>/ingredienti", methods=["POST"])
@nutrizionista_required
def aggiungi_ingrediente(ricetta_id: int):
    ricetta = db.get_or_404(Ricetta, ricetta_id)
    alimento_id = forms.intero(request.form.get("alimento_id"))
    testo = forms.testo(request.form.get("testo"), 200)
    grammi = forms.numero(request.form.get("grammi"))

    if not alimento_id and not testo:
        flash("Scegli un alimento oppure scrivi l'ingrediente.", "warning")
    else:
        ordine = max([i.ordine for i in ricetta.ingredienti], default=-1) + 1
        db.session.add(
            IngredienteRicetta(
                ricetta_id=ricetta.id,
                alimento_id=alimento_id,
                testo=testo if not alimento_id else None,
                grammi=grammi or 0,
                ordine=ordine,
            )
        )
        db.session.commit()
    return redirect(url_for("recipes.dettaglio", ricetta_id=ricetta.id) + "#ingredienti")


@bp.route("/<int:ricetta_id>/ingredienti/<int:ingrediente_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina_ingrediente(ricetta_id: int, ingrediente_id: int):
    ingrediente = db.get_or_404(IngredienteRicetta, ingrediente_id)
    if ingrediente.ricetta_id == ricetta_id:
        db.session.delete(ingrediente)
        db.session.commit()
    return redirect(url_for("recipes.dettaglio", ricetta_id=ricetta_id) + "#ingredienti")


@bp.route("/<int:ricetta_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina(ricetta_id: int):
    ricetta = db.get_or_404(Ricetta, ricetta_id)
    titolo = ricetta.titolo
    db.session.delete(ricetta)
    db.session.commit()
    flash(f"Ricetta «{titolo}» eliminata.", "info")
    return redirect(url_for("recipes.elenco"))
