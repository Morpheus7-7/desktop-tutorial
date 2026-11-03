"""Note: il diario delle attività di ogni giorno, divise per sezione, con
promemoria via email e Google Calendar."""
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for

from .. import diario, google
from ..models import SEZIONI_NOTE, SEZIONI_NOTE_LABELS, Client, Nota, db

bp = Blueprint("note", __name__, url_prefix="/note")

PERIODI = {"7": 7, "30": 30, "90": 90, "365": 365, "tutte": None}


def _data(valore):
    try:
        return date.fromisoformat(valore) if valore else None
    except ValueError:
        return None


def _ora(valore):
    valore = (valore or "").strip()
    try:
        return datetime.strptime(valore, "%H:%M").strftime("%H:%M") if valore else None
    except ValueError:
        return None


def _destinazione(predefinita: str) -> str:
    dest = request.form.get("next") or ""
    if dest.startswith("/") and not dest.startswith("//") and "\\" not in dest:
        return dest
    return predefinita


def _compila(nota: Nota, form) -> str | None:
    """Riempie la nota dal modulo; restituisce un errore o None."""
    nota.titolo = (form.get("titolo") or "").strip()[:200]
    nota.testo = (form.get("testo") or "").strip()[:20000] or None
    nota.giorno = _data(form.get("giorno")) or nota.giorno or date.today()
    nota.ora = _ora(form.get("ora"))
    sezione = form.get("sezione", "altro")
    nota.sezione = sezione if sezione in SEZIONI_NOTE_LABELS else "altro"
    cliente = form.get("client_id", type=int)
    nota.client_id = cliente if cliente and db.session.get(Client, cliente) else None

    giorno_p, ora_p = _data(form.get("promemoria_giorno")), _ora(form.get("promemoria_ora"))
    if giorno_p:
        nuovo = datetime.combine(giorno_p, datetime.strptime(ora_p or "09:00", "%H:%M").time())
        if nuovo != nota.promemoria_il:
            nota.promemoria_fatto = False  # promemoria spostato: torna da fare
        nota.promemoria_il = nuovo
        nota.promemoria_email = bool(form.get("promemoria_email"))
    else:
        nota.promemoria_il, nota.promemoria_email, nota.promemoria_fatto = None, False, False
    if not nota.titolo:
        return "Scrivi almeno il titolo della nota."
    return None


def _messaggio_salvata(nota: Nota) -> str:
    msg = "Nota salvata."
    if nota.promemoria_aperto:
        msg += f" Promemoria il {nota.promemoria_il:%d/%m alle %H:%M}"
        msg += " via email." if nota.promemoria_email else "."
        if nota.promemoria_email and not diario.destinatari_configurati():
            msg += " Attenzione: l'email non è ancora configurata (Impostazioni → Google)."
    return msg


GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


@bp.app_template_filter("giorno_lungo")
def giorno_lungo(giorno: date) -> str:
    """«martedì 28 ottobre» (con l'anno se non è quello in corso)."""
    testo = f"{GIORNI[giorno.weekday()]} {giorno.day} {MESI[giorno.month - 1]}"
    return testo if giorno.year == date.today().year else f"{testo} {giorno.year}"


@bp.app_template_global("link_calendar_nota")
def link_calendar_nota(nota: Nota) -> str:
    dettagli = nota.testo or ""
    if nota.cliente:
        dettagli = f"Cliente: {nota.cliente.ragione_sociale}\n\n{dettagli}".strip()
    titolo = f"{nota.titolo} ({nota.cliente.ragione_sociale})" if nota.cliente else nota.titolo
    if nota.promemoria_il:
        return google.link_calendar_ora(titolo, nota.promemoria_il, dettagli)
    return google.link_calendar(titolo, nota.giorno, dettagli)


@bp.route("/")
def index():
    sezione = request.args.get("sezione", "")
    q = (request.args.get("q") or "").strip()
    periodo = request.args.get("periodo", "30")
    giorni = PERIODI.get(periodo, 30)
    cliente_id = request.args.get("cliente", type=int)

    query = Nota.query
    if sezione in SEZIONI_NOTE_LABELS:
        query = query.filter(Nota.sezione == sezione)
    if cliente_id:
        query = query.filter(Nota.client_id == cliente_id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Nota.titolo.ilike(like), Nota.testo.ilike(like)))
    if giorni and not q:
        query = query.filter(Nota.giorno >= date.today() - timedelta(days=giorni))
    note = query.order_by(Nota.giorno.desc(), Nota.ora.desc(), Nota.id.desc()).limit(500).all()

    per_giorno: dict[date, list[Nota]] = {}
    for n in note:
        per_giorno.setdefault(n.giorno, []).append(n)

    promemoria = (Nota.query.filter(Nota.promemoria_il.isnot(None), Nota.promemoria_fatto.is_(False))
                  .order_by(Nota.promemoria_il).limit(20).all())
    return render_template(
        "note/index.html", per_giorno=per_giorno, promemoria=promemoria, sezioni=SEZIONI_NOTE,
        sezione=sezione, q=q, periodo=periodo, cliente_id=cliente_id,
        cliente_filtro=db.session.get(Client, cliente_id) if cliente_id else None,
        clienti=Client.query.order_by(Client.ragione_sociale).all(), adesso=datetime.now(),
        email_pronta=diario.destinatari_configurati(),
    )


@bp.route("/nuova", methods=["POST"])
def new():
    nota = Nota()
    errore = _compila(nota, request.form)
    if errore:
        flash(errore, "danger")
    else:
        db.session.add(nota)
        db.session.commit()
        flash(_messaggio_salvata(nota), "success")
    return redirect(_destinazione(url_for("note.index")))


@bp.route("/<int:nota_id>/modifica", methods=["GET", "POST"])
def edit(nota_id):
    nota = db.get_or_404(Nota, nota_id)
    if request.method == "POST":
        errore = _compila(nota, request.form)
        if errore:
            flash(errore, "danger")
        else:
            db.session.commit()
            flash(_messaggio_salvata(nota), "success")
            return redirect(_destinazione(url_for("note.index")))
    return render_template("note/modifica.html", nota=nota, sezioni=SEZIONI_NOTE,
                           clienti=Client.query.order_by(Client.ragione_sociale).all(),
                           email_pronta=diario.destinatari_configurati(),
                           inviato=diario.gia_inviato(current_app, nota))


@bp.route("/<int:nota_id>/elimina", methods=["POST"])
def delete(nota_id):
    nota = db.get_or_404(Nota, nota_id)
    db.session.delete(nota)
    db.session.commit()
    flash("Nota eliminata.", "success")
    return redirect(_destinazione(url_for("note.index")))


@bp.route("/<int:nota_id>/fatto", methods=["POST"])
def done(nota_id):
    nota = db.get_or_404(Nota, nota_id)
    if not nota.promemoria_il:
        abort(404)
    nota.promemoria_fatto = not nota.promemoria_fatto
    db.session.commit()
    return redirect(_destinazione(url_for("note.index")))


@bp.route("/promemoria.ics")
def calendar_ics():
    """Tutti i promemoria futuri, da importare in Google Calendar in una volta."""
    note = (Nota.query.filter(Nota.promemoria_il >= datetime.now() - timedelta(days=1),
                              Nota.promemoria_fatto.is_(False))
            .order_by(Nota.promemoria_il).all())
    eventi = [{
        "uid": f"nota-{n.id}-{n.promemoria_il:%Y%m%d%H%M}",
        "titolo": f"{n.titolo} ({n.cliente.ragione_sociale})" if n.cliente else n.titolo,
        "inizio": n.promemoria_il,
        "dettagli": n.testo or "",
    } for n in note]
    return Response(google.calendario_ics(eventi, "Deal Combined - Promemoria"), mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=deal-combined-promemoria.ics"})
