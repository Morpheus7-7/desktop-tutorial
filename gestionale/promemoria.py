"""Promemoria di Windows: cosa annunciare e avvio automatico con Windows.

L'icona vicino all'orologio (``run_desktop.py``) chiede qui, ogni tanto, i
follow-up da fare oggi o in ritardo, le polizze in scadenza e le rate da far
pagare (annuali e frazionate, anche arretrate), e mostra una
notifica di Windows solo quando compare qualcosa di nuovo. Le letture non
modificano il database: con il programma chiuso nella barra l'archivio può
essere aperto sull'altro PC.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta

NOME_AVVIO = "Deal Combined"
CHIAVE_AVVIO = r"Software\Microsoft\Windows\CurrentVersion\Run"
PARAMETRO_SILENZIOSO = "--avvio-silenzioso"
GIORNI_SCADENZA = 7
CONTROLLO_OGNI = 60  # i promemoria delle note hanno un orario preciso


def elementi_di_oggi(oggi: date | None = None, adesso: datetime | None = None) -> list[dict]:
    """Promemoria delle note arrivati all'ora, follow-up aperti con scadenza
    fino a oggi e polizze attive in scadenza nei prossimi giorni. Da
    chiamare dentro un app context."""
    from .models import FollowUp, Nota, Policy, Settings, Title
    from .titoli import rate_previste_portafoglio

    oggi = oggi or date.today()
    adesso = adesso or datetime.now()
    elementi = []
    for n in (Nota.query.filter(Nota.promemoria_fatto.is_(False), Nota.promemoria_il <= adesso,
                                Nota.promemoria_il >= datetime.combine(oggi, datetime.min.time()))
              .order_by(Nota.promemoria_il).all()):
        testo = f"{n.promemoria_il:%H:%M} {n.titolo}" + (f" · {n.cliente.ragione_sociale}" if n.cliente else "")
        elementi.append({"chiave": f"n{n.id}-{n.promemoria_il:%Y%m%d%H%M}", "tipo": "nota", "ritardo": False,
                         "testo": testo, "titolo": n.titolo})
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
    # Rate da far pagare: quietanze emesse non incassate (anche arretrate) e
    # rate del frazionamento non ancora emesse, entro i giorni di preavviso.
    try:
        preavviso = Settings.get().giorni_preavviso_rate
    except Exception:  # noqa: BLE001 - database non ancora aggiornato
        preavviso = GIORNI_SCADENZA
    limite = oggi + timedelta(days=preavviso)
    for t in (Title.query.filter(Title.stato == "da_incassare", Title.premio_lordo > 0, Title.data_effetto <= limite)
              .order_by(Title.data_effetto).all()):
        p = t.polizza
        if p is None or not p.attiva:
            continue
        elementi.append({"chiave": f"t{t.id}", "tipo": "rata", "ritardo": t.data_effetto < oggi,
                         "testo": f"{p.cliente.ragione_sociale}: rata {p.numero_polizza} "
                                  f"del {t.data_effetto:%d/%m} da incassare"})
    for r in rate_previste_portafoglio(oggi, limite):
        p = r["polizza"]
        elementi.append({"chiave": f"r{p.id}-{r['data']:%Y%m%d}", "tipo": "rata", "ritardo": False,
                         "testo": f"{p.cliente.ragione_sociale}: rata {r['numero']}/{r['totali']} "
                                  f"{p.numero_polizza} del {r['data']:%d/%m} da far pagare"})
    return elementi


def messaggio(elementi: list[dict], nuove: set | None = None) -> tuple[str, str] | None:
    """Titolo e testo della notifica (breve: Windows ne mostra poche righe).
    Un promemoria di una nota appena arrivato ha la precedenza."""
    if not elementi:
        return None
    note_nuove = [e for e in elementi if e["tipo"] == "nota" and (nuove is None or e["chiave"] in nuove)]
    if note_nuove:
        titolo = (f"Promemoria: {note_nuove[0]['titolo']}" if len(note_nuove) == 1
                  else f"{len(note_nuove)} promemoria")
        return titolo[:63], "\n".join(e["testo"] for e in note_nuove[:4])[:250]
    followup = [e for e in elementi if e["tipo"] == "followup"]
    polizze = [e for e in elementi if e["tipo"] == "polizza"]
    parti = []
    if followup:
        ritardo = sum(e["ritardo"] for e in followup)
        parti.append(f"{len(followup)} follow-up da fare" + (f" ({ritardo} in ritardo)" if ritardo else ""))
    if polizze:
        parti.append(f"{len(polizze)} polizz{'a' if len(polizze) == 1 else 'e'} in scadenza")
    rate = [e for e in elementi if e["tipo"] == "rata"]
    if rate:
        arretrate = sum(e["ritardo"] for e in rate)
        parti.append(f"{len(rate)} rat{'a' if len(rate) == 1 else 'e'} da incassare"
                     + (f" ({arretrate} arretrat{'a' if arretrate == 1 else 'e'})" if arretrate else ""))
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
        nuove = chiavi - self.visti
        if not nuove:
            return None
        self.visti |= chiavi
        return messaggio(elementi, nuove)


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
