"""Piani alimentari: costruzione, analisi, scheda da consegnare, pubblicazione."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import forms
from ..mailer import invia_piano_pubblicato
from ..models import (
    Alimento,
    Assistito,
    DIETE,
    GIORNI,
    PASTI,
    Piano,
    Ricetta,
    STATI_PIANO,
    VocePiano,
    db,
)
from ..notifications import notifica_al_cliente
from ..nutrition import CHIAVI, NUTRIENTI, analisi_piano
from ..security import nutrizionista_required

bp = Blueprint("plans", __name__, url_prefix="/piani")


def _alimenti_per_menu():
    """Alimenti raggruppati per reparto, per i menu a tendina del costruttore."""
    alimenti = Alimento.query.order_by(
        Alimento.categoria_it, Alimento.nome_it, Alimento.nome
    ).all()
    gruppi: dict[str, list[Alimento]] = {}
    for a in alimenti:
        gruppi.setdefault(a.categoria_it or a.categoria or "Altro", []).append(a)
    return gruppi


@bp.route("/")
@nutrizionista_required
def elenco():
    stato = request.args.get("stato", "")
    query = Piano.query
    if stato in STATI_PIANO:
        query = query.filter_by(stato=stato)
    piani = query.order_by(Piano.data_inizio.desc()).all()
    return render_template("plans/list.html", piani=piani, stato=stato, stati=STATI_PIANO)


@bp.route("/nuovo", methods=["GET", "POST"])
@nutrizionista_required
def nuovo():
    assistito_id = forms.intero(request.args.get("assistito")) or forms.intero(
        request.form.get("assistito_id")
    )
    assistito = db.session.get(Assistito, assistito_id) if assistito_id else None

    if request.method == "POST":
        if assistito is None:
            flash("Scegli l'assistito a cui intestare il piano.", "warning")
        else:
            inizio = forms.data(request.form.get("data_inizio")) or date.today()
            settimane = forms.intero(request.form.get("settimane")) or 4
            piano = Piano(
                assistito_id=assistito.id,
                titolo=forms.testo(request.form.get("titolo"), 200)
                or f"Piano {inizio.strftime('%d/%m/%Y')}",
                data_inizio=inizio,
                data_fine=inizio + timedelta(weeks=max(1, settimane)) - timedelta(days=1),
                target_kcal=forms.intero(request.form.get("target_kcal"))
                or assistito.target_kcal
                or 1800,
                tipo_dieta=forms.testo(request.form.get("tipo_dieta"), 40)
                or assistito.tipo_dieta
                or "Standard",
                note_nutrizionista=forms.testo(request.form.get("note_nutrizionista")),
                note_cliente=forms.testo(request.form.get("note_cliente")),
            )
            db.session.add(piano)
            db.session.commit()

            copia_da = forms.intero(request.form.get("copia_da"))
            if copia_da:
                _copia_voci(copia_da, piano)
                flash("Piano creato copiando la settimana del piano precedente.", "success")
            else:
                flash("Piano creato: ora componi la settimana.", "success")
            return redirect(url_for("plans.dettaglio", piano_id=piano.id))

    assistiti = Assistito.query.filter_by(attivo=True).order_by(Assistito.cognome).all()
    piani_esistenti = (
        Piano.query.filter_by(assistito_id=assistito.id).order_by(Piano.data_inizio.desc()).all()
        if assistito
        else []
    )
    return render_template(
        "plans/form.html",
        assistito=assistito,
        assistiti=assistiti,
        diete=DIETE,
        piani_esistenti=piani_esistenti,
        oggi=date.today(),
    )


def _copia_voci(piano_origine_id: int, piano_destinazione: Piano) -> int:
    origine = db.session.get(Piano, piano_origine_id)
    if origine is None:
        return 0
    for voce in origine.voci:
        db.session.add(
            VocePiano(
                piano_id=piano_destinazione.id,
                giorno=voce.giorno,
                pasto=voce.pasto,
                ordine=voce.ordine,
                alimento_id=voce.alimento_id,
                ricetta_id=voce.ricetta_id,
                testo_libero=voce.testo_libero,
                porzioni=voce.porzioni,
                nota=voce.nota,
            )
        )
    db.session.commit()
    return len(origine.voci)


@bp.route("/<int:piano_id>")
@nutrizionista_required
def dettaglio(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    analisi = analisi_piano(piano)
    return render_template(
        "plans/builder.html",
        piano=piano,
        analisi=analisi,
        gruppi_alimenti=_alimenti_per_menu(),
        ricette=Ricetta.query.order_by(Ricetta.titolo).all(),
        diete=DIETE,
        nutrienti=NUTRIENTI,
    )


@bp.route("/<int:piano_id>/giorno/<int:giorno>")
@nutrizionista_required
def giorno(piano_id: int, giorno: int):
    """Scheda di una singola giornata: quella che il cliente vede sul telefono."""
    piano = db.get_or_404(Piano, piano_id)
    giorno = max(0, min(6, giorno))
    analisi = analisi_piano(piano)
    return render_template(
        "plans/giorno.html",
        piano=piano,
        giorno=analisi["giorni"][giorno],
        analisi=analisi,
        anteprima=True,
    )


@bp.route("/<int:piano_id>/impostazioni", methods=["POST"])
@nutrizionista_required
def impostazioni(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    f = request.form
    piano.titolo = forms.testo(f.get("titolo"), 200) or piano.titolo
    piano.data_inizio = forms.data(f.get("data_inizio")) or piano.data_inizio
    piano.data_fine = forms.data(f.get("data_fine")) or piano.data_fine
    piano.target_kcal = forms.intero(f.get("target_kcal")) or piano.target_kcal
    piano.tipo_dieta = forms.testo(f.get("tipo_dieta"), 40) or piano.tipo_dieta
    piano.note_nutrizionista = forms.testo(f.get("note_nutrizionista"))
    piano.note_cliente = forms.testo(f.get("note_cliente"))

    # Riferimenti nutrizionali personalizzati per questo assistito.
    riferimenti = {}
    for chiave in CHIAVI:
        valore = forms.numero(f.get(f"rif_{chiave}"))
        if valore is not None:
            riferimenti[chiave] = valore
    if riferimenti:
        piano.imposta_riferimenti(riferimenti)

    db.session.commit()
    flash("Impostazioni del piano aggiornate.", "success")
    return redirect(url_for("plans.dettaglio", piano_id=piano.id))


# ----------------------------------------------------------------------
# Voci del piano
# ----------------------------------------------------------------------
@bp.route("/<int:piano_id>/voci", methods=["POST"])
@nutrizionista_required
def aggiungi_voce(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    f = request.form
    giorno = max(0, min(6, forms.intero(f.get("giorno")) or 0))
    pasto = forms.testo(f.get("pasto"), 30) or PASTI[0]

    alimento_id = forms.intero(f.get("alimento_id"))
    ricetta_id = forms.intero(f.get("ricetta_id"))
    libero = forms.testo(f.get("testo_libero"), 250)

    if not (alimento_id or ricetta_id or libero):
        flash("Scegli un alimento, una ricetta oppure scrivi una voce libera.", "warning")
        return redirect(url_for("plans.dettaglio", piano_id=piano.id) + f"#giorno-{giorno}")

    ultimo = max(
        [v.ordine for v in piano.voci if v.giorno == giorno and v.pasto == pasto],
        default=-1,
    )
    db.session.add(
        VocePiano(
            piano_id=piano.id,
            giorno=giorno,
            pasto=pasto,
            ordine=ultimo + 1,
            alimento_id=alimento_id,
            ricetta_id=ricetta_id if not alimento_id else None,
            testo_libero=libero if not (alimento_id or ricetta_id) else None,
            porzioni=forms.numero(f.get("porzioni")) or 1.0,
            nota=forms.testo(f.get("nota"), 250),
        )
    )
    db.session.commit()
    return redirect(url_for("plans.dettaglio", piano_id=piano.id) + f"#giorno-{giorno}")


@bp.route("/<int:piano_id>/voci/<int:voce_id>/porzioni", methods=["POST"])
@nutrizionista_required
def aggiorna_porzioni(piano_id: int, voce_id: int):
    voce = db.get_or_404(VocePiano, voce_id)
    if voce.piano_id != piano_id:
        flash("Voce non trovata.", "warning")
        return redirect(url_for("plans.dettaglio", piano_id=piano_id))
    porzioni = forms.numero(request.form.get("porzioni"))
    if porzioni and porzioni > 0:
        voce.porzioni = porzioni
        db.session.commit()
    return redirect(url_for("plans.dettaglio", piano_id=piano_id) + f"#giorno-{voce.giorno}")


@bp.route("/<int:piano_id>/voci/<int:voce_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina_voce(piano_id: int, voce_id: int):
    voce = db.get_or_404(VocePiano, voce_id)
    if voce.piano_id != piano_id:
        flash("Voce non trovata.", "warning")
        return redirect(url_for("plans.dettaglio", piano_id=piano_id))
    giorno = voce.giorno
    db.session.delete(voce)
    db.session.commit()
    return redirect(url_for("plans.dettaglio", piano_id=piano_id) + f"#giorno-{giorno}")


@bp.route("/<int:piano_id>/giorni/<int:giorno>/copia", methods=["POST"])
@nutrizionista_required
def copia_giorno(piano_id: int, giorno: int):
    """Copia una giornata su altri giorni: la settimana si compone in fretta."""
    piano = db.get_or_404(Piano, piano_id)
    destinazioni = [int(g) for g in request.form.getlist("destinazioni") if g.isdigit()]
    destinazioni = [g for g in destinazioni if 0 <= g <= 6 and g != giorno]
    if not destinazioni:
        flash("Scegli almeno un giorno di destinazione.", "warning")
        return redirect(url_for("plans.dettaglio", piano_id=piano.id) + f"#giorno-{giorno}")

    sorgente = piano.voci_giorno(giorno)
    sostituisci = forms.flag(request.form.get("sostituisci"))
    for destinazione in destinazioni:
        if sostituisci:
            for voce in piano.voci_giorno(destinazione):
                db.session.delete(voce)
        for voce in sorgente:
            db.session.add(
                VocePiano(
                    piano_id=piano.id,
                    giorno=destinazione,
                    pasto=voce.pasto,
                    ordine=voce.ordine,
                    alimento_id=voce.alimento_id,
                    ricetta_id=voce.ricetta_id,
                    testo_libero=voce.testo_libero,
                    porzioni=voce.porzioni,
                    nota=voce.nota,
                )
            )
    db.session.commit()
    nomi = ", ".join(GIORNI[g] for g in sorted(destinazioni))
    flash(f"{GIORNI[giorno]} copiato su: {nomi}.", "success")
    return redirect(url_for("plans.dettaglio", piano_id=piano.id))


@bp.route("/<int:piano_id>/giorni/<int:giorno>/svuota", methods=["POST"])
@nutrizionista_required
def svuota_giorno(piano_id: int, giorno: int):
    piano = db.get_or_404(Piano, piano_id)
    for voce in piano.voci_giorno(giorno):
        db.session.delete(voce)
    db.session.commit()
    flash(f"{GIORNI[giorno]} svuotato.", "info")
    return redirect(url_for("plans.dettaglio", piano_id=piano.id) + f"#giorno-{giorno}")


# ----------------------------------------------------------------------
# Analisi e scheda
# ----------------------------------------------------------------------
@bp.route("/<int:piano_id>/analisi")
@nutrizionista_required
def analisi(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    return render_template(
        "plans/analisi.html",
        piano=piano,
        analisi=analisi_piano(piano),
        nutrienti=NUTRIENTI,
    )


@bp.route("/<int:piano_id>/scheda")
@nutrizionista_required
def scheda(piano_id: int):
    """Il foglio da stampare o salvare in PDF e consegnare al cliente."""
    piano = db.get_or_404(Piano, piano_id)
    return render_template("plans/scheda.html", piano=piano, analisi=analisi_piano(piano))


# ----------------------------------------------------------------------
# Stati
# ----------------------------------------------------------------------
@bp.route("/<int:piano_id>/pubblica", methods=["POST"])
@nutrizionista_required
def pubblica(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    analisi = analisi_piano(piano)
    if analisi["giorni_compilati"] == 0:
        flash("Il piano è vuoto: aggiungi almeno una giornata prima di pubblicarlo.", "warning")
        return redirect(url_for("plans.dettaglio", piano_id=piano.id))

    # Un piano pubblicato per volta: gli altri dello stesso assistito vanno in archivio.
    for altro in piano.assistito.piani:
        if altro.id != piano.id and altro.stato == "pubblicato":
            altro.stato = "archiviato"

    piano.stato = "pubblicato"
    piano.pubblicato_at = datetime.utcnow()
    db.session.commit()

    notifica_al_cliente(
        piano.assistito,
        f"Il tuo nuovo piano «{piano.titolo}» è disponibile.",
        url_for("portal.piano"),
        chiave=f"piano-pubblicato-{piano.id}",
    )

    messaggi = [f"Piano pubblicato: {piano.assistito.nome_completo} lo vede nella sua area."]
    if piano.assistito.utente is None:
        messaggi.append("L'assistito non ha ancora un accesso: creane uno dalla sua scheda.")
    else:
        inviata, dettaglio = invia_piano_pubblicato(piano)
        messaggi.append("Email di avviso inviata." if inviata else dettaglio)
    flash(" ".join(messaggi), "success")

    if analisi["conflitti"]:
        flash(
            f"Attenzione: {len(analisi['conflitti'])} voci non rispettano la dieta "
            f"«{piano.tipo_dieta}». Controllale nell'analisi.",
            "warning",
        )
    return redirect(url_for("plans.dettaglio", piano_id=piano.id))


@bp.route("/<int:piano_id>/archivia", methods=["POST"])
@nutrizionista_required
def archivia(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    piano.stato = "archiviato"
    db.session.commit()
    flash("Piano archiviato: non è più visibile al cliente.", "info")
    return redirect(url_for("plans.dettaglio", piano_id=piano.id))


@bp.route("/<int:piano_id>/riporta-in-bozza", methods=["POST"])
@nutrizionista_required
def riporta_in_bozza(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    piano.stato = "bozza"
    db.session.commit()
    flash("Piano riportato in bozza.", "info")
    return redirect(url_for("plans.dettaglio", piano_id=piano.id))


@bp.route("/<int:piano_id>/duplica", methods=["POST"])
@nutrizionista_required
def duplica(piano_id: int):
    origine = db.get_or_404(Piano, piano_id)
    durata = (origine.data_fine - origine.data_inizio).days or 27
    inizio = max(date.today(), origine.data_fine + timedelta(days=1))
    copia = Piano(
        assistito_id=origine.assistito_id,
        titolo=f"{origine.titolo} (copia)",
        data_inizio=inizio,
        data_fine=inizio + timedelta(days=durata),
        target_kcal=origine.target_kcal,
        tipo_dieta=origine.tipo_dieta,
        note_nutrizionista=origine.note_nutrizionista,
        note_cliente=origine.note_cliente,
        riferimenti_json=origine.riferimenti_json,
    )
    db.session.add(copia)
    db.session.commit()
    _copia_voci(origine.id, copia)
    flash("Piano duplicato: modifica le date e la settimana.", "success")
    return redirect(url_for("plans.dettaglio", piano_id=copia.id))


@bp.route("/<int:piano_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina(piano_id: int):
    piano = db.get_or_404(Piano, piano_id)
    assistito_id = piano.assistito_id
    db.session.delete(piano)
    db.session.commit()
    flash("Piano eliminato.", "info")
    return redirect(url_for("clients.dettaglio", assistito_id=assistito_id))
