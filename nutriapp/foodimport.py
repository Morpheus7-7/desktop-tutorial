"""Importazione del database alimenti nel database dell'applicazione.

I 322 alimenti arrivano da USDA FoodData Central (Foundation Foods, aprile
2026, pubblico dominio CC0): i valori nutrizionali sono riprodotti senza
modifiche. Quello che aggiungiamo è la traduzione in italiano del nome e del
reparto, più il termine con cui cercare il prodotto sui servizi di spesa.

I nomi non presenti nel dizionario restano in inglese e l'alimento viene
marcato «da verificare»: si correggono a mano dalla scheda alimento, una volta
sola, e restano corretti per sempre.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Alimento, db

DATA_DIR = Path(__file__).parent / "data"

_CAMPI_NUTRIENTI = (
    "kcal", "proteine", "carboidrati", "zuccheri", "grassi", "grassi_saturi", "fibre",
    "sodio", "calcio", "ferro", "magnesio", "potassio", "zinco", "vit_c", "vit_d",
    "vit_b12", "folati",
)


def _carica(nome_file: str):
    percorso = DATA_DIR / nome_file
    if not percorso.exists():
        return None
    with percorso.open(encoding="utf-8") as f:
        return json.load(f)


def traduci_nome(nome: str, heads: dict, qualifiers: dict) -> tuple[str | None, str | None]:
    """(nome italiano, termine per la spesa). (None, None) se non sappiamo tradurre.

    Il nome USDA è «testa, specifica, specifica»: traduciamo la testa dal
    dizionario e le specifiche una per una, lasciando in inglese quelle che non
    conosciamo invece di inventarle.
    """
    parti = [p.strip() for p in (nome or "").split(",") if p.strip()]
    if not parti:
        return None, None
    testa_it = heads.get(parti[0])
    if not testa_it:
        return None, None
    minuscole = {chiave.lower(): valore for chiave, valore in qualifiers.items()}
    specifiche = [minuscole.get(p.lower(), p) for p in parti[1:]]
    nome_it = ", ".join([testa_it] + specifiche)
    return nome_it[0].upper() + nome_it[1:], testa_it


def traduci_porzione(testo: str | None, porzioni: dict) -> str | None:
    """«1 cup (chopped) (76 g)» → «1 tazza (tritato) (76 g)».

    Sostituisce parola per parola, lasciando in inglese quello che il
    dizionario non copre: meglio un'etichetta mista che una inventata.
    """
    if not testo:
        return testo
    tradotto = testo
    # prima le espressioni di più parole, altrimenti la singola le spezzerebbe
    for inglese in sorted(porzioni, key=len, reverse=True):
        tradotto = re.sub(
            rf"\b{re.escape(inglese)}\b", porzioni[inglese], tradotto, flags=re.IGNORECASE
        )
    return tradotto


def importa_alimenti(forza: bool = False) -> int:
    """Carica gli alimenti mancanti. Ritorna quanti ne ha inseriti.

    È idempotente: gli alimenti già presenti (stesso FDC ID) non vengono
    toccati, così le correzioni fatte a mano non si perdono a ogni avvio.
    """
    dati = _carica("foods.json")
    if not dati:
        return 0

    dizionari = _carica("traduzioni.json") or {}
    heads = dizionari.get("heads", {})
    qualifiers = dizionari.get("qualifiers", {})
    categorie = dizionari.get("categorie", {})
    porzioni = dizionari.get("porzioni", {})

    esistenti = {a.fdc_id for a in Alimento.query.with_entities(Alimento.fdc_id).all()}
    inseriti = 0

    for riga in dati:
        fdc_id = riga.get("fdc_id")
        if fdc_id and fdc_id in esistenti and not forza:
            continue

        nome_it, termine = traduci_nome(riga.get("nome", ""), heads, qualifiers)
        alimento = Alimento(
            fdc_id=fdc_id,
            nome=riga.get("nome"),
            nome_it=nome_it,
            categoria=riga.get("categoria"),
            categoria_it=categorie.get(riga.get("categoria"), riga.get("categoria")),
            spesa_query=termine,
            porzione_nome=traduci_porzione(riga.get("porzione_nome"), porzioni),
            porzione_g=riga.get("porzione_g") or 100,
            vegan=riga.get("vegan"),
            vegetariano=riga.get("vegetariano"),
            senza_glutine=riga.get("senza_glutine"),
            senza_lattosio=riga.get("senza_lattosio"),
            fonte_porzione=riga.get("fonte_porzione"),
            # «da verificare» = porzione stimata, flag di dieta incerto o nome
            # ancora in inglese: tutte cose da guardare prima di darle al cliente.
            da_verificare=bool(riga.get("review")) or nome_it is None,
        )
        for campo in _CAMPI_NUTRIENTI:
            setattr(alimento, campo, riga.get(campo))
        db.session.add(alimento)
        inseriti += 1

    if inseriti:
        db.session.commit()
    return inseriti


def importa_dispensa_italiana() -> int:
    """Aggiunge gli alimenti quotidiani che il set USDA non copre.

    Vengono creati **senza valori nutrizionali**: qui non si inventano numeri.
    Sono comunque subito utilizzabili nel piano e nella lista della spesa, e
    restano marcati «da completare» finché la nutrizionista non inserisce i
    valori della propria fonte di riferimento.
    """
    dati = _carica("alimenti_italia.json")
    if not dati:
        return 0

    esistenti = {a.nome_it for a in Alimento.query.with_entities(Alimento.nome_it).all()}
    inseriti = 0
    for riga in dati.get("alimenti", []):
        nome = riga.get("nome_it")
        if not nome or nome in esistenti:
            continue
        db.session.add(
            Alimento(
                nome=nome,
                nome_it=nome,
                categoria=riga.get("categoria_it"),
                categoria_it=riga.get("categoria_it"),
                spesa_query=nome.split(",")[0].strip(),
                porzione_nome=riga.get("porzione_nome"),
                porzione_g=riga.get("porzione_g") or 100,
                vegan=riga.get("vegan"),
                vegetariano=riga.get("vegetariano"),
                senza_glutine=riga.get("senza_glutine"),
                senza_lattosio=riga.get("senza_lattosio"),
                fonte_porzione="dispensa italiana",
                da_verificare=True,
            )
        )
        inseriti += 1

    if inseriti:
        db.session.commit()
    return inseriti


def settimana_esempio() -> list[dict]:
    """La settimana bilanciata già pronta del foglio originale (per il seed)."""
    return _carica("sample_week.json") or []
