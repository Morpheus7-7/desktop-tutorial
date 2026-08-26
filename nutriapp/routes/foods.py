"""Database alimenti: consultazione, correzione, aggiunta di alimenti propri."""
from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import or_

from .. import forms
from ..models import Alimento, db
from ..nutrition import NUTRIENTI
from ..security import nutrizionista_required

bp = Blueprint("foods", __name__, url_prefix="/alimenti")

PER_PAGINA = 40


@bp.route("/")
@nutrizionista_required
def elenco():
    q = (request.args.get("q") or "").strip()
    categoria = request.args.get("categoria") or ""
    filtro = request.args.get("filtro") or ""
    pagina = forms.intero(request.args.get("pagina")) or 1

    query = Alimento.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Alimento.nome.ilike(like), Alimento.nome_it.ilike(like)))
    if categoria:
        query = query.filter(Alimento.categoria_it == categoria)
    if filtro == "da_verificare":
        query = query.filter(Alimento.da_verificare.is_(True))
    elif filtro == "senza_valori":
        query = query.filter(Alimento.kcal.is_(None))
    elif filtro == "miei":
        query = query.filter(Alimento.personalizzato.is_(True))
    elif filtro in ("vegan", "vegetariano", "senza_glutine", "senza_lattosio"):
        query = query.filter(getattr(Alimento, filtro).is_(True))

    pagina_risultati = query.order_by(Alimento.nome_it, Alimento.nome).paginate(
        page=max(1, pagina), per_page=PER_PAGINA, error_out=False
    )

    categorie = [
        c[0]
        for c in db.session.query(Alimento.categoria_it)
        .filter(Alimento.categoria_it.isnot(None))
        .distinct()
        .order_by(Alimento.categoria_it)
        .all()
    ]
    return render_template(
        "foods/list.html",
        pagina_risultati=pagina_risultati,
        q=q,
        categoria=categoria,
        filtro=filtro,
        categorie=categorie,
        da_verificare=Alimento.query.filter_by(da_verificare=True).count(),
        senza_valori=Alimento.query.filter(Alimento.kcal.is_(None)).count(),
        totale=Alimento.query.count(),
    )


def _leggi_form(alimento: Alimento) -> None:
    f = request.form
    alimento.nome = forms.testo(f.get("nome"), 250) or alimento.nome
    alimento.nome_it = forms.testo(f.get("nome_it"), 250)
    alimento.categoria_it = forms.testo(f.get("categoria_it"), 120)
    alimento.spesa_query = forms.testo(f.get("spesa_query"), 120)
    alimento.porzione_nome = forms.testo(f.get("porzione_nome"), 80)
    alimento.porzione_g = forms.numero(f.get("porzione_g")) or 100
    for nutriente in NUTRIENTI:
        setattr(alimento, nutriente.chiave, forms.numero(f.get(nutriente.chiave)))
    alimento.vegan = forms.tri_stato(f.get("vegan"))
    alimento.vegetariano = forms.tri_stato(f.get("vegetariano"))
    alimento.senza_glutine = forms.tri_stato(f.get("senza_glutine"))
    alimento.senza_lattosio = forms.tri_stato(f.get("senza_lattosio"))
    alimento.da_verificare = forms.flag(f.get("da_verificare"))


@bp.route("/nuovo", methods=["GET", "POST"])
@nutrizionista_required
def nuovo():
    if request.method == "POST":
        nome = forms.testo(request.form.get("nome_it")) or forms.testo(request.form.get("nome"))
        if not nome:
            flash("Serve almeno il nome dell'alimento.", "warning")
        else:
            alimento = Alimento(nome=nome, personalizzato=True, porzione_g=100)
            _leggi_form(alimento)
            if not alimento.nome_it:
                alimento.nome_it = nome
            db.session.add(alimento)
            db.session.commit()
            flash(f"«{alimento.etichetta}» aggiunto al database.", "success")
            return redirect(url_for("foods.dettaglio", alimento_id=alimento.id))

    return render_template("foods/form.html", alimento=None, nutrienti=NUTRIENTI)


@bp.route("/<int:alimento_id>", methods=["GET", "POST"])
@nutrizionista_required
def dettaglio(alimento_id: int):
    alimento = db.get_or_404(Alimento, alimento_id)
    if request.method == "POST":
        _leggi_form(alimento)
        db.session.commit()
        flash("Alimento aggiornato.", "success")
        return redirect(url_for("foods.dettaglio", alimento_id=alimento.id))
    return render_template("foods/form.html", alimento=alimento, nutrienti=NUTRIENTI)


@bp.route("/<int:alimento_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina(alimento_id: int):
    alimento = db.get_or_404(Alimento, alimento_id)
    if not alimento.personalizzato:
        # Gli alimenti USDA restano: sono la base condivisa di tutti i piani.
        flash("Gli alimenti della banca dati USDA non si eliminano: correggili se serve.", "warning")
        return redirect(url_for("foods.dettaglio", alimento_id=alimento.id))
    nome = alimento.etichetta
    db.session.delete(alimento)
    db.session.commit()
    flash(f"«{nome}» eliminato.", "info")
    return redirect(url_for("foods.elenco"))


@bp.route("/cerca.json")
@nutrizionista_required
def cerca_json():
    """Ricerca rapida per i campi di completamento del costruttore di piani."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])
    like = f"%{q}%"
    alimenti = (
        Alimento.query.filter(or_(Alimento.nome.ilike(like), Alimento.nome_it.ilike(like)))
        .order_by(Alimento.nome_it, Alimento.nome)
        .limit(25)
        .all()
    )
    return jsonify(
        [
            {
                "id": a.id,
                "nome": a.etichetta,
                "categoria": a.categoria_it,
                "porzione": a.porzione_etichetta,
                "kcal": round(a.kcal or 0),
            }
            for a in alimenti
        ]
    )
