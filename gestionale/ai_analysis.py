"""Analisi dei rischi assistita da AI (Claude) — opzionale.

Affianca il motore a regole (`risk_engine.py`) con un'analisi generata da un
modello Claude: interpreta descrizioni libere e propone coperture e spunti di
trattativa su misura del singolo cliente.

Richiede connessione a Internet, il pacchetto ``anthropic`` e una chiave API
(configurabili dalla pagina «Impostazioni» oppure via variabili d'ambiente
``ANTHROPIC_API_KEY`` / ``AI_MODELLO``). Se qualcosa manca, l'app continua a
funzionare normalmente con il solo motore a regole.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from .models import BRANCH_LABELS, Settings

DEFAULT_MODEL = "claude-opus-5"

# Schema dell'output richiesto al modello: garantisce una risposta strutturata
# e parsabile, coerente con quella del motore a regole.
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "riepilogo": {
            "type": "string",
            "description": "Sintesi in 2-3 frasi del profilo di rischio del cliente.",
        },
        "rischi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "descrizione": {"type": "string"},
                    "severita": {"type": "string", "enum": ["alta", "media", "bassa"]},
                    "coperture": {"type": "array", "items": {"type": "string"}},
                    "spunto_trattativa": {
                        "type": "string",
                        "description": "Leva di vendita con esempio in terza persona e vantaggi.",
                    },
                },
                "required": ["nome", "descrizione", "severita", "coperture", "spunto_trattativa"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["riepilogo", "rischi"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "Sei un consulente assicurativo esperto del mercato italiano che affianca un "
    "intermediario. Analizza l'attività o la situazione del cliente e individua i "
    "principali rischi assicurabili, con le coperture (rami) consigliate e, per "
    "ciascun rischio, uno spunto di trattativa: una leva persuasiva con un breve "
    "esempio in terza persona e i vantaggi concreti da portare al cliente. "
    "Scrivi tutto in italiano, in modo pratico e specifico per il cliente descritto. "
    "Ordina i rischi dal più rilevante. È un supporto alla consulenza, non un parere legale."
)


def _env(name: str) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else None


def ai_config(settings: Settings | None = None) -> dict:
    """Configurazione effettiva dell'AI (Settings con override da ambiente)."""
    settings = settings or Settings.get()
    env_attiva = _env("AI_ATTIVA")
    attiva = (
        env_attiva.strip().lower() in ("1", "true", "yes", "si", "sì", "on")
        if env_attiva is not None
        else bool(settings.ai_attiva)
    )
    return {
        "attiva": attiva,
        "api_key": _env("ANTHROPIC_API_KEY") or settings.anthropic_api_key or "",
        "modello": _env("AI_MODELLO") or settings.ai_modello or DEFAULT_MODEL,
    }


def sdk_disponibile() -> bool:
    """True se il pacchetto ``anthropic`` è installato."""
    try:
        import anthropic  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def ai_disponibile(settings: Settings | None = None) -> bool:
    """True se l'AI è attiva, configurata e utilizzabile."""
    cfg = ai_config(settings)
    return bool(cfg["attiva"] and cfg["api_key"] and sdk_disponibile())


def _client_context(client) -> str:
    """Compone i dati strutturati del cliente da passare al modello."""
    righe = [f"Tipo cliente: {client.tipo_label}"]
    if client.settore:
        righe.append(f"Settore: {client.settore}")
    if client.professione:
        righe.append(f"Professione/Mansione: {client.professione}")
    if client.datore_lavoro:
        righe.append(f"Datore di lavoro: {client.datore_lavoro}")
    if client.numero_dipendenti is not None:
        righe.append(f"Dipendenti: {client.numero_dipendenti}")
    if client.fatturato_annuo:
        righe.append(f"Fatturato annuo: € {client.fatturato_annuo:,.0f}")
    attive = [p for p in client.polizze if p.stato in ("attiva", "in_rinnovo")]
    if attive:
        rami = ", ".join(sorted({BRANCH_LABELS.get(p.ramo, p.ramo) for p in attive}))
        righe.append(f"Coperture già attive: {rami}")
    return "\n".join(righe)


def analizza_cliente_ai(client, description: str, settings: Settings | None = None) -> dict:
    """Esegue l'analisi AI. Ritorna il dizionario dei risultati.

    Solleva ``RuntimeError`` con un messaggio comprensibile in caso di problemi
    (pacchetto assente, chiave mancante, errore di rete o risposta non valida).
    """
    settings = settings or Settings.get()
    cfg = ai_config(settings)
    if not cfg["attiva"]:
        raise RuntimeError("L'analisi AI è disattivata: attivala dalle Impostazioni.")
    if not cfg["api_key"]:
        raise RuntimeError("Chiave API Anthropic mancante: inseriscila nelle Impostazioni.")
    try:
        import anthropic
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Il pacchetto 'anthropic' non è installato. Esegui: pip install anthropic"
        ) from exc

    testo = (description or "").strip()
    contesto = _client_context(client)
    prompt = (
        f"Dati del cliente:\n{contesto}\n\n"
        f"Descrizione dell'attività / situazione:\n{testo}\n\n"
        "Individua i rischi assicurabili con coperture consigliate e spunti di trattativa."
    )

    try:
        cli = anthropic.Anthropic(api_key=cfg["api_key"], timeout=60.0)
        response = cli.messages.create(
            model=cfg["modello"],
            max_tokens=8000,
            system=_SYSTEM_PROMPT,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA},
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — mostriamo l'errore all'utente
        raise RuntimeError(f"Chiamata all'AI non riuscita: {exc}") from exc

    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("Il modello ha rifiutato la richiesta per motivi di sicurezza.")

    # Con output strutturato la risposta contiene un blocco di testo con il JSON.
    testo_json = next(
        (b.text for b in response.content if getattr(b, "type", None) == "text"), None
    )
    if not testo_json:
        raise RuntimeError("Risposta dell'AI vuota o non nel formato atteso.")
    try:
        dati = json.loads(testo_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Risposta dell'AI non in formato JSON valido.") from exc

    dati["fonte"] = "ai"
    dati["modello"] = cfg["modello"]
    dati["generata_il"] = datetime.utcnow().isoformat(timespec="seconds")
    dati.setdefault("rischi", [])
    dati["sintesi"] = {"rischi_rilevati": len(dati["rischi"])}
    return dati
