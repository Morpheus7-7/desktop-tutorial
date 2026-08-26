"""Lista della spesa del piano e collegamenti ai carrelli online."""
from __future__ import annotations

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for


from ..mailer import invia_lista_spesa
from ..models import GIORNI, Piano, db
from ..security import nutrizionista_required
from ..shopping import carrello_completo, fornitori_attivi, lista_spesa, testo_lista

bp = Blueprint("shopping", __name__, url_prefix="/piani")


def _giorni_richiesti() -> list[int] | None:
    """Filtro «solo alcuni giorni»: utile per la spesa di metà settimana."""
    valori = [int(g) for g in request.args.getlist("giorno") if g.isdigit()]
    valori = [g for g in valori if 0 <= g <= 6]
    return valori or None


@bp.route("/<int:piano_id>/spesa")
@nutrizionista_required
def lista(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    giorni = _giorni_richiesti()
    gruppi, manuali = lista_spesa(piano, giorni)
    fornitori = fornitori_attivi()
    return render_template(
        "shopping/lista.html",
        piano=piano,
        gruppi=gruppi,
        manuali=manuali,
        fornitori=fornitori,
        giorni_scelti=giorni or list(range(7)),
        carrelli={f.id: carrello_completo(f, gruppi) for f in fornitori},
        titolo=f"Spesa · {piano.titolo}",
    )


@bp.route("/<int:piano_id>/spesa.txt")
@nutrizionista_required
def testo(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    gruppi, manuali = lista_spesa(piano, _giorni_richiesti())
    corpo = testo_lista(gruppi, manuali, f"Lista della spesa — {piano.titolo}")
    return Response(
        corpo,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="spesa-{piano.id}.txt"'},
    )


@bp.route("/<int:piano_id>/spesa/invia", methods=["POST"])
@nutrizionista_required
def invia(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    giorni = [int(g) for g in request.form.getlist("giorno") if g.isdigit()] or None
    gruppi, manuali = lista_spesa(piano, giorni)
    if not gruppi and not manuali:
        flash("La lista è vuota: il piano non ha ancora alimenti.", "warning")
        return redirect(url_for("shopping.lista", piano_id=piano.id))

    intestazione = f"Lista della spesa — {piano.titolo}"
    if giorni:
        intestazione += " (" + ", ".join(GIORNI[g] for g in sorted(giorni)) + ")"
    inviata, dettaglio = invia_lista_spesa(piano, testo_lista(gruppi, manuali, intestazione))
    flash(dettaglio, "success" if inviata else "warning")
    return redirect(url_for("shopping.lista", piano_id=piano.id))
