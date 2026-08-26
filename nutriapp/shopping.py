"""Lista della spesa generata dal piano e collegamenti ai carrelli online.

Il piano sa già quanti grammi di ogni alimento servono in una settimana: qui i
grammi vengono sommati, raggruppati per reparto e trasformati in quantità
comprensibili («1,2 kg», «3 confezioni»). Ogni riga porta con sé un termine di
ricerca in italiano con cui aprire il carrello di Glovo, Everli, Carrefour e
compagnia: nessuna integrazione da autorizzare, solo un link di ricerca.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import FornitoreSpesa, GIORNI


@dataclass
class RigaSpesa:
    alimento_id: int | None
    etichetta: str
    termine: str
    categoria: str
    grammi: float = 0.0
    porzioni: float = 0.0
    porzione_etichetta: str = ""
    giorni: set[int] = field(default_factory=set)
    ricette: set[str] = field(default_factory=set)

    @property
    def quantita(self) -> str:
        """Quantità leggibile: grammi sotto il chilo, chili sopra."""
        if self.grammi >= 1000:
            return f"{self.grammi / 1000:.1f}".replace(".", ",") + " kg"
        return f"{self.grammi:.0f} g"

    @property
    def dettaglio_porzioni(self) -> str:
        if not self.porzioni or not self.porzione_etichetta:
            return ""
        numero = f"{self.porzioni:g}".replace(".", ",")
        return f"{numero} × {self.porzione_etichetta}"

    @property
    def giorni_etichetta(self) -> str:
        if len(self.giorni) >= 7:
            return "tutti i giorni"
        return ", ".join(GIORNI[i][:3] for i in sorted(self.giorni))


@dataclass
class GruppoSpesa:
    categoria: str
    righe: list[RigaSpesa] = field(default_factory=list)

    @property
    def peso_totale(self) -> float:
        return sum(r.grammi for r in self.righe)


def _chiave(voce_alimento) -> tuple:
    return ("alimento", voce_alimento.id)


def lista_spesa(piano, giorni: list[int] | None = None) -> tuple[list[GruppoSpesa], list[str]]:
    """Aggrega il piano in una lista della spesa.

    Ritorna (gruppi per reparto, voci da aggiungere a mano). Le ricette inserite
    nel piano vengono espanse nei loro ingredienti, riproporzionati sul numero
    di porzioni previste.
    """
    accumulatore: dict[tuple, RigaSpesa] = {}
    manuali: list[str] = []

    for voce in piano.voci:
        if giorni is not None and voce.giorno not in giorni:
            continue

        if voce.alimento:
            _aggiungi(
                accumulatore,
                voce.alimento,
                grammi=(voce.alimento.porzione_g or 100) * (voce.porzioni or 1),
                porzioni=voce.porzioni or 1,
                giorno=voce.giorno,
            )
        elif voce.ricetta:
            ricetta = voce.ricetta
            fattore = (voce.porzioni or 1) / max(1, ricetta.porzioni or 1)
            for ing in ricetta.ingredienti:
                if ing.alimento and ing.grammi:
                    riga = _aggiungi(
                        accumulatore,
                        ing.alimento,
                        grammi=ing.grammi * fattore,
                        porzioni=0,
                        giorno=voce.giorno,
                    )
                    riga.ricette.add(ricetta.titolo)
                elif ing.testo:
                    testo = f"{ing.testo} (per «{ricetta.titolo}»)"
                    if testo not in manuali:
                        manuali.append(testo)
        elif voce.testo_libero:
            if voce.testo_libero not in manuali:
                manuali.append(voce.testo_libero)

    gruppi: dict[str, GruppoSpesa] = {}
    for riga in accumulatore.values():
        gruppi.setdefault(riga.categoria, GruppoSpesa(riga.categoria)).righe.append(riga)

    ordinati = sorted(gruppi.values(), key=lambda g: g.categoria.lower())
    for gruppo in ordinati:
        gruppo.righe.sort(key=lambda r: r.etichetta.lower())
    return ordinati, manuali


def _aggiungi(acc: dict, alimento, grammi: float, porzioni: float, giorno: int) -> RigaSpesa:
    chiave = _chiave(alimento)
    riga = acc.get(chiave)
    if riga is None:
        riga = RigaSpesa(
            alimento_id=alimento.id,
            etichetta=alimento.etichetta,
            termine=alimento.termine_spesa,
            categoria=alimento.categoria_it or alimento.categoria or "Altro",
            porzione_etichetta=alimento.porzione_breve,
        )
        acc[chiave] = riga
    riga.grammi += grammi
    riga.porzioni += porzioni
    riga.giorni.add(giorno)
    return riga


def fornitori_attivi() -> list[FornitoreSpesa]:
    return (
        FornitoreSpesa.query.filter_by(attivo=True)
        .order_by(FornitoreSpesa.ordine, FornitoreSpesa.nome)
        .all()
    )


def carrello_completo(fornitore: FornitoreSpesa, gruppi: list[GruppoSpesa]) -> str:
    """Link di ricerca con i primi termini della lista (i carrelli non accettano
    un ordine intero via URL: apriamo la ricerca sui prodotti principali)."""
    termini = [r.termine for g in gruppi for r in g.righe][:5]
    return fornitore.url_per(" ".join(termini))


def testo_lista(gruppi: list[GruppoSpesa], manuali: list[str], titolo: str = "Lista della spesa") -> str:
    """Versione testuale, per l'email al cliente o per copiarla nel telefono."""
    righe = [titolo, "=" * len(titolo), ""]
    for gruppo in gruppi:
        righe.append(f"{gruppo.categoria.upper()}")
        for r in gruppo.righe:
            dettaglio = f"  ({r.dettaglio_porzioni})" if r.dettaglio_porzioni else ""
            righe.append(f"  - {r.etichetta}: {r.quantita}{dettaglio}")
        righe.append("")
    if manuali:
        righe.append("DA AGGIUNGERE A MANO")
        for m in manuali:
            righe.append(f"  - {m}")
        righe.append("")
    return "\n".join(righe).strip()
