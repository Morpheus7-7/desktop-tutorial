"""PDF delle schede compilate (ReportLab).

Il PDF è costruito dai dati strutturati della scheda (sezioni, campi,
valori), non dall'HTML: esce identico su ogni PC, senza browser.
"""
from __future__ import annotations

import io
import re
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

VERDE = colors.HexColor("#1d3b30")
INCHIOSTRO = colors.HexColor("#16211b")
ATTENUATO = colors.HexColor("#4d5c54")
FILETTO = colors.HexColor("#93a39a")

_base = getSampleStyleSheet()
STILI = {
    "titolo": ParagraphStyle("titolo", parent=_base["Title"], fontName="Helvetica-Bold", fontSize=16,
                             leading=20, alignment=0, textColor=INCHIOSTRO, spaceAfter=2),
    "marchio": ParagraphStyle("marchio", fontName="Helvetica", fontSize=11, textColor=VERDE, alignment=TA_RIGHT),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=9, textColor=ATTENUATO, leading=12),
    "sezione": ParagraphStyle("sezione", fontName="Helvetica-Bold", fontSize=10, textColor=VERDE,
                              leading=13, spaceBefore=10, spaceAfter=4),
    "etichetta": ParagraphStyle("etichetta", fontName="Helvetica", fontSize=9, textColor=ATTENUATO, leading=11),
    "valore": ParagraphStyle("valore", fontName="Helvetica-Bold", fontSize=9.5, textColor=INCHIOSTRO, leading=12),
    "domanda": ParagraphStyle("domanda", fontName="Helvetica", fontSize=9, textColor=ATTENUATO, leading=11, spaceBefore=4),
    "risposta": ParagraphStyle("risposta", fontName="Helvetica", fontSize=9.5, textColor=INCHIOSTRO, leading=13, spaceAfter=2),
    "cella": ParagraphStyle("cella", fontName="Helvetica", fontSize=8, textColor=INCHIOSTRO, leading=10),
    "cella_testa": ParagraphStyle("cella_testa", fontName="Helvetica-Bold", fontSize=8, textColor=INCHIOSTRO, leading=10),
}


class Casella(Flowable):
    """Casella di spunta disegnata: leggibile anche stampata in bianco e nero."""

    def __init__(self, spuntata: bool, lato: float = 3.4 * mm):
        super().__init__()
        self.spuntata, self.lato = spuntata, lato
        self.width = self.height = lato

    def draw(self):
        c, l = self.canv, self.lato
        c.setLineWidth(0.8)
        c.setStrokeColor(VERDE if self.spuntata else ATTENUATO)
        c.rect(0, 0, l, l, stroke=1, fill=0)
        if self.spuntata:
            c.setLineWidth(1.3)
            c.line(l * 0.2, l * 0.5, l * 0.42, l * 0.25)
            c.line(l * 0.42, l * 0.25, l * 0.82, l * 0.8)


def _p(testo, stile: str) -> Paragraph:
    return Paragraph(escape(str(testo or "")).replace("\n", "<br/>"), STILI[stile])


def nome_file(titolo: str, cliente: str, quando: date) -> str:
    base = f"{quando:%Y-%m-%d} {titolo} - {cliente}"
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", base)  # caratteri vietati nei nomi di file Windows
    return re.sub(r"\s+", " ", base).strip()[:150] + ".pdf"


def scheda_pdf(titolo: str, cliente: str, quando: date, consulente: str | None,
               struttura: dict, valori: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"{titolo} - {cliente}", author="Deal Combined")
    larghezza = A4[0] - 32 * mm
    storia = []

    testa = Table([[_p(titolo, "titolo"), Paragraph("<b>Deal</b> Combined", STILI["marchio"])]],
                  colWidths=[larghezza * 0.75, larghezza * 0.25])
    testa.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    storia += [testa, _p(f"Cliente: {cliente}   ·   Data: {quando:%d/%m/%Y}"
                          + (f"   ·   Consulente: {consulente}" if consulente else ""), "meta"), Spacer(1, 4 * mm)]

    def riga_sezione(titolo_sezione):
        return [_p(titolo_sezione.upper(), "sezione")]

    for si, sez in enumerate(struttura.get("sezioni", [])):
        blocco = riga_sezione(sez["titolo"])
        tipo = sez["tipo"]
        if tipo == "campi":
            righe = [[_p(etichetta, "etichetta"), _p(valori.get(f"s{si}c{ci}", ""), "valore")]
                     for ci, etichetta in enumerate(sez["campi"])]
            t = Table(righe, colWidths=[larghezza * 0.38, larghezza * 0.62])
            t.setStyle(TableStyle([("LINEBELOW", (1, 0), (1, -1), 0.4, FILETTO), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 3)]))
            blocco.append(t)
        elif tipo == "domande":
            for di, domanda in enumerate(sez["domande"]):
                blocco += [_p(domanda, "domanda"), _p(valori.get(f"s{si}d{di}", "") or "—", "risposta")]
        elif tipo == "check":
            celle = []
            for vi, voce in enumerate(sez["voci"]):
                celle += [Casella(bool(valori.get(f"s{si}v{vi}"))), _p(voce, "risposta")]
            righe = [celle[i:i + 4] + [""] * (4 - len(celle[i:i + 4])) for i in range(0, len(celle), 4)]
            meta = larghezza / 2 - 6 * mm
            t = Table(righe, colWidths=[6 * mm, meta, 6 * mm, meta])
            t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("TOPPADDING", (0, 0), (0, -1), 4.5), ("TOPPADDING", (2, 0), (2, -1), 4.5)]))
            blocco.append(t)
        elif tipo == "tabella":
            fisse = sez.get("righe_fisse")
            n = len(fisse) if fisse else sez.get("righe", 0)
            righe = [[_p(c, "cella_testa") for c in sez["colonne"]]]
            for ri in range(n):
                riga = []
                for ki, _ in enumerate(sez["colonne"]):
                    if fisse and ki == 0:
                        riga.append(_p(fisse[ri], "cella_testa"))
                    else:
                        riga.append(_p(valori.get(f"s{si}r{ri}k{ki}", ""), "cella"))
                if fisse or any(valori.get(f"s{si}r{ri}k{ki}") for ki in range(len(sez["colonne"]))):
                    righe.append(riga)  # nel PDF le righe libere vuote si omettono
            if len(righe) == 1:
                righe.append([_p("—", "cella")] + [""] * (len(sez["colonne"]) - 1))
            t = Table(righe, colWidths=[larghezza / len(sez["colonne"])] * len(sez["colonne"]), repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, FILETTO),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9efe8")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            blocco.append(t)
        storia.append(KeepTogether(blocco) if tipo != "tabella" else blocco[0])
        if tipo == "tabella":
            storia += blocco[1:]

    if valori.get("note"):
        storia += riga_sezione("Note") + [_p(valori["note"], "risposta")]

    def piede(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(ATTENUATO)
        canvas.drawString(16 * mm, 8 * mm, f"Deal Combined · {titolo} · {cliente}")
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Pagina {documento.page}")
        canvas.restoreState()

    doc.build(storia, onFirstPage=piede, onLaterPages=piede)
    return buf.getvalue()
