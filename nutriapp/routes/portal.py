"""Area riservata del cliente.

Qui l'assistito vede soltanto le proprie cose: il piano pubblicato, la scheda
del giorno, la spesa, le ricette e gli articoli pubblicati, i suoi progressi e
la conversazione con lo studio. Nessuna vista di quest'area accetta un id
altrui: l'assistito viene sempre ricavato dalla sessione.
"""
from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from .. import forms
from ..models import Articolo, Messaggio, Misurazione, Notifica, Ricetta, db

from ..nutrition import analisi_piano, nutrienti_ricetta
from ..security import assistito_corrente, cliente_required
from ..shopping import carrello_completo, fornitori_attivi, lista_spesa, testo_lista

bp = Blueprint("portal", __name__, url_prefix="/area")


def _piano_o_niente():
    """Il piano pubblicato dell'assistito, oppure None se lo studio non l'ha ancora
    pubblicato: l'area resta navigabile lo stesso."""
    assistito = assistito_corrente()
    return assistito.piano_attivo if assistito else None


@bp.route("/")
@cliente_required
def home():
    assistito = assistito_corrente()
    piano = _piano_o_niente()

    giorno_oggi = None
    analisi = None
    if piano:
        analisi = analisi_piano(piano)
        indice = piano.indice_giorno_oggi()
        if indice is None:
            indice = min(date.today().weekday(), 6)
        giorno_oggi = analisi["giorni"][indice]

    prossimo_appuntamento = next(
        (
            a
            for a in assistito.appuntamenti
            if a.stato in ("programmato", "confermato")
            and a.data_ora.date() >= date.today()
        ),
        None,
    )
    ultimi_messaggi = assistito.messaggi[-3:]
    articoli = (
        Articolo.query.filter_by(pubblicato=True)
        .order_by(Articolo.data_pubblicazione.desc())
        .limit(3)
        .all()
    )

    return render_template(
        "portal/home.html",
        assistito=assistito,
        piano=piano,
        analisi=analisi,
        giorno=giorno_oggi,
        prossimo_appuntamento=prossimo_appuntamento,
        ultimi_messaggi=ultimi_messaggi,
        articoli=articoli,
        notifiche=Notifica.query.filter_by(
            destinatario="cliente", assistito_id=assistito.id, letta=False
        )
        .order_by(Notifica.created_at.desc())
        .limit(5)
        .all(),
    )


@bp.route("/piano")
@cliente_required
def piano():
    piano = _piano_o_niente()
    if piano is None:
        return render_template("portal/piano.html", piano=None, analisi=None)
    return render_template("portal/piano.html", piano=piano, analisi=analisi_piano(piano))


@bp.route("/giorno/<int:giorno>")
@cliente_required
def giorno(giorno: int):
    """La scheda pasti di una giornata: la pagina che si guarda in cucina."""
    piano = _piano_o_niente()
    if piano is None:
        flash("Non hai ancora un piano pubblicato.", "info")
        return redirect(url_for("portal.home"))
    giorno = max(0, min(6, giorno))
    analisi = analisi_piano(piano)
    return render_template(
        "portal/giorno.html", piano=piano, analisi=analisi, giorno=analisi["giorni"][giorno]
    )


# ----------------------------------------------------------------------
# Spesa
# ----------------------------------------------------------------------
@bp.route("/spesa")
@cliente_required
def spesa():
    piano = _piano_o_niente()
    if piano is None:
        return render_template("portal/spesa.html", piano=None, gruppi=[], manuali=[], fornitori=[])
    giorni = [int(g) for g in request.args.getlist("giorno") if g.isdigit()] or None
    gruppi, manuali = lista_spesa(piano, giorni)
    fornitori = fornitori_attivi()
    return render_template(
        "portal/spesa.html",
        piano=piano,
        gruppi=gruppi,
        manuali=manuali,
        fornitori=fornitori,
        giorni_scelti=giorni or list(range(7)),
        carrelli={f.id: carrello_completo(f, gruppi) for f in fornitori},
    )


@bp.route("/spesa.txt")
@cliente_required
def spesa_testo():
    piano = _piano_o_niente()
    if piano is None:
        abort(404)
    gruppi, manuali = lista_spesa(piano)
    corpo = testo_lista(gruppi, manuali, f"Lista della spesa — {piano.titolo}")
    return Response(
        corpo,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="lista-spesa.txt"'},
    )


# ----------------------------------------------------------------------
# Contenuti
# ----------------------------------------------------------------------
@bp.route("/ricette")
@cliente_required
def ricette():
    q = (request.args.get("q") or "").strip()
    query = Ricetta.query.filter_by(pubblicata=True)
    if q:
        query = query.filter(Ricetta.titolo.ilike(f"%{q}%"))
    elenco = query.order_by(Ricetta.categoria, Ricetta.titolo).all()
    schede = [{"ricetta": r, "per_porzione": nutrienti_ricetta(r)[1]} for r in elenco]
    return render_template("portal/ricette.html", schede=schede, q=q)


@bp.route("/ricette/<slug>")
@cliente_required
def ricetta(slug: str):
    ricetta = Ricetta.query.filter_by(slug=slug, pubblicata=True).first_or_404()
    totale, per_porzione = nutrienti_ricetta(ricetta)
    return render_template(
        "portal/ricetta.html", ricetta=ricetta, totale=totale, per_porzione=per_porzione
    )


@bp.route("/blog")
@cliente_required
def blog():
    categoria = request.args.get("categoria") or ""
    query = Articolo.query.filter_by(pubblicato=True)
    if categoria:
        query = query.filter_by(categoria=categoria)
    articoli = query.order_by(Articolo.data_pubblicazione.desc()).all()
    categorie = sorted({a.categoria for a in Articolo.query.filter_by(pubblicato=True) if a.categoria})
    return render_template(
        "portal/blog.html", articoli=articoli, categorie=categorie, categoria=categoria
    )


@bp.route("/blog/<slug>")
@cliente_required
def articolo(slug: str):
    articolo = Articolo.query.filter_by(slug=slug, pubblicato=True).first_or_404()
    correlati = (
        Articolo.query.filter(
            Articolo.pubblicato.is_(True),
            Articolo.categoria == articolo.categoria,
            Articolo.id != articolo.id,
        )
        .limit(3)
        .all()
    )
    return render_template("portal/articolo.html", articolo=articolo, correlati=correlati)


# ----------------------------------------------------------------------
# Progressi e messaggi
# ----------------------------------------------------------------------
@bp.route("/progressi", methods=["GET", "POST"])
@cliente_required
def progressi():
    assistito = assistito_corrente()

    if request.method == "POST":
        peso = forms.numero(request.form.get("peso_kg"))
        if peso is None:
            flash("Indica almeno il peso.", "warning")
        else:
            db.session.add(
                Misurazione(
                    assistito_id=assistito.id,
                    data=forms.data(request.form.get("data")) or date.today(),
                    peso_kg=peso,
                    vita_cm=forms.numero(request.form.get("vita_cm")),
                    note=forms.testo(request.form.get("note")),
                    inserita_dal_cliente=True,
                )
            )
            db.session.commit()
            flash("Misurazione registrata. La vedrà anche il tuo nutrizionista.", "success")
        return redirect(url_for("portal.progressi"))

    serie = [m for m in reversed(assistito.misurazioni) if m.peso_kg]
    return render_template(
        "portal/progressi.html", assistito=assistito, serie_peso=serie, oggi=date.today()
    )


@bp.route("/messaggi", methods=["GET", "POST"])
@cliente_required
def messaggi():
    assistito = assistito_corrente()

    if request.method == "POST":
        testo = forms.testo(request.form.get("testo"))
        if not testo:
            flash("Il messaggio è vuoto.", "warning")
        else:
            db.session.add(
                Messaggio(
                    assistito_id=assistito.id,
                    mittente_ruolo="cliente",
                    mittente_nome=assistito.nome_completo,
                    testo=testo,
                )
            )
            db.session.commit()
            flash("Messaggio inviato allo studio.", "success")
        return redirect(url_for("portal.messaggi"))

    # Aprendo la conversazione i messaggi dello studio risultano letti.
    for m in assistito.messaggi:
        if m.mittente_ruolo == "nutrizionista" and not m.letto:
            m.letto = True
    db.session.commit()

    return render_template("portal/messaggi.html", assistito=assistito)


@bp.route("/profilo")
@cliente_required
def profilo():
    return render_template("portal/profilo.html", assistito=assistito_corrente())


@bp.route("/notifiche/lette", methods=["POST"])
@cliente_required
def notifiche_lette():
    assistito = assistito_corrente()
    Notifica.query.filter_by(
        destinatario="cliente", assistito_id=assistito.id, letta=False
    ).update({"letta": True})
    db.session.commit()
    return redirect(url_for("portal.home"))
