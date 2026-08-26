"""Cruscotto dello studio, ricerca globale e centro notifiche."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from ..models import (
    Alimento,
    Appuntamento,
    Articolo,
    Assistito,
    Messaggio,
    Notifica,
    Piano,
    Ricetta,
    db,
)
from ..security import nutrizionista_required, utente_corrente

bp = Blueprint("main", __name__)


@bp.route("/studio")
@nutrizionista_required
def dashboard():
    oggi = date.today()
    fra_una_settimana = oggi + timedelta(days=7)

    assistiti_attivi = Assistito.query.filter_by(attivo=True).count()
    piani_pubblicati = Piano.query.filter_by(stato="pubblicato").all()
    piani_in_corso = [p for p in piani_pubblicati if p.data_inizio <= oggi <= p.data_fine]
    piani_in_scadenza = sorted(
        [p for p in piani_in_corso if p.data_fine <= fra_una_settimana],
        key=lambda p: p.data_fine,
    )

    appuntamenti = (
        Appuntamento.query.filter(
            Appuntamento.data_ora >= datetime.combine(oggi, datetime.min.time()),
            Appuntamento.stato.in_(["programmato", "confermato"]),
        )
        .order_by(Appuntamento.data_ora)
        .limit(6)
        .all()
    )

    messaggi_non_letti = (
        Messaggio.query.filter_by(mittente_ruolo="cliente", letto=False)
        .order_by(Messaggio.created_at.desc())
        .limit(5)
        .all()
    )

    senza_piano = [
        a
        for a in Assistito.query.filter_by(attivo=True).order_by(Assistito.cognome).all()
        if a.piano_attivo is None
    ]

    ultimi_assistiti = (
        Assistito.query.filter_by(attivo=True)
        .order_by(Assistito.created_at.desc())
        .limit(5)
        .all()
    )

    bozze = Articolo.query.filter_by(pubblicato=False).count()

    return render_template(
        "dashboard.html",
        assistiti_attivi=assistiti_attivi,
        piani_in_corso=piani_in_corso,
        piani_in_scadenza=piani_in_scadenza,
        appuntamenti=appuntamenti,
        messaggi_non_letti=messaggi_non_letti,
        senza_piano=senza_piano,
        ultimi_assistiti=ultimi_assistiti,
        bozze_articoli=bozze,
        ricette_totali=Ricetta.query.count(),
        alimenti_totali=Alimento.query.count(),
    )


@bp.route("/cerca")
@nutrizionista_required
def cerca():
    q = (request.args.get("q") or "").strip()
    risultati = {"assistiti": [], "alimenti": [], "ricette": [], "articoli": []}

    if len(q) >= 2:
        like = f"%{q}%"
        risultati["assistiti"] = (
            Assistito.query.filter(
                or_(
                    Assistito.nome.ilike(like),
                    Assistito.cognome.ilike(like),
                    Assistito.email.ilike(like),
                    Assistito.telefono.ilike(like),
                )
            )
            .order_by(Assistito.cognome)
            .limit(20)
            .all()
        )
        risultati["alimenti"] = (
            Alimento.query.filter(
                or_(Alimento.nome.ilike(like), Alimento.nome_it.ilike(like))
            )
            .order_by(Alimento.nome_it, Alimento.nome)
            .limit(20)
            .all()
        )
        risultati["ricette"] = (
            Ricetta.query.filter(
                or_(Ricetta.titolo.ilike(like), Ricetta.tags.ilike(like))
            )
            .order_by(Ricetta.titolo)
            .limit(15)
            .all()
        )
        risultati["articoli"] = (
            Articolo.query.filter(
                or_(Articolo.titolo.ilike(like), Articolo.sommario.ilike(like))
            )
            .order_by(Articolo.titolo)
            .limit(15)
            .all()
        )

    totale = sum(len(v) for v in risultati.values())
    return render_template("search.html", q=q, risultati=risultati, totale=totale)


# ----------------------------------------------------------------------
# Notifiche
# ----------------------------------------------------------------------
@bp.route("/notifiche")
@nutrizionista_required
def notifiche():
    elenco = Notifica.query.filter_by(destinatario="nutrizionista").order_by(
        Notifica.letta, Notifica.created_at.desc()
    ).limit(200).all()
    return render_template("notifiche.html", notifiche=elenco)


@bp.route("/notifiche/<int:notifica_id>/letta", methods=["POST"])
@nutrizionista_required
def segna_letta(notifica_id: int):
    notifica = db.get_or_404(Notifica, notifica_id)
    notifica.letta = True
    db.session.commit()
    return redirect(notifica.link or url_for("main.notifiche"))


@bp.route("/notifiche/tutte-lette", methods=["POST"])
@nutrizionista_required
def segna_tutte_lette():
    utente = utente_corrente()
    destinatario = "nutrizionista" if utente.is_nutrizionista else "cliente"
    aggiornate = Notifica.query.filter_by(destinatario=destinatario, letta=False).update(
        {"letta": True}
    )
    db.session.commit()
    flash(f"{aggiornate} notifiche segnate come lette.", "success")
    return redirect(url_for("main.notifiche"))


@bp.route("/notifiche/pulisci", methods=["POST"])
@nutrizionista_required
def pulisci():
    """Elimina le notifiche lette più vecchie di un mese."""
    limite = datetime.utcnow() - timedelta(days=30)
    eliminate = Notifica.query.filter(
        Notifica.letta.is_(True), Notifica.created_at < limite
    ).delete()
    db.session.commit()
    flash(f"{eliminate} notifiche archiviate.", "info")
    return redirect(url_for("main.notifiche"))
