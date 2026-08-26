"""Area contenuti: articoli informativi per gli assistiti."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from .. import forms
from ..models import Articolo, CATEGORIE_ARTICOLO, db
from ..security import nutrizionista_required, utente_corrente

bp = Blueprint("blog", __name__, url_prefix="/articoli")


@bp.route("/")
@nutrizionista_required
def elenco():
    q = (request.args.get("q") or "").strip()
    stato = request.args.get("stato", "")
    query = Articolo.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Articolo.titolo.ilike(like), Articolo.sommario.ilike(like)))
    if stato == "pubblicati":
        query = query.filter_by(pubblicato=True)
    elif stato == "bozze":
        query = query.filter_by(pubblicato=False)

    articoli = query.order_by(
        Articolo.pubblicato.desc(), Articolo.data_pubblicazione.desc(), Articolo.created_at.desc()
    ).all()
    return render_template(
        "blog/list.html", articoli=articoli, q=q, stato=stato, categorie=CATEGORIE_ARTICOLO
    )


def _leggi_form(articolo: Articolo) -> None:
    f = request.form
    articolo.titolo = forms.testo(f.get("titolo"), 200) or articolo.titolo
    articolo.sommario = forms.testo(f.get("sommario"))
    articolo.corpo = forms.testo(f.get("corpo"))
    articolo.categoria = forms.testo(f.get("categoria"), 60)
    articolo.tags = forms.testo(f.get("tags"), 250)
    articolo.autore = forms.testo(f.get("autore"), 120) or (utente_corrente().nome)
    era_pubblicato = articolo.pubblicato
    articolo.pubblicato = forms.flag(f.get("pubblicato"))
    if articolo.pubblicato and not era_pubblicato:
        articolo.data_pubblicazione = forms.data(f.get("data_pubblicazione")) or date.today()
    elif articolo.pubblicato:
        articolo.data_pubblicazione = (
            forms.data(f.get("data_pubblicazione")) or articolo.data_pubblicazione or date.today()
        )
    articolo.assegna_slug()
    articolo.calcola_tempo_lettura()


@bp.route("/nuovo", methods=["GET", "POST"])
@nutrizionista_required
def nuovo():
    if request.method == "POST":
        titolo = forms.testo(request.form.get("titolo"), 200)
        if not titolo:
            flash("Serve il titolo dell'articolo.", "warning")
        else:
            articolo = Articolo(titolo=titolo)
            _leggi_form(articolo)
            db.session.add(articolo)
            db.session.commit()
            flash("Articolo salvato.", "success")
            return redirect(url_for("blog.dettaglio", articolo_id=articolo.id))

    return render_template(
        "blog/form.html", articolo=None, categorie=CATEGORIE_ARTICOLO, oggi=date.today()
    )


@bp.route("/<int:articolo_id>", methods=["GET", "POST"])
@nutrizionista_required
def dettaglio(articolo_id: int):
    articolo = db.get_or_404(Articolo, articolo_id)
    if request.method == "POST":
        _leggi_form(articolo)
        db.session.commit()
        flash("Articolo aggiornato.", "success")
        return redirect(url_for("blog.dettaglio", articolo_id=articolo.id))
    return render_template(
        "blog/form.html", articolo=articolo, categorie=CATEGORIE_ARTICOLO, oggi=date.today()
    )


@bp.route("/<int:articolo_id>/pubblica", methods=["POST"])
@nutrizionista_required
def pubblica(articolo_id: int):
    articolo = db.get_or_404(Articolo, articolo_id)
    articolo.pubblicato = not articolo.pubblicato
    if articolo.pubblicato and not articolo.data_pubblicazione:
        articolo.data_pubblicazione = date.today()
    db.session.commit()
    flash(
        "Articolo pubblicato: è visibile nell'area dei clienti."
        if articolo.pubblicato
        else "Articolo riportato in bozza.",
        "success",
    )
    return redirect(url_for("blog.elenco"))


@bp.route("/<int:articolo_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina(articolo_id: int):
    articolo = db.get_or_404(Articolo, articolo_id)
    titolo = articolo.titolo
    db.session.delete(articolo)
    db.session.commit()
    flash(f"Articolo «{titolo}» eliminato.", "info")
    return redirect(url_for("blog.elenco"))
