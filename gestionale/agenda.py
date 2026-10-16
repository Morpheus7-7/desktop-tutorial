"""Agenda delle scadenze future: un elenco unico di eventi datati.

Raccoglie in ordine cronologico tutto ciò che ha una data da rispettare:
scadenze e decorrenze delle polizze, termini di disdetta, rate da incassare
e giorni di sospensione della copertura, follow-up, termini di denuncia dei
sinistri, documenti d'identità e questionari di adeguatezza in scadenza.
L'agenda alimenta lo scadenzario e l'esportazione in calendario (.ics).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from flask import url_for

from .models import (
    CLAIM_OPEN_STATUSES,
    GIORNI_DENUNCIA_SINISTRO,
    Claim,
    Client,
    FollowUp,
    Policy,
    Title,
)
from .utils import formatta_euro

STATI_ATTIVI = ("attiva", "in_rinnovo")

# Tipi di evento: etichetta, icona Bootstrap e colore del badge.
TIPI_EVENTO = {
    "scadenza": ("Scadenza polizza", "bi-calendar-x", "bg-danger"),
    "decorrenza": ("Decorrenza polizza", "bi-calendar-plus", "bg-info text-dark"),
    "disdetta": ("Termine disdetta", "bi-envelope-x", "bg-warning text-dark"),
    "rata": ("Rata da incassare", "bi-cash-coin", "bg-primary"),
    "sospensione": ("Sospensione copertura", "bi-shield-exclamation", "bg-danger"),
    "followup": ("Follow-up", "bi-check2-square", "bg-secondary"),
    "denuncia": ("Termine denuncia sinistro", "bi-exclamation-octagon", "bg-danger"),
    "documento": ("Documento d'identità", "bi-person-vcard", "bg-warning text-dark"),
    "adeguatezza": ("Questionario di adeguatezza", "bi-clipboard-check", "bg-warning text-dark"),
}


@dataclass
class Evento:
    data: date
    tipo: str
    titolo: str
    dettaglio: str
    link: str
    uid: str

    @property
    def etichetta(self) -> str:
        return TIPI_EVENTO[self.tipo][0]

    @property
    def icona(self) -> str:
        return TIPI_EVENTO[self.tipo][1]

    @property
    def badge(self) -> str:
        return TIPI_EVENTO[self.tipo][2]

    @property
    def giorni(self) -> int:
        return (self.data - date.today()).days


def eventi_agenda(dal: date, al: date, tipi: set[str] | None = None) -> list[Evento]:
    """Eventi con data in [dal, al], in ordine cronologico."""
    tipi = set(TIPI_EVENTO) if tipi is None else tipi
    eventi: list[Evento] = []

    def aggiungi(giorno, tipo, titolo, dettaglio, link, uid):
        if giorno is not None and dal <= giorno <= al and tipo in tipi:
            eventi.append(Evento(giorno, tipo, titolo, dettaglio, link, uid))

    polizze = Policy.query.filter(Policy.stato.in_(STATI_ATTIVI)).all()
    for p in polizze:
        link = url_for("policies.detail", policy_id=p.id)
        nome = f"{p.cliente.ragione_sociale} · {p.compagnia} n. {p.numero_polizza}"
        if p.data_scadenza:
            esito = (
                "disdetta inviata: cessa" if p.disdetta_inviata
                else "rinnovo tacito" if p.tacito_rinnovo else "da rinnovare"
            )
            aggiungi(p.data_scadenza, "scadenza", f"Scadenza polizza {p.numero_polizza}",
                     f"{nome} ({esito})", link, f"polizza-{p.id}-scadenza-{p.data_scadenza:%Y%m%d}")
        if p.data_decorrenza and p.non_ancora_in_vigore:
            aggiungi(p.data_decorrenza, "decorrenza", f"Decorrenza polizza {p.numero_polizza}",
                     nome, link, f"polizza-{p.id}-decorrenza-{p.data_decorrenza:%Y%m%d}")
        termine = p.termine_disdetta
        if termine and not p.disdetta_inviata:
            aggiungi(termine, "disdetta", f"Ultimo giorno per la disdetta {p.numero_polizza}",
                     f"{nome}: preavviso di {p.preavviso_disdetta} giorni sulla scadenza del "
                     f"{p.data_scadenza:%d/%m/%Y}", link, f"polizza-{p.id}-disdetta-{termine:%Y%m%d}")

    titoli = Title.query.filter(Title.stato == "da_incassare", Title.premio_lordo > 0).all()
    for t in titoli:
        link = url_for("policies.detail", policy_id=t.policy_id) + "#titoli"
        nome = f"{t.cliente.ragione_sociale} · polizza {t.polizza.numero_polizza}"
        aggiungi(t.data_effetto, "rata", f"Rata {t.polizza.numero_polizza} da incassare",
                 f"{nome}: {t.tipo_label} di {formatta_euro(t.premio_lordo)}",
                 link, f"titolo-{t.id}-effetto-{t.data_effetto:%Y%m%d}")
        # Sospensione solo per le rate già scadute: per quelle future basta la rata.
        if t.tipo != "perfezionamento" and t.data_effetto <= date.today() and t.data_sospensione != date.max:
            aggiungi(t.data_sospensione + timedelta(days=1), "sospensione",
                     f"Copertura sospesa se non pagata: {t.polizza.numero_polizza}",
                     f"{nome}: rata del {t.data_effetto:%d/%m/%Y} (art. 1901 c.c.)",
                     link, f"titolo-{t.id}-sospensione-{t.data_effetto:%Y%m%d}")

    for f in FollowUp.query.filter(FollowUp.stato == "aperto").all():
        aggiungi(f.data_scadenza, "followup", f.titolo, f"{f.cliente.ragione_sociale} · {f.tipo_label}",
                 url_for("clients.detail", client_id=f.client_id) + "#followup",
                 f"followup-{f.id}-{f.data_scadenza:%Y%m%d}")

    for s in Claim.query.filter(Claim.stato.in_(CLAIM_OPEN_STATUSES), Claim.data_denuncia.is_(None)).all():
        termine = s.data_evento + timedelta(days=GIORNI_DENUNCIA_SINISTRO)
        aggiungi(termine, "denuncia", f"Denuncia sinistro {s.numero} alla compagnia",
                 f"{s.cliente.ragione_sociale}: evento del {s.data_evento:%d/%m/%Y} (art. 1913 c.c.)",
                 url_for("claims.detail", claim_id=s.id), f"sinistro-{s.id}-denuncia-{termine:%Y%m%d}")

    for c in Client.query.filter(
        (Client.documento_scadenza.isnot(None)) | (Client.data_adeguatezza.isnot(None))
    ).all():
        link = url_for("clients.detail", client_id=c.id)
        aggiungi(c.documento_scadenza, "documento", f"Scade il documento di {c.ragione_sociale}",
                 "Richiedere il documento d'identità aggiornato (antiriciclaggio).", link,
                 f"cliente-{c.id}-documento-{c.documento_scadenza:%Y%m%d}" if c.documento_scadenza else "")
        scad = c.adeguatezza_scadenza
        aggiungi(scad, "adeguatezza", f"Rinnovare il questionario di {c.ragione_sociale}",
                 "Questionario di adeguatezza (IVASS Reg. 40/2018) oltre i 12 mesi.", link,
                 f"cliente-{c.id}-adeguatezza-{scad:%Y%m%d}" if scad else "")

    eventi.sort(key=lambda e: (e.data, list(TIPI_EVENTO).index(e.tipo), e.titolo))
    return eventi


# ----------------------------------------------------------------------
# Esportazione iCalendar (RFC 5545)
# ----------------------------------------------------------------------
def _ics_testo(valore: str) -> str:
    return (
        valore.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "")
    )


def _ics_piega(riga: str) -> list[str]:
    """Spezza le righe oltre 75 ottetti (continuazione con uno spazio)."""
    parti, corrente = [], ""
    for carattere in riga:
        limite = 75 if not parti else 74
        if len((corrente + carattere).encode("utf-8")) > limite:
            parti.append(corrente)
            corrente = carattere
        else:
            corrente += carattere
    parti.append(corrente)
    return [parti[0]] + [" " + p for p in parti[1:]]


def esporta_ics(eventi: list[Evento], base_url: str, nome_calendario: str) -> str:
    adesso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    righe = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Gestionale Assicurativo//Scadenzario//IT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_testo(nome_calendario)}",
    ]
    for e in eventi:
        righe += [
            "BEGIN:VEVENT",
            f"UID:{e.uid}@gestionale-assicurativo",
            f"DTSTAMP:{adesso}",
            f"DTSTART;VALUE=DATE:{e.data:%Y%m%d}",
            f"DTEND;VALUE=DATE:{e.data + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ics_testo(e.titolo)}",
            f"DESCRIPTION:{_ics_testo(e.etichetta + ' — ' + e.dettaglio)}",
            f"CATEGORIES:{_ics_testo(e.etichetta)}",
            f"URL:{base_url.rstrip('/')}{e.link}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    righe.append("END:VCALENDAR")
    piegate = []
    for riga in righe:
        piegate.extend(_ics_piega(riga))
    return "\r\n".join(piegate) + "\r\n"
