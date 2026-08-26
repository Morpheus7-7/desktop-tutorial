"""Motore di calcolo nutrizionale.

Riproduce (e amplia) le formule del foglio Excel di partenza: i valori degli
alimenti sono per 100 g, ogni voce del piano vale
``porzioni × grammi_porzione``, i totali di giornata sono la somma delle voci e
la settimana è la media dei sette giorni.

Un dettaglio ereditato dai dati USDA e mantenuto qui: **una cella vuota
significa «non analizzato», non «zero»**. Per questo ogni totale porta con sé
quante voci non avevano il dato, così l'interfaccia può dirlo invece di
mostrare un numero falsamente preciso.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ----------------------------------------------------------------------
# Nutrienti gestiti
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Nutriente:
    chiave: str
    etichetta: str
    unita: str
    gruppo: str  # "energia" | "macro" | "micro"
    limite: bool = False  # True = è un tetto da non superare, non un obiettivo
    decimali: int = 1


NUTRIENTI: tuple[Nutriente, ...] = (
    Nutriente("kcal", "Energia", "kcal", "energia", decimali=0),
    Nutriente("proteine", "Proteine", "g", "macro"),
    Nutriente("carboidrati", "Carboidrati", "g", "macro"),
    Nutriente("zuccheri", "Zuccheri", "g", "macro", limite=True),
    Nutriente("grassi", "Grassi", "g", "macro"),
    Nutriente("grassi_saturi", "Grassi saturi", "g", "macro", limite=True),
    Nutriente("fibre", "Fibre", "g", "macro"),
    Nutriente("sodio", "Sodio", "mg", "micro", limite=True, decimali=0),
    Nutriente("calcio", "Calcio", "mg", "micro", decimali=0),
    Nutriente("ferro", "Ferro", "mg", "micro"),
    Nutriente("magnesio", "Magnesio", "mg", "micro", decimali=0),
    Nutriente("potassio", "Potassio", "mg", "micro", decimali=0),
    Nutriente("zinco", "Zinco", "mg", "micro"),
    Nutriente("vit_c", "Vitamina C", "mg", "micro"),
    Nutriente("vit_d", "Vitamina D", "µg", "micro"),
    Nutriente("vit_b12", "Vitamina B12", "µg", "micro", decimali=2),
    Nutriente("folati", "Folati", "µg", "micro", decimali=0),
)

CHIAVI = tuple(n.chiave for n in NUTRIENTI)
MACRO = tuple(n for n in NUTRIENTI if n.gruppo == "macro")
MICRO = tuple(n for n in NUTRIENTI if n.gruppo == "micro")
PER_CHIAVE = {n.chiave: n for n in NUTRIENTI}

# Valori giornalieri di riferimento (modificabili per ogni piano).
RIFERIMENTI_DEFAULT: dict[str, float] = {
    "kcal": 1800,
    "proteine": 110,
    "carboidrati": 200,
    "zuccheri": 50,
    "grassi": 60,
    "grassi_saturi": 20,
    "fibre": 25,
    "sodio": 2000,
    "calcio": 800,
    "ferro": 14,
    "magnesio": 375,
    "potassio": 2000,
    "zinco": 10,
    "vit_c": 80,
    "vit_d": 5,
    "vit_b12": 2.5,
    "folati": 200,
}

# Kcal per grammo, per la ripartizione dei macronutrienti.
KCAL_PER_GRAMMO = {"proteine": 4, "carboidrati": 4, "grassi": 9}


# ----------------------------------------------------------------------
# Struttura dei totali
# ----------------------------------------------------------------------
@dataclass
class Totali:
    """Somma di nutrienti, con memoria di quanti dati mancavano."""

    valori: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in CHIAVI})
    mancanti: dict[str, int] = field(default_factory=lambda: {k: 0 for k in CHIAVI})
    voci: int = 0

    def somma(self, altro: "Totali") -> None:
        for k in CHIAVI:
            self.valori[k] += altro.valori.get(k, 0.0)
            self.mancanti[k] += altro.mancanti.get(k, 0)
        self.voci += altro.voci

    def get(self, chiave: str) -> float:
        return self.valori.get(chiave, 0.0)

    def parziale(self, chiave: str) -> bool:
        """True se almeno una voce non aveva il dato: il totale è sottostimato."""
        return self.mancanti.get(chiave, 0) > 0

    def scala(self, fattore: float) -> "Totali":
        return Totali(
            valori={k: v * fattore for k, v in self.valori.items()},
            mancanti=dict(self.mancanti),
            voci=self.voci,
        )

    def arrotondati(self) -> dict[str, float]:
        return {k: round(v, PER_CHIAVE[k].decimali) for k, v in self.valori.items()}


def totali_vuoti() -> Totali:
    return Totali()


# ----------------------------------------------------------------------
# Calcolo per alimento / ricetta / voce di piano
# ----------------------------------------------------------------------
def nutrienti_alimento(alimento, grammi: float) -> Totali:
    """Nutrienti di ``grammi`` grammi di un alimento (i valori sono per 100 g)."""
    t = Totali(voci=1)
    fattore = (grammi or 0) / 100.0
    for k in CHIAVI:
        valore = getattr(alimento, k, None)
        if valore is None:
            t.mancanti[k] = 1
        else:
            t.valori[k] = float(valore) * fattore
    return t


def nutrienti_ricetta(ricetta) -> tuple[Totali, Totali]:
    """(totale ricetta, per porzione). Gli ingredienti liberi non contano."""
    totale = Totali()
    for ing in ricetta.ingredienti:
        if ing.alimento and ing.grammi:
            totale.somma(nutrienti_alimento(ing.alimento, ing.grammi))
        elif not ing.alimento:
            # ingrediente scritto a mano: nessun valore nutrizionale disponibile
            for k in CHIAVI:
                totale.mancanti[k] += 1
            totale.voci += 1
    porzioni = max(1, ricetta.porzioni or 1)
    return totale, totale.scala(1 / porzioni)


def nutrienti_voce(voce) -> Totali:
    """Nutrienti di una riga del piano (alimento, ricetta o testo libero)."""
    if voce.alimento:
        grammi = (voce.alimento.porzione_g or 100) * (voce.porzioni or 1)
        return nutrienti_alimento(voce.alimento, grammi)
    if voce.ricetta:
        _, per_porzione = nutrienti_ricetta(voce.ricetta)
        return per_porzione.scala(voce.porzioni or 1)
    # Testo libero: nessun dato, ma lo segnaliamo come mancante.
    t = Totali(voci=1)
    for k in CHIAVI:
        t.mancanti[k] = 1
    return t


# ----------------------------------------------------------------------
# Compatibilità con il tipo di dieta
# ----------------------------------------------------------------------
_REGOLE_DIETA = {
    "Vegana": ("vegan", "non è vegano"),
    "Vegetariana": ("vegetariano", "non è vegetariano"),
    "Senza glutine": ("senza_glutine", "contiene glutine"),
    "Senza lattosio": ("senza_lattosio", "contiene lattosio"),
}


def conflitto_dieta(alimento, tipo_dieta: str | None) -> str | None:
    """Motivo del conflitto con la dieta scelta, oppure None se compatibile.

    Il valore ``None`` sul flag significa «non verificato» nel dato di
    partenza: lo segnaliamo come dubbio, non come errore.
    """
    if alimento is None or not tipo_dieta:
        return None
    regola = _REGOLE_DIETA.get(tipo_dieta)
    if not regola:
        return None
    campo, motivo = regola
    valore = getattr(alimento, campo, None)
    if valore is False:
        return motivo
    if valore is None:
        return "da verificare"
    return None


def conflitto_voce(voce, tipo_dieta: str | None) -> str | None:
    if voce.alimento:
        return conflitto_dieta(voce.alimento, tipo_dieta)
    if voce.ricetta:
        for ing in voce.ricetta.ingredienti:
            motivo = conflitto_dieta(ing.alimento, tipo_dieta)
            if motivo and motivo != "da verificare":
                return f"{ing.etichetta}: {motivo}"
    return None


# ----------------------------------------------------------------------
# Semafori
# ----------------------------------------------------------------------
def stato_kcal(valore: float, target: float | None) -> str:
    """'ok' entro il 5% dal target, 'attenzione' entro il 12%, altrimenti 'fuori'."""
    if not target:
        return "neutro"
    scarto = abs(valore - target) / target
    if scarto <= 0.05:
        return "ok"
    if scarto <= 0.12:
        return "attenzione"
    return "fuori"


def stato_copertura(percentuale: float | None, limite: bool = False) -> str:
    """Verde ≥ 90% del riferimento, rosso < 70%. Per i tetti la logica si inverte."""
    if percentuale is None:
        return "neutro"
    if limite:
        if percentuale <= 1.0:
            return "ok"
        return "attenzione" if percentuale <= 1.2 else "fuori"
    if percentuale >= 0.9:
        return "ok"
    return "attenzione" if percentuale >= 0.7 else "fuori"


CLASSE_BOOTSTRAP = {
    "ok": "success",
    "attenzione": "warning",
    "fuori": "danger",
    "neutro": "secondary",
}


# ----------------------------------------------------------------------
# Analisi completa di un piano
# ----------------------------------------------------------------------
def ripartizione_macro(totali: Totali) -> dict[str, float]:
    """Percentuale di calorie da proteine, carboidrati e grassi."""
    contributi = {k: totali.get(k) * kcal for k, kcal in KCAL_PER_GRAMMO.items()}
    somma = sum(contributi.values())
    if somma <= 0:
        return {k: 0.0 for k in KCAL_PER_GRAMMO}
    return {k: round(v / somma * 100, 1) for k, v in contributi.items()}


def analisi_piano(piano) -> dict:
    """Analisi giorno per giorno + medie settimanali + copertura dei riferimenti."""
    from .models import GIORNI, PASTI

    riferimenti = piano.riferimenti
    target = piano.target_kcal or riferimenti.get("kcal")

    giorni = []
    indice_oggi = piano.indice_giorno_oggi()
    settimana = Totali()
    conflitti: list[dict] = []
    giorni_con_voci = 0

    for indice, nome_giorno in enumerate(GIORNI):
        voci = piano.voci_giorno(indice)
        totali_giorno = Totali()
        pasti = []
        for nome_pasto in PASTI:
            del_pasto = [v for v in voci if v.pasto == nome_pasto]
            if not del_pasto:
                continue
            totali_pasto = Totali()
            righe = []
            for voce in sorted(del_pasto, key=lambda v: v.ordine):
                t = nutrienti_voce(voce)
                totali_pasto.somma(t)
                motivo = conflitto_voce(voce, piano.tipo_dieta)
                if motivo:
                    conflitti.append(
                        {"giorno": nome_giorno, "pasto": nome_pasto, "voce": voce, "motivo": motivo}
                    )
                righe.append({"voce": voce, "totali": t, "conflitto": motivo})
            totali_giorno.somma(totali_pasto)
            pasti.append({"nome": nome_pasto, "righe": righe, "totali": totali_pasto})

        if totali_giorno.voci:
            giorni_con_voci += 1
            settimana.somma(totali_giorno)

        kcal = totali_giorno.get("kcal")
        giorni.append(
            {
                "indice": indice,
                "nome": nome_giorno,
                "pasti": pasti,
                "totali": totali_giorno,
                "kcal": round(kcal),
                "perc_target": round(kcal / target * 100) if target else None,
                "stato": stato_kcal(kcal, target) if totali_giorno.voci else "neutro",
                "macro": ripartizione_macro(totali_giorno),
                "vuoto": not totali_giorno.voci,
                "oggi": indice == indice_oggi,
            }
        )

    divisore = giorni_con_voci or 1
    medie = settimana.scala(1 / divisore)

    copertura = []
    for nutriente in NUTRIENTI:
        riferimento = riferimenti.get(nutriente.chiave)
        valore = medie.get(nutriente.chiave)
        perc = (valore / riferimento) if riferimento else None
        copertura.append(
            {
                "nutriente": nutriente,
                "valore": round(valore, nutriente.decimali),
                "riferimento": riferimento,
                "percentuale": round(perc * 100) if perc is not None else None,
                "stato": stato_copertura(perc, nutriente.limite),
                "parziale": medie.parziale(nutriente.chiave),
            }
        )

    return {
        "giorni": giorni,
        "giorni_compilati": giorni_con_voci,
        "medie": medie,
        "media_kcal": round(medie.get("kcal")),
        "target": target,
        "stato_media": stato_kcal(medie.get("kcal"), target) if giorni_con_voci else "neutro",
        "macro_medi": ripartizione_macro(medie),
        "copertura": copertura,
        "conflitti": conflitti,
        "riferimenti": riferimenti,
    }


# ----------------------------------------------------------------------
# Fabbisogno energetico stimato
# ----------------------------------------------------------------------
LIVELLI_ATTIVITA = [
    ("sedentario", "Sedentario (poco o nessun esercizio)", 1.2),
    ("leggero", "Leggermente attivo (1-3 giorni a settimana)", 1.375),
    ("moderato", "Moderatamente attivo (3-5 giorni)", 1.55),
    ("intenso", "Molto attivo (6-7 giorni)", 1.725),
    ("atleta", "Attività molto intensa o lavoro fisico", 1.9),
]


def metabolismo_basale(sesso: str | None, peso_kg: float, altezza_cm: float, eta: int) -> float | None:
    """Metabolismo basale con l'equazione di Mifflin-St Jeor."""
    if not (peso_kg and altezza_cm and eta):
        return None
    base = 10 * peso_kg + 6.25 * altezza_cm - 5 * eta
    if (sesso or "").upper().startswith("M"):
        return round(base + 5)
    return round(base - 161)


def fabbisogno_stimato(assistito, livello: str = "leggero") -> dict | None:
    """Stima di BMR e fabbisogno giornaliero per l'assistito, se i dati bastano."""
    bmr = metabolismo_basale(
        assistito.sesso, assistito.peso_attuale, assistito.altezza_cm, assistito.eta or 0
    )
    if bmr is None:
        return None
    fattore = next((f for k, _, f in LIVELLI_ATTIVITA if k == livello), 1.375)
    tdee = round(bmr * fattore)
    return {
        "bmr": bmr,
        "livello": livello,
        "fattore": fattore,
        "tdee": tdee,
        "dimagrimento": round(tdee * 0.8),
        "mantenimento": tdee,
        "aumento": round(tdee * 1.12),
    }
