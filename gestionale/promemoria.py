"""Promemoria di Windows: cosa annunciare e avvio automatico con Windows.

L'icona vicino all'orologio (``run_desktop.py``) chiede qui, ogni tanto, i
follow-up da fare oggi o in ritardo e le polizze in scadenza, e mostra una
notifica di Windows solo quando compare qualcosa di nuovo. Le letture non
modificano il database: con il programma chiuso nella barra l'archivio può
essere aperto sull'altro PC.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

NOME_AVVIO = "Deal Combined"
CHIAVE_AVVIO = r"Software\Microsoft\Windows\CurrentVersion\Run"
PARAMETRO_SILENZIOSO = "--avvio-silenzioso"
GIORNI_SCADENZA = 7
CONTROLLO_OGNI = 15 * 60


def elementi_di_oggi(oggi: date | None = None) -> list[dict]:
    """Follow-up aperti con scadenza fino a oggi e polizze attive in scadenza
    nei prossimi giorni. Da chiamare dentro un app context."""
    from .models import FollowUp, Policy

    oggi = oggi or date.today()
    elementi = []
    for f in (FollowUp.query.filter(FollowUp.stato == "aperto", FollowUp.data_scadenza <= oggi)
              .order_by(FollowUp.data_scadenza).all()):
        elementi.append({"chiave": f"f{f.id}", "tipo": "followup", "ritardo": f.data_scadenza < oggi,
                         "testo": f"{f.titolo} · {f.cliente.ragione_sociale}"})
    for p in (Policy.query.filter(Policy.stato.in_(("attiva", "in_rinnovo")),
                                  Policy.data_scadenza >= oggi,
                                  Policy.data_scadenza <= oggi + timedelta(days=GIORNI_SCADENZA))
              .order_by(Policy.data_scadenza).all()):
        elementi.append({"chiave": f"p{p.id}", "tipo": "polizza", "ritardo": False,
                         "testo": f"{p.cliente.ragione_sociale}: {p.compagnia} n. {p.numero_polizza} "
                                  f"scade il {p.data_scadenza:%d/%m}"})
    return elementi


def messaggio(elementi: list[dict]) -> tuple[str, str] | None:
    """Titolo e testo della notifica (breve: Windows ne mostra poche righe)."""
    if not elementi:
        return None
    followup = [e for e in elementi if e["tipo"] == "followup"]
    polizze = [e for e in elementi if e["tipo"] == "polizza"]
    parti = []
    if followup:
        ritardo = sum(e["ritardo"] for e in followup)
        parti.append(f"{len(followup)} follow-up da fare" + (f" ({ritardo} in ritardo)" if ritardo else ""))
    if polizze:
        parti.append(f"{len(polizze)} polizz{'a' if len(polizze) == 1 else 'e'} in scadenza")
    righe = [e["testo"] for e in elementi[:3]]
    if len(elementi) > 3:
        righe.append(f"… e altri {len(elementi) - 3}")
    return "Oggi: " + ", ".join(parti), "\n".join(righe)[:250]


class Annunciatore:
    """Ricorda cosa è già stato notificato oggi, per non ripetersi."""

    def __init__(self):
        self.giorno, self.visti = None, set()

    def novita(self, elementi: list[dict], oggi: date | None = None) -> tuple[str, str] | None:
        oggi = oggi or date.today()
        if oggi != self.giorno:
            self.giorno, self.visti = oggi, set()
        chiavi = {e["chiave"] for e in elementi}
        if not chiavi - self.visti:
            return None
        self.visti |= chiavi
        return messaggio(elementi)


# ----------------------------------------------------------------------
# Avvio con Windows (registro dell'utente, senza permessi da amministratore)
# ----------------------------------------------------------------------
def comando_avvio() -> str:
    eseguibile = sys.executable if getattr(sys, "frozen", False) else f'{sys.executable}" "{sys.argv[0]}'
    return f'"{eseguibile}" {PARAMETRO_SILENZIOSO}'


def avvio_automatico() -> bool | None:
    """True/False se attivo o no; None se non si può sapere (non Windows)."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHIAVE_AVVIO) as chiave:
            winreg.QueryValueEx(chiave, NOME_AVVIO)
        return True
    except OSError:
        return False


def imposta_avvio_automatico(attivo: bool) -> None:
    if sys.platform != "win32":
        raise OSError("L'avvio automatico si imposta solo su Windows.")
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHIAVE_AVVIO, 0, winreg.KEY_SET_VALUE) as chiave:
        if attivo:
            winreg.SetValueEx(chiave, NOME_AVVIO, 0, winreg.REG_SZ, comando_avvio())
        else:
            try:
                winreg.DeleteValue(chiave, NOME_AVVIO)
            except FileNotFoundError:
                pass
