"""Importazione di clienti e polizze da Excel (.xlsx) o CSV.

Si può partire dal modello scaricabile (fogli «Clienti» e «Polizze») oppure
da un proprio file: le intestazioni delle colonne vengono riconosciute anche
se scritte in modo diverso («P.IVA», «Partita IVA», «Ragione sociale»,
«Nome»…). Un foglio con solo polizze che indica il cliente per nome crea
anche i clienti mancanti.

Il flusso ha due passi: ``analizza`` legge il file e prepara l'anteprima
(nuovi, già presenti, errori riga per riga) senza toccare il database;
``importa`` scrive davvero. I clienti già presenti (stessa P.IVA, stesso
codice fiscale o stesso nome) non vengono sovrascritti: si completano solo i
campi vuoti. Le polizze già presenti (stesso numero e compagnia) si saltano.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, datetime

from .models import (
    BRANCH_LABELS, CLIENT_TYPES, PAYMENT_FREQUENCIES, POLICY_BRANCHES, POLICY_STATUSES, RUOLI_PERSONA,
    RUOLI_PERSONA_LABELS, Client, PersonaCollegata, Policy, db,
)

RIGHE_MASSIME = 20000
COLONNE_MASSIME = 80
ESEMPIO_CLIENTE = "Rossi Impianti S.r.l."
ESEMPIO_COMPAGNIA = "Compagnia Esempio"

# ----------------------------------------------------------------------
# Colonne: campo -> (intestazione del modello, altri nomi riconosciuti, tipo)
# ----------------------------------------------------------------------
COLONNE_CLIENTI = {
    "ragione_sociale": ("Ragione sociale (aziende)", ["ragione sociale", "cliente", "denominazione",
                        "nominativo", "nome e cognome", "nome cognome", "azienda", "contraente"], "testo"),
    "nome": ("Nome (persone)", ["nome persona"], "testo"),
    "cognome": ("Cognome (persone)", ["cognome persona"], "testo"),
    "tipo": ("Tipo", ["tipo cliente", "tipologia"], "tipo"),
    "referente": ("Referente", ["contatto", "persona di riferimento"], "testo"),
    "partita_iva": ("Partita IVA", ["p iva", "piva", "p iva cliente", "partita iva"], "piva"),
    "codice_fiscale": ("Codice fiscale", ["cf", "cod fiscale", "c f"], "cf"),
    "codice_ateco": ("Codice ATECO", ["ateco"], "testo"),
    "professione": ("Professione", ["attivita professionale"], "testo"),
    "datore_lavoro": ("Datore di lavoro", ["datore"], "testo"),
    "settore": ("Settore", ["settore attivita", "categoria"], "testo"),
    "indirizzo": ("Indirizzo", ["via", "sede"], "testo"),
    "citta": ("Città", ["comune", "localita", "citta"], "testo"),
    "cap": ("CAP", ["codice postale"], "cap"),
    "provincia": ("Provincia", ["prov", "pr"], "provincia"),
    "email": ("Email", ["e mail", "mail", "posta elettronica"], "testo"),
    "pec": ("PEC", ["email pec", "posta certificata"], "testo"),
    "telefono": ("Telefono", ["tel", "cellulare", "cell", "telefono cellulare", "mobile", "numero di telefono"], "testo"),
    "data_nascita": ("Data di nascita", ["nato il", "nata il", "data nascita", "nascita"], "data"),
    "luogo_nascita": ("Luogo di nascita", ["nato a", "nata a", "luogo nascita", "comune di nascita"], "testo"),
    "residenza_indirizzo": ("Indirizzo di residenza", ["residenza", "indirizzo residenza"], "testo"),
    "residenza_citta": ("Città di residenza", ["comune di residenza", "citta residenza"], "testo"),
    "residenza_cap": ("CAP residenza", ["cap di residenza"], "cap"),
    "residenza_provincia": ("Provincia residenza", ["provincia di residenza", "prov residenza"], "provincia"),
    "albo": ("Albo / Ordine", ["ordine", "ordine professionale", "albo professionale"], "testo"),
    "albo_provincia": ("Sede dell'ordine", ["provincia albo", "sede albo", "sede ordine"], "testo"),
    "albo_numero": ("N. iscrizione albo", ["numero albo", "n iscrizione", "iscrizione albo", "numero iscrizione",
                    "n albo"], "testo"),
    "albo_data_iscrizione": ("Data iscrizione albo", ["iscritto dal", "iscritta dal", "data iscrizione"], "data"),
    "numero_dipendenti": ("Numero dipendenti", ["dipendenti", "n dipendenti", "addetti"], "intero"),
    "fatturato_annuo": ("Fatturato annuo (€)", ["fatturato", "ricavi", "volume d affari"], "numero"),
    "descrizione_attivita": ("Descrizione attività", ["descrizione", "attivita"], "testo"),
    "note": ("Note", ["annotazioni", "osservazioni"], "testo"),
}

COLONNE_POLIZZE = {
    "cliente": ("Cliente (nome, P.IVA o codice fiscale)", ["cliente", "contraente", "ragione sociale", "nome",
                "assicurato", "nominativo"], "testo"),
    "compagnia": ("Compagnia", ["compagnia assicurativa", "assicuratore", "impresa", "agenzia compagnia"], "testo"),
    "numero_polizza": ("Numero polizza", ["polizza", "n polizza", "numero", "nr polizza", "num polizza"], "testo"),
    "ramo": ("Ramo", ["ramo polizza", "prodotto", "garanzia", "tipo polizza"], "ramo"),
    "massimale": ("Massimale (€)", ["massimale assicurato", "capitale", "somma assicurata"], "numero"),
    "premio_annuo": ("Premio annuo (€)", ["premio", "premio lordo", "premio annuale"], "numero"),
    "provvigione_perc": ("Provvigione %", ["provvigione", "provvigioni", "perc provvigione"], "percentuale"),
    "frazionamento": ("Frazionamento", ["rateazione", "pagamento"], "frazionamento"),
    "data_decorrenza": ("Decorrenza", ["data decorrenza", "effetto", "data effetto", "inizio"], "data"),
    "data_scadenza": ("Scadenza", ["data scadenza", "fine", "termine"], "data"),
    "tacito_rinnovo": ("Tacito rinnovo (sì/no)", ["tacito rinnovo", "rinnovo tacito", "tacito"], "booleano"),
    "stato": ("Stato", ["stato polizza"], "stato"),
    "note": ("Note", ["annotazioni", "osservazioni"], "testo"),
}

COLONNE_PERSONE = {
    "cliente": ("Cliente (nome, P.IVA o codice fiscale)", ["cliente", "societa", "azienda", "ragione sociale",
                "ditta"], "testo"),
    "piva_cliente": ("P.IVA del cliente", ["partita iva", "p iva", "piva", "p iva cliente"], "piva"),
    "ruolo": ("Ruolo", ["carica", "qualifica", "ruolo societario", "incarico"], "testo"),
    "nome": ("Nome", ["nome persona"], "testo"),
    "cognome": ("Cognome", ["cognome persona"], "testo"),
    "codice_fiscale": ("Codice fiscale", ["cf", "cod fiscale", "c f"], "cf"),
    "data_nascita": ("Data di nascita", ["nato il", "nata il", "data nascita", "nascita"], "data"),
    "luogo_nascita": ("Luogo di nascita", ["nato a", "nata a", "luogo nascita", "comune di nascita"], "testo"),
    "indirizzo": ("Indirizzo di residenza", ["indirizzo", "residenza", "via"], "testo"),
    "citta": ("Città", ["comune", "localita", "citta di residenza"], "testo"),
    "cap": ("CAP", ["codice postale"], "cap"),
    "provincia": ("Provincia", ["prov", "pr"], "provincia"),
    "email": ("Email", ["e mail", "mail"], "testo"),
    "telefono": ("Telefono", ["tel", "cellulare", "cell"], "testo"),
    "quota_perc": ("Quota %", ["quota", "quota partecipazione", "percentuale", "quota di partecipazione"], "percentuale"),
    "dal": ("In carica dal", ["data nomina", "nominato il", "dal"], "data"),
    "note": ("Note", ["annotazioni", "osservazioni"], "testo"),
}
ESEMPIO_PERSONA = ("Mario", "Rossi")

# Le colonne che identificano un cliente servono anche nel foglio polizze.
CLIENTE_IN_POLIZZE = {"partita_iva", "codice_fiscale"}


class FileNonValido(Exception):
    pass


def _norm(testo) -> str:
    """Minuscole, senza accenti né punteggiatura: «P.IVA» -> «p iva»."""
    testo = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", testo.lower()).strip()


def _mappa_intestazioni(intestazioni: list, colonne: dict) -> dict[int, str]:
    """Indice di colonna -> campo, riconoscendo le intestazioni più comuni."""
    alias = {}
    for campo, (etichetta, altri, _) in colonne.items():
        for nome in [etichetta, campo.replace("_", " "), *altri]:
            alias.setdefault(_norm(nome), campo)
    mappa, usati = {}, set()
    for i, intestazione in enumerate(intestazioni):
        campo = alias.get(_norm(intestazione))
        if campo and campo not in usati:
            mappa[i] = campo
            usati.add(campo)
    return mappa


# ----------------------------------------------------------------------
# Conversione dei valori
# ----------------------------------------------------------------------
def _testo(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)  # Excel trasforma 01234567890 in 1234567890.0
    if isinstance(v, (datetime, date)):
        return v.strftime("%d/%m/%Y")
    return re.sub(r"\s+", " ", str(v)).strip()


def _numero(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r"[€\s]|eur(o)?", "", str(v), flags=re.I).replace("%", "")
    if not t:
        return None
    if "," in t:  # formato italiano: 1.234,56
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")  # 1.200.000 -> 1200000
    return float(t)


_FORMATI_DATA = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d-%m-%y", "%Y/%m/%d")


def _data(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    t = str(v).strip().split(" ")[0]
    for formato in _FORMATI_DATA:
        try:
            return datetime.strptime(t, formato).date()
        except ValueError:
            continue
    raise ValueError


def _booleano(v) -> bool:
    return _norm(_testo(v)) in {"si", "s", "yes", "y", "x", "true", "vero", "1"}


def _scelta(v, voci: list[tuple[str, str]], predefinita: str, sinonimi: dict | None = None) -> tuple[str, bool]:
    """Codice dalla lista (accetta codice o etichetta). Restituisce
    (codice, riconosciuto)."""
    n = _norm(_testo(v))
    if not n:
        return predefinita, True
    for codice, etichetta in voci:
        if n in (_norm(codice), _norm(etichetta)):
            return codice, True
    for chiave, codice in (sinonimi or {}).items():
        if re.search(r"\b" + re.escape(chiave), n):
            return codice, True
    return predefinita, False


SINONIMI_RAMO = {
    "rc professionale": "rc_professionale", "rc prof": "rc_professionale",
    "rct": "rct_rco", "rco": "rct_rco", "rc prodott": "rc_prodotti", "inquinamento": "rc_ambientale",
    "incendio": "incendio", "all risk": "incendio", "furto": "furto", "rapina": "furto",
    "catastrofal": "catastrofali", "catnat": "catastrofali", "guasti": "guasti_macchine",
    "elettronic": "guasti_macchine", "cyber": "cyber", "infortun": "infortuni", "malattia": "malattia",
    "sanitari": "malattia", "rimborso spese": "malattia", "capofamiglia": "rc_capofamiglia",
    "vita privata": "rc_capofamiglia", "tcm": "vita", "caso morte": "vita", "vita": "vita",
    "previdenz": "previdenza", "pip": "previdenza", "fondo pension": "previdenza", "d o": "do", "amministrator": "do", "tutela": "tutela_legale",
    "trasport": "trasporti", "merci": "trasporti", "rca": "auto", "auto": "auto", "flott": "auto",
    "cauzion": "cauzioni", "fideiussion": "cauzioni", "credito": "credito", "key man": "key_man",
}
SINONIMI_TIPO = {"ditta": "azienda", "societ": "azienda", "impresa": "azienda", "srl": "azienda", "spa": "azienda",
                 "libero prof": "professionista", "privato": "dipendente", "dipendent": "dipendente"}


def _converti(campo: str, tipo: str, v, avvisi: list, errori: list, etichetta: str):
    try:
        if tipo == "testo":
            return _testo(v) or None
        if tipo == "piva":
            t = re.sub(r"\D", "", _testo(v).upper().removeprefix("IT"))
            if t and len(t) < 11:
                t = t.zfill(11)  # Excel toglie gli zeri iniziali
            if t and len(t) != 11:
                avvisi.append(f"{etichetta}: «{_testo(v)}» non ha 11 cifre")
                return _testo(v)[:11] or None
            return t or None
        if tipo == "cf":
            t = re.sub(r"\s", "", _testo(v)).upper()
            if t.isdigit() and len(t) < 11:
                t = t.zfill(11)  # CF numerico di una società
            if t and len(t) not in (11, 16):
                avvisi.append(f"{etichetta}: «{t}» non sembra un codice fiscale")
            return t[:16] or None
        if tipo == "cap":
            t = re.sub(r"\D", "", _testo(v))
            return t.zfill(5)[:5] if t else None
        if tipo == "provincia":
            t = _testo(v).upper()
            return t[:2] or None
        if tipo == "intero":
            n = _numero(v)
            return int(n) if n is not None else None
        if tipo == "numero":
            return _numero(v)
        if tipo == "percentuale":
            n = _numero(v)
            # Una cella Excel formattata come percentuale contiene 0,15 per 15%.
            if n is not None and isinstance(v, (int, float)) and 0 < n < 1:
                n = round(n * 100, 4)
            return n
        if tipo == "data":
            return _data(v)
        if tipo == "booleano":
            return _booleano(v)
    except (ValueError, TypeError):
        errori.append(f"{etichetta}: valore non valido «{_testo(v)}»")
        return None
    if tipo == "tipo":
        if not _testo(v):
            return None  # deciso dopo: azienda o persona, in base alle colonne compilate
        codice, ok = _scelta(v, CLIENT_TYPES, "azienda", SINONIMI_TIPO)
    elif tipo == "ramo":
        codice, ok = _scelta(v, POLICY_BRANCHES, "altro", SINONIMI_RAMO)
    elif tipo == "stato":
        codice, ok = _scelta(v, POLICY_STATUSES, "attiva")
    elif tipo == "frazionamento":
        codice, ok = _scelta(v, PAYMENT_FREQUENCIES, "annuale")
    else:  # pragma: no cover - tipo sconosciuto nella tabella delle colonne
        raise KeyError(tipo)
    if not ok:
        avvisi.append(f"{etichetta}: «{_testo(v)}» non riconosciuto, uso «{dict(_VOCI[tipo])[codice]}»")
    return codice


SINONIMI_RUOLO = {
    "amministratore unico": "amministratore_unico", "amm unico": "amministratore_unico",
    "amministratore delegato": "amministratore_delegato", "delegato": "amministratore_delegato",
    "presidente": "presidente_cda", "consigl": "consigliere", "legale rapp": "legale_rappresentante",
    "rappresentante legale": "legale_rappresentante", "soci": "socio", "procurat": "procuratore",
    "sindac": "sindaco", "revisor": "sindaco", "titolare effettivo": "titolare_effettivo",
    "beneficiario effettivo": "titolare_effettivo", "coniuge": "coniuge", "moglie": "coniuge", "marito": "coniuge",
    "convivente": "coniuge", "figli": "familiare", "padre": "familiare", "madre": "familiare",
    "familiar": "familiare", "amministratore": "amministratore_unico",
}
ABBREVIAZIONI_RUOLO = {"ad": "amministratore_delegato", "au": "amministratore_unico", "lr": "legale_rappresentante",
                       "pres": "presidente_cda", "cons": "consigliere"}


def _ruolo(testo: str | None) -> tuple[str, str | None]:
    """(codice del ruolo, testo libero se non riconosciuto)."""
    if not testo:
        return "altro", None
    n = _norm(testo)
    if n.replace(" ", "") in ABBREVIAZIONI_RUOLO:
        return ABBREVIAZIONI_RUOLO[n.replace(" ", "")], None
    codice, ok = _scelta(testo, RUOLI_PERSONA, "altro", SINONIMI_RUOLO)
    return (codice, None) if ok else ("altro", testo[:100])


_VOCI = {"tipo": CLIENT_TYPES, "ramo": POLICY_BRANCHES, "stato": POLICY_STATUSES, "frazionamento": PAYMENT_FREQUENCIES}


# ----------------------------------------------------------------------
# Lettura del file
# ----------------------------------------------------------------------
def _fogli_da_xlsx(dati: bytes) -> list[tuple[str, list[list]]]:
    from openpyxl import load_workbook

    try:
        libro = load_workbook(io.BytesIO(dati), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - zip rotto, formato .xls, ecc.
        raise FileNonValido("Il file non è un Excel .xlsx leggibile (i vecchi .xls vanno salvati come .xlsx).") from exc
    fogli = []
    try:
        for foglio in libro.worksheets:
            righe = []
            for riga in foglio.iter_rows(values_only=True, max_col=COLONNE_MASSIME):
                righe.append(list(riga))
                if len(righe) > RIGHE_MASSIME + 1:
                    raise FileNonValido(f"Il foglio «{foglio.title}» ha più di {RIGHE_MASSIME} righe.")
            fogli.append((foglio.title, righe))
    finally:
        libro.close()
    return fogli


def _fogli_da_csv(dati: bytes) -> list[tuple[str, list[list]]]:
    try:
        testo = dati.decode("utf-8-sig")
    except UnicodeDecodeError:
        testo = dati.decode("cp1252", errors="replace")  # CSV salvato da Excel italiano
    try:
        dialetto = csv.Sniffer().sniff(testo[:4096], delimiters=";,\t")
    except csv.Error:
        class dialetto(csv.excel):  # noqa: N801 - Excel italiano usa il punto e virgola
            delimiter = ";"
    righe = list(csv.reader(io.StringIO(testo), dialetto))
    if len(righe) > RIGHE_MASSIME + 1:
        raise FileNonValido(f"Il file ha più di {RIGHE_MASSIME} righe.")
    return [("CSV", righe)]


def _vuota(riga) -> bool:
    return all(c is None or str(c).strip() == "" for c in riga)


def _trova_intestazione(righe: list[list]) -> int:
    """Indice della riga di intestazione: la prima non vuota tra le prime 10
    (sopra possono esserci un titolo o delle note)."""
    migliore, punti = 0, -1
    for i, riga in enumerate(righe[:10]):
        if _vuota(riga):
            continue
        p = max(len(_mappa_intestazioni(riga, c)) for c in (COLONNE_CLIENTI, COLONNE_POLIZZE, COLONNE_PERSONE))
        if p > punti:
            migliore, punti = i, p
    return migliore


def _tipo_foglio(nome: str, intestazioni: list) -> str | None:
    n = _norm(nome)
    if n.startswith("istruzion") or n.startswith("valori"):
        return None
    if "polizz" in n:
        return "polizze"
    if any(x in n for x in ("ammin", "person", "soci", "esponent", "consigl", "familiar")):
        return "persone"
    if "client" in n or "anagraf" in n:
        return "clienti"
    campi_polizze = set(_mappa_intestazioni(intestazioni, COLONNE_POLIZZE).values())
    if {"compagnia", "numero_polizza"} <= campi_polizze:
        return "polizze"
    if {"ruolo", "cognome"} <= set(_mappa_intestazioni(intestazioni, COLONNE_PERSONE).values()):
        return "persone"
    if {"ragione_sociale", "cognome"} & set(_mappa_intestazioni(intestazioni, COLONNE_CLIENTI).values()):
        return "clienti"
    return None


# ----------------------------------------------------------------------
# Analisi (anteprima) e importazione
# ----------------------------------------------------------------------
def _chiave_nome(nome: str | None) -> str:
    return _norm(nome).replace(" ", "")


class _Indice:
    """Ritrova i clienti (del database e del file) per P.IVA, CF o nome."""

    def __init__(self):
        self.per_piva, self.per_cf, self.per_nome = {}, {}, {}
        self.codici = {}  # rif -> (P.IVA, CF) già noti
        for c in Client.query.all():
            self.aggiungi(("db", c.id), c.partita_iva, c.codice_fiscale, c.ragione_sociale)

    def aggiungi(self, rif, piva, cf, nome):
        noti = self.codici.get(rif, (None, None))
        self.codici[rif] = (noti[0] or piva, noti[1] or (cf.upper() if cf else None))
        if piva:
            self.per_piva.setdefault(piva, rif)
        if cf:
            self.per_cf.setdefault(cf.upper(), rif)
        if nome:
            self.per_nome.setdefault(_chiave_nome(nome), rif)

    def trova(self, piva=None, cf=None, nome=None):
        trovato = (piva and self.per_piva.get(piva)) or (cf and self.per_cf.get(cf.upper()))
        if trovato:
            return trovato
        per_nome = nome and self.per_nome.get(_chiave_nome(nome))
        if per_nome and not self.codici_in_conflitto(per_nome, piva, cf):
            return per_nome
        return None

    def codici_in_conflitto(self, rif, piva, cf) -> bool:
        """Stesso nome ma P.IVA o codice fiscale diversi: sono due persone
        (o aziende) diverse, non lo stesso cliente."""
        noti_piva, noti_cf = self.codici.get(rif, (None, None))
        return bool((piva and noti_piva and piva != noti_piva) or (cf and noti_cf and cf.upper() != noti_cf))

    def cerca_testo(self, testo: str):
        """Il campo «Cliente» delle polizze può contenere nome, P.IVA o CF."""
        t = (testo or "").strip()
        cifre = re.sub(r"\D", "", t)
        if cifre and len(cifre) == len(re.sub(r"\s", "", t)) and len(cifre) <= 11:
            trovato = self.per_piva.get(cifre.zfill(11)) or self.per_cf.get(cifre.zfill(11))
            if trovato:
                return trovato
        return self.per_cf.get(t.upper().replace(" ", "")) or self.per_nome.get(_chiave_nome(t))


def _leggi_righe(righe, colonne, inizio):
    intestazioni = righe[inizio] if righe else []
    mappa = _mappa_intestazioni(intestazioni, colonne)
    out = []
    for n, riga in enumerate(righe[inizio + 1:], start=inizio + 2):
        if _vuota(riga):
            continue
        avvisi, errori, dati = [], [], {}
        for i, campo in mappa.items():
            v = riga[i] if i < len(riga) else None
            etichetta, _, tipo = colonne[campo]
            dati[campo] = _converti(campo, tipo, v, avvisi, errori, etichetta)
        out.append({"riga": n, "dati": dati, "avvisi": avvisi, "errori": errori})
    return mappa, out


def analizza(dati: bytes, nome_file: str) -> dict:
    """Legge il file e prepara l'anteprima, senza scrivere nel database."""
    estensione = nome_file.lower().rsplit(".", 1)[-1] if "." in nome_file else ""
    if estensione in ("xlsx", "xlsm"):
        fogli = _fogli_da_xlsx(dati)
    elif estensione in ("csv", "txt"):
        fogli = _fogli_da_csv(dati)
    elif estensione == "xls":
        raise FileNonValido("I file .xls (Excel 97-2003) non si leggono: aprilo in Excel e salvalo come .xlsx.")
    else:
        raise FileNonValido("Carica un file Excel (.xlsx) o CSV.")

    indice = _Indice()
    clienti, polizze, ignorati = [], [], []
    polizze_viste = {(_norm(p.numero_polizza), _norm(p.compagnia)) for p in Policy.query.all()}

    righe_clienti, righe_polizze, righe_persone, persone = [], [], [], []
    for nome, righe in fogli:
        if not righe:
            continue
        inizio = _trova_intestazione(righe)
        tipo = _tipo_foglio(nome, righe[inizio])
        if tipo == "clienti":
            righe_clienti.append((nome, righe, inizio))
        elif tipo == "polizze":
            righe_polizze.append((nome, righe, inizio))
        elif tipo == "persone":
            righe_persone.append((nome, righe, inizio))
        elif not _vuota(righe[inizio]) and not _norm(nome).startswith(("istruzion", "valori")):
            ignorati.append(nome)

    if not righe_clienti and not righe_polizze and not righe_persone:
        raise FileNonValido("Non trovo colonne riconoscibili: serve almeno «Ragione sociale» o «Cognome» (clienti), "
                            "«Compagnia» e «Numero polizza» (polizze) oppure «Ruolo» e «Cognome» (amministratori). "
                            "Parti dal modello.")

    # 1) Clienti
    for nome, righe, inizio in righe_clienti:
        mappa, lette = _leggi_righe(righe, COLONNE_CLIENTI, inizio)
        if "nome" in mappa.values() and not {"ragione_sociale", "cognome"} & set(mappa.values()):
            # Una sola colonna «Nome»: contiene il nominativo intero, non si divide.
            for r in lette:
                r["dati"]["ragione_sociale"] = r["dati"].pop("nome", None)
            mappa = {i: ("ragione_sociale" if c == "nome" else c) for i, c in mappa.items()}
        if not {"ragione_sociale", "cognome"} & set(mappa.values()):
            raise FileNonValido(f"Nel foglio «{nome}» manca la colonna «Ragione sociale» (aziende) "
                                "oppure «Cognome» (persone).")
        for r in lette:
            d = r["dati"]
            r["foglio"] = nome
            persona = d.get("nome") or d.get("cognome")
            cf_persona = len(d.get("codice_fiscale") or "") == 16  # il CF di una persona ha 16 caratteri
            if not d.get("tipo"):
                if (persona and not d.get("ragione_sociale")) or cf_persona:
                    professionista = d.get("albo") or d.get("partita_iva") or d.get("professione")
                    d["tipo"] = "professionista" if professionista else "dipendente"
                else:
                    d["tipo"] = "azienda"
            if persona and d["tipo"] != "azienda":
                # Per le persone il nominativo è «Nome Cognome», come nella scheda.
                d["ragione_sociale"] = " ".join(x for x in (d.get("nome"), d.get("cognome")) if x)
            if not d.get("ragione_sociale"):
                r["errori"].append("Manca la ragione sociale (aziende) o nome e cognome (persone)")
            if r["errori"]:
                r["esito"] = "errore"
            else:
                trovato = indice.trova(d.get("partita_iva"), d.get("codice_fiscale"), d.get("ragione_sociale"))
                omonimo = indice.per_nome.get(_chiave_nome(d.get("ragione_sociale")))
                if not trovato and omonimo:
                    r["avvisi"].append("Esiste già un cliente con lo stesso nome ma P.IVA o codice fiscale "
                                       "diversi: verrà creato un cliente nuovo")
                if trovato:
                    r["esito"] = "esistente" if trovato[0] == "db" else "doppione"
                    r["rif"] = trovato
                    # Anche il nome scritto nel file porta a questo cliente:
                    # le polizze che lo usano non devono crearne un doppione.
                    indice.aggiungi(trovato, d.get("partita_iva"), d.get("codice_fiscale"), d.get("ragione_sociale"))
                else:
                    r["esito"] = "nuovo"
                    r["rif"] = ("file", len(clienti))
                    indice.aggiungi(r["rif"], d.get("partita_iva"), d.get("codice_fiscale"), d.get("ragione_sociale"))
            clienti.append(r)

    def risolvi_cliente(r, testo, piva=None, cf=None):
        """Trova il cliente di una riga di polizze o persone; se non esiste e
        il campo «Cliente» contiene un nome, lo prepara come cliente nuovo."""
        rif = indice.trova(piva, cf)
        if not rif and testo:
            rif = indice.cerca_testo(testo)
            if rif and indice.codici_in_conflitto(rif, piva, cf):
                rif = None  # stesso nome ma codici diversi: è un altro cliente
        if not rif:
            if testo and not re.fullmatch(r"[\d\s]+", testo):
                rif = ("file", len(clienti))
                nuovo = {"ragione_sociale": testo, "partita_iva": piva, "codice_fiscale": cf}
                clienti.append({"riga": r["riga"], "foglio": r["foglio"], "dati": nuovo, "avvisi": [],
                                "errori": [], "esito": "nuovo", "rif": rif, "da_polizza": True})
                indice.aggiungi(rif, piva, cf, testo)
            else:
                r["errori"].append("Cliente non trovato")
        return rif

    # 2) Polizze
    for nome, righe, inizio in righe_polizze:
        colonne = {**COLONNE_POLIZZE, **{k: COLONNE_CLIENTI[k] for k in CLIENTE_IN_POLIZZE}}
        mappa, lette = _leggi_righe(righe, colonne, inizio)
        mancanti = {"compagnia", "numero_polizza"} - set(mappa.values())
        if mancanti:
            raise FileNonValido(f"Nel foglio «{nome}» mancano le colonne «Compagnia» e «Numero polizza».")
        if not ({"cliente", "partita_iva", "codice_fiscale"} & set(mappa.values())):
            raise FileNonValido(f"Nel foglio «{nome}» manca la colonna «Cliente» (o P.IVA / codice fiscale).")
        for r in lette:
            d = r["dati"]
            r["foglio"] = nome
            for campo in ("compagnia", "numero_polizza"):
                if not d.get(campo):
                    r["errori"].append(f"Manca {COLONNE_POLIZZE[campo][0].lower()}")
            r["rif"] = risolvi_cliente(r, d.get("cliente"), d.get("partita_iva"), d.get("codice_fiscale"))
            if d.get("data_decorrenza") and d.get("data_scadenza") and d["data_scadenza"] < d["data_decorrenza"]:
                r["avvisi"].append("La scadenza è prima della decorrenza")
            chiave = (_norm(d.get("numero_polizza")), _norm(d.get("compagnia")))
            if r["errori"]:
                r["esito"] = "errore"
            elif chiave in polizze_viste:
                r["esito"] = "esistente"
            else:
                r["esito"] = "nuova"
                polizze_viste.add(chiave)
            polizze.append(r)

    # 3) Amministratori e persone collegate
    gia_presenti = set()
    for p in PersonaCollegata.query.all():
        rif = ("db", p.client_id)
        if p.codice_fiscale:
            gia_presenti.add((rif, "cf", p.codice_fiscale.upper()))
        gia_presenti.add((rif, "nome", _chiave_nome(p.nome_completo)))
    for nome, righe, inizio in righe_persone:
        mappa, lette = _leggi_righe(righe, COLONNE_PERSONE, inizio)
        if "cognome" not in mappa.values():
            raise FileNonValido(f"Nel foglio «{nome}» manca la colonna «Cognome».")
        if not {"cliente", "piva_cliente"} & set(mappa.values()):
            raise FileNonValido(f"Nel foglio «{nome}» manca la colonna «Cliente» (o P.IVA del cliente).")
        for r in lette:
            d = r["dati"]
            r["foglio"] = nome
            d["ruolo"], d["ruolo_altro"] = _ruolo(d.get("ruolo"))
            if not d.get("cognome"):
                r["errori"].append("Manca il cognome")
            if d.get("quota_perc") is not None and not 0 <= d["quota_perc"] <= 100:
                r["errori"].append("La quota deve essere tra 0 e 100")
            rif = risolvi_cliente(r, d.get("cliente"), d.get("piva_cliente"))
            r["rif"] = rif
            chiavi = set()
            if rif:
                if d.get("codice_fiscale"):
                    chiavi.add((rif, "cf", d["codice_fiscale"]))
                chiavi.add((rif, "nome", _chiave_nome(" ".join(x for x in (d.get("nome"), d.get("cognome")) if x))))
            if r["errori"]:
                r["esito"] = "errore"
            elif chiavi & gia_presenti:
                r["esito"] = "esistente"
            else:
                r["esito"] = "nuova"
                gia_presenti |= chiavi
            if (d.get("nome"), d.get("cognome")) == ESEMPIO_PERSONA and d.get("cliente") == ESEMPIO_CLIENTE:
                r["avvisi"].append("È la riga di esempio del modello: cancellala dal file se non serve")
            persone.append(r)

    for r in clienti:
        if r["dati"].get("ragione_sociale") == ESEMPIO_CLIENTE:
            r["avvisi"].append("È la riga di esempio del modello: cancellala dal file se non è un tuo cliente")
    for r in polizze:
        if r["dati"].get("compagnia") == ESEMPIO_COMPAGNIA:
            r["avvisi"].append("È la riga di esempio del modello: cancellala dal file se non è una tua polizza")

    def conta(righe, esito):
        return sum(1 for r in righe if r["esito"] == esito)

    nomi_db = {c.id: c.ragione_sociale for c in Client.query.with_entities(Client.id, Client.ragione_sociale)}
    for p in polizze + persone:
        rif = p.get("rif")
        if rif:
            p["nome_cliente"] = nomi_db.get(rif[1]) if rif[0] == "db" else clienti[rif[1]]["dati"]["ragione_sociale"]

    return {
        "clienti": clienti,
        "polizze": polizze,
        "persone": persone,
        "ignorati": ignorati,
        "conteggi": {
            "clienti_nuovi": conta(clienti, "nuovo"),
            "clienti_esistenti": conta(clienti, "esistente") + conta(clienti, "doppione"),
            "clienti_errori": conta(clienti, "errore"),
            "polizze_nuove": conta(polizze, "nuova"),
            "polizze_esistenti": conta(polizze, "esistente"),
            "polizze_errori": conta(polizze, "errore"),
            "persone_nuove": conta(persone, "nuova"),
            "persone_esistenti": conta(persone, "esistente"),
            "persone_errori": conta(persone, "errore"),
        },
    }


def importa(anteprima: dict) -> dict:
    """Scrive nel database ciò che l'anteprima segna come nuovo; completa i
    campi vuoti dei clienti già presenti. Tutto o niente."""
    creati, completati = {}, 0
    try:
        for i, r in enumerate(anteprima["clienti"]):
            d = {k: v for k, v in r["dati"].items() if k in COLONNE_CLIENTI}
            if r["esito"] == "nuovo":
                c = Client(**{k: v for k, v in d.items() if v not in (None, "")})
                c.tipo = c.tipo or "azienda"
                db.session.add(c)
                creati[i] = c
            elif r["esito"] == "esistente" and r.get("rif") and r["rif"][0] == "db":
                c = db.session.get(Client, r["rif"][1])
                cambiato = False
                for k, v in d.items():
                    if k != "tipo" and v not in (None, "") and getattr(c, k) in (None, ""):
                        setattr(c, k, v)
                        cambiato = True
                completati += cambiato
        db.session.flush()

        polizze_create = 0
        for r in anteprima["polizze"]:
            if r["esito"] != "nuova":
                continue
            origine, idx = r["rif"]
            cliente = db.session.get(Client, idx) if origine == "db" else creati.get(idx)
            if cliente is None:  # il cliente aveva un errore: la polizza si salta
                continue
            d = {k: v for k, v in r["dati"].items() if k in COLONNE_POLIZZE and k != "cliente" and v is not None}
            p = Policy(client_id=cliente.id, **d)
            p.ramo = p.ramo or "altro"
            p.stato = p.stato or "attiva"
            p.frazionamento = p.frazionamento or "annuale"
            db.session.add(p)
            polizze_create += 1

        persone_create = 0
        campi_persona = set(COLONNE_PERSONE) - {"cliente", "piva_cliente"} | {"ruolo_altro"}
        for r in anteprima.get("persone", []):
            if r["esito"] != "nuova":
                continue
            origine, idx = r["rif"]
            cliente = db.session.get(Client, idx) if origine == "db" else creati.get(idx)
            if cliente is None:
                continue
            d = {k: v for k, v in r["dati"].items() if k in campi_persona and v not in (None, "")}
            persona = PersonaCollegata(client_id=cliente.id, **d)
            if persona.codice_fiscale:
                # Già cliente privato (stesso codice fiscale): si collegano le schede.
                privato = Client.query.filter(Client.tipo.in_(("dipendente", "professionista")),
                                              db.func.upper(Client.codice_fiscale) == persona.codice_fiscale).first()
                if privato is not None and privato.id != cliente.id:
                    persona.persona_client_id = privato.id
            db.session.add(persona)
            persone_create += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"clienti": len(creati), "completati": completati, "polizze": polizze_create,
            "persone": persone_create}


# ----------------------------------------------------------------------
# Modello da scaricare
# ----------------------------------------------------------------------
def modello_xlsx() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    libro = Workbook()
    testa = Font(bold=True, color="FFFFFF")
    sfondo = PatternFill("solid", fgColor="1D3B30")

    def prepara(foglio, colonne, esempio: dict, testo=(), date_col=()):
        foglio.append([v[0] for v in colonne.values()])
        foglio.append([esempio.get(campo) for campo in colonne])
        # Codici come testo (Excel non toglie gli zeri), date in formato italiano
        for campi, formato in ((testo, "@"), (date_col, "DD/MM/YYYY")):
            for campo in campi:
                col = get_column_letter(list(colonne).index(campo) + 1)
                for riga in range(2, 501):
                    foglio[f"{col}{riga}"].number_format = formato
        for i, cella in enumerate(foglio[1], start=1):
            cella.font, cella.fill = testa, sfondo
            cella.alignment = Alignment(vertical="center", wrap_text=True)
            foglio.column_dimensions[get_column_letter(i)].width = max(14, min(36, len(cella.value) + 4))
        foglio.row_dimensions[1].height = 32
        foglio.freeze_panes = "A2"

    def lista(foglio, colonne, campo, voci_rif):
        col = get_column_letter(list(colonne).index(campo) + 1)
        dv = DataValidation(type="list", formula1=voci_rif, allow_blank=True, showErrorMessage=False)
        foglio.add_data_validation(dv)
        dv.add(f"{col}2:{col}{RIGHE_MASSIME}")

    valori = libro.active
    valori.title = "Valori"
    elenchi = {
        "Tipo cliente": [e for _, e in CLIENT_TYPES],
        "Ramo": [e for _, e in POLICY_BRANCHES],
        "Stato polizza": [e for _, e in POLICY_STATUSES],
        "Frazionamento": [e for _, e in PAYMENT_FREQUENCIES],
        "Sì/No": ["Sì", "No"],
        "Ruolo": [e for _, e in RUOLI_PERSONA],
    }
    for j, (titolo, voci) in enumerate(elenchi.items(), start=1):
        valori.cell(row=1, column=j, value=titolo).font = Font(bold=True)
        valori.column_dimensions[get_column_letter(j)].width = 34
        for i, voce in enumerate(voci, start=2):
            valori.cell(row=i, column=j, value=voce)

    def rif(j, voci):
        col = get_column_letter(j)
        return f"Valori!${col}$2:${col}${len(voci) + 1}"

    clienti = libro.create_sheet("Clienti", 0)
    prepara(clienti, COLONNE_CLIENTI, {
        "ragione_sociale": ESEMPIO_CLIENTE, "tipo": "Azienda", "referente": "Mario Rossi",
        "partita_iva": "01234567890", "codice_fiscale": "01234567890", "codice_ateco": "43.21.01",
        "settore": "Impianti elettrici", "indirizzo": "Via Roma 1", "citta": "Brescia", "cap": "25121",
        "provincia": "BS", "email": "info@rossiimpianti.it", "telefono": "030 1234567", "numero_dipendenti": 12,
        "fatturato_annuo": 1500000, "descrizione_attivita": "Installazione impianti elettrici civili e industriali",
    }, testo=("partita_iva", "codice_fiscale", "cap", "residenza_cap"),
        date_col=("data_nascita", "albo_data_iscrizione"))
    lista(clienti, COLONNE_CLIENTI, "tipo", rif(1, elenchi["Tipo cliente"]))

    polizze = libro.create_sheet("Polizze", 1)
    prepara(polizze, COLONNE_POLIZZE, {
        "cliente": ESEMPIO_CLIENTE, "compagnia": ESEMPIO_COMPAGNIA, "numero_polizza": "123456789",
        "ramo": BRANCH_LABELS["rct_rco"], "massimale": 3000000, "premio_annuo": 2450, "provvigione_perc": 12,
        "frazionamento": "Annuale", "data_decorrenza": date(date.today().year, 1, 1),
        "data_scadenza": date(date.today().year, 12, 31), "tacito_rinnovo": "Sì", "stato": "Attiva",
    }, date_col=("data_decorrenza", "data_scadenza"))
    lista(polizze, COLONNE_POLIZZE, "ramo", rif(2, elenchi["Ramo"]))
    lista(polizze, COLONNE_POLIZZE, "stato", rif(3, elenchi["Stato polizza"]))
    lista(polizze, COLONNE_POLIZZE, "frazionamento", rif(4, elenchi["Frazionamento"]))
    lista(polizze, COLONNE_POLIZZE, "tacito_rinnovo", rif(5, elenchi["Sì/No"]))

    persone = libro.create_sheet("Amministratori", 2)
    prepara(persone, COLONNE_PERSONE, {
        "cliente": ESEMPIO_CLIENTE, "ruolo": "Amministratore unico", "nome": ESEMPIO_PERSONA[0],
        "cognome": ESEMPIO_PERSONA[1], "codice_fiscale": "RSSMRA70A01B157X", "data_nascita": date(1970, 1, 1),
        "luogo_nascita": "Brescia", "indirizzo": "Via Garibaldi 3", "citta": "Brescia", "cap": "25122",
        "provincia": "BS", "telefono": "333 1234567", "dal": date(2015, 3, 1),
    }, testo=("piva_cliente", "codice_fiscale", "cap"), date_col=("data_nascita", "dal"))
    lista(persone, COLONNE_PERSONE, "ruolo", rif(6, elenchi["Ruolo"]))

    istruzioni = libro.create_sheet("Istruzioni")
    testo = [
        "Come compilare",
        "1. Foglio «Clienti»: una riga per cliente. Per le aziende basta «Ragione sociale»;",
        "   per professionisti e privati compila «Nome» e «Cognome» (più nascita, residenza e albo se li hai).",
        "2. Foglio «Polizze»: una riga per polizza. Obbligatori «Cliente», «Compagnia» e «Numero polizza».",
        "   In «Cliente» scrivi il nome come nel foglio Clienti, oppure la P.IVA o il codice fiscale.",
        "   Se il cliente non esiste ancora viene creato con quel nome.",
        "3. Foglio «Amministratori»: amministratori, consiglieri, soci, familiari… Obbligatori «Cliente»",
        "   e «Cognome»; il «Ruolo» si sceglie dal menu (un ruolo diverso viene salvato così com'è).",
        "4. Le righe di esempio (riga 2) vanno sostituite o cancellate.",
        "5. Date nel formato 31/12/2026; importi senza simbolo € (es. 2450 o 2.450,00).",
        "6. Ramo, stato, frazionamento, tipo e ruolo: scegli dal menu a tendina (elenchi nel foglio «Valori»).",
        "",
        "Cosa succede all'importazione",
        "- Prima vedi un'anteprima: niente viene salvato finché non confermi.",
        "- I clienti già presenti (stessa P.IVA, codice fiscale o nome) non vengono sovrascritti:",
        "  si completano solo i campi che erano vuoti.",
        "- Le polizze già presenti (stesso numero e compagnia) vengono saltate, così come le persone",
        "  già registrate sullo stesso cliente (stesso codice fiscale o stesso nome e cognome).",
        "- Prima di importare il gestionale fa un backup del database.",
    ]
    for riga in testo:
        istruzioni.append([riga])
    istruzioni.column_dimensions["A"].width = 110
    for r, riga in enumerate(testo, start=1):
        if riga in ("Come compilare", "Cosa succede all'importazione"):
            istruzioni[f"A{r}"].font = Font(bold=True, size=12)

    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()
