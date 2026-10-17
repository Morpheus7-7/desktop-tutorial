"""Catalogo delle professioni per l'anagrafica clienti.

Un libero professionista è una persona sola (l'avvocato civilista, il
pediatra); lo studio associato o la società tra professionisti è un'altra
cosa. Per entrambi il catalogo suggerisce specializzazioni (i settori in cui
lavora), attività svolte (rilevanti per il questionario RC professionale),
l'ordine di iscrizione e gli obblighi assicurativi di legge, con i massimali
minimi dove la legge li fissa.

La professione resta un testo libero: il catalogo la riconosce anche scritta
a mano («Medico pediatra», «Ing. civile») e non vincola le figure non in elenco.

Riferimenti normativi verificati a ottobre 2026 su fonti primarie; le norme
cambiano: in caso di dubbio fa fede il testo vigente.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Obbligo:
    """Copertura obbligatoria per legge per una professione."""

    ramo: str               # ramo del gestionale che la soddisfa
    copertura: str          # nome leggibile
    norma: str              # riferimento normativo
    descrizione: str = ""   # perché è obbligatoria e cosa deve coprire


@dataclass(frozen=True)
class Professione:
    chiave: str
    nome: str
    area: str                       # chiave di AREE
    albo: str                       # ordine / albo / collegio di iscrizione
    alias: tuple[str, ...]          # forme con cui viene scritta a mano (inizi di parola)
    specializzazioni: tuple[str, ...]
    attivita: tuple[str, ...]
    nome_studio: str
    obblighi: tuple[Obbligo, ...] = ()
    gelli_bianco: bool = False      # professione sanitaria soggetta alla L. 24/2017
    rischio_alto: tuple[str, ...] = ()  # voci che portano ai massimali più alti del DM 232/2023
    nota: str = ""                  # avvertenza per l'intermediario

    @property
    def sanitaria(self) -> bool:
        return self.area == "sanitaria"


AREE = {
    "legale": "Area legale",
    "sanitaria": "Professioni sanitarie",
    "tecnica": "Area tecnica",
    "economica": "Area economica e fiscale",
    "altro": "Altre professioni",
}

# Inquadramento del professionista: per le professioni sanitarie decide quale
# RC serve (L. 24/2017, art. 10): professionale per chi esercita in proprio
# (anche convenzionato con il SSN, DM 232/2023 art. 1), per colpa grave per chi
# opera in una struttura.
INQUADRAMENTI = [
    ("libero_professionista", "Libero professionista"),
    ("convenzionato", "Convenzionato con il SSN"),
    ("dipendente_pubblico", "Dipendente pubblico"),
    ("dipendente_privato", "Dipendente privato"),
    ("misto", "Dipendente con libera professione"),
]
INQUADRAMENTI_DIPENDENTE = {"dipendente_pubblico", "dipendente_privato"}

FORME_GIURIDICHE_STUDIO = [
    "Studio associato",
    "Società tra avvocati (STA)",
    "STP S.r.l.",
    "STP S.p.A.",
    "STP S.n.c.",
    "STP S.a.s.",
    "STP società semplice",
    "STP cooperativa",
    "Società di ingegneria",
    "Società di servizi tra professionisti",
    "Struttura sanitaria privata autorizzata",
    "S.r.l. (non STP)",
    "Altra forma",
]
FORME_GIURIDICHE_AZIENDA = [
    "Ditta individuale",
    "S.n.c.",
    "S.a.s.",
    "S.r.l.",
    "S.r.l.s.",
    "S.p.A.",
    "Società cooperativa",
    "Consorzio",
    "Associazione / ente non profit",
    "Altra forma",
]
FORME_GIURIDICHE = {"azienda": FORME_GIURIDICHE_AZIENDA, "studio": FORME_GIURIDICHE_STUDIO}

# Condizioni tipiche di chi non ha un'attività lavorativa in corso.
CONDIZIONI_PRIVATO = ["Pensionato", "Studente", "Casalinga / casalingo", "In cerca di occupazione", "Benestante"]

# Professioni «ombrello» che cedono alla specialità indicata nel testo.
PROFESSIONI_GENERICHE = {"medico"}

_DPR_137 = "DL 138/2011, art. 3 c. 5 lett. e); DPR 137/2012, art. 5"
_GELLI = "L. 24/2017 (Gelli-Bianco), art. 10; DM 232/2023"
_DESCR_137 = ("Obbligatoria per gli iscritti all'ordine o al collegio: estremi della polizza e massimale vanno "
              "comunicati al cliente al conferimento dell'incarico. La legge non fissa massimali minimi.")
_RC_ORDINE = Obbligo("rc_professionale", "RC professionale", _DPR_137, _DESCR_137)
_RC_SANITARIA = Obbligo("rc_professionale", "RC professionale (o per colpa grave se opera in una struttura)", _GELLI)


# ----------------------------------------------------------------------
# Riconoscimento della professione da testo libero
# ----------------------------------------------------------------------
def normalizza(testo: str | None) -> str:
    """Minuscole, senza accenti né spazi doppi: «Ing. Civile» → «ing. civile»."""
    testo = unicodedata.normalize("NFKD", (testo or "").lower())
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", testo).strip()


def trova_professione(testo: str | None) -> Professione | None:
    """Professione del catalogo descritta dal testo (None se non riconosciuta).

    Vince la professione nominata per prima («Ingegnere informatico» →
    ingegnere; a parità di posizione, l'alias più lungo: «Medico di base»).
    Una professione generica come il medico cede alla specialità della stessa
    area citata dopo: «Medico pediatra» → pediatra, «Medico veterinario» →
    veterinario.
    """
    n = normalizza(testo)
    if not n:
        return None
    candidati = []
    for indice, p in enumerate(PROFESSIONI):
        migliore = None
        for alias in (p.nome, *p.alias):
            a = normalizza(alias)
            trovato = re.search(r"(?<![a-z0-9])" + re.escape(a), n) if a else None
            if trovato and (migliore is None or (trovato.start(), -len(a)) < migliore):
                migliore = (trovato.start(), -len(a))
        if migliore:
            candidati.append((*migliore, indice, p))
    if not candidati:
        return None
    candidati.sort(key=lambda c: c[:3])
    scelta = candidati[0][3]
    if scelta.chiave in PROFESSIONI_GENERICHE:
        scelta = next(
            (c[3] for c in candidati if c[3].area == scelta.area and c[3].chiave not in PROFESSIONI_GENERICHE),
            scelta,
        )
    return scelta


def info_professione(professione: Professione) -> str:
    """Riga informativa per il modulo: ordine di iscrizione e obblighi di legge."""
    parti = []
    if professione.albo:
        parti.append(f"Iscrizione: {professione.albo}.")
    if professione.obblighi:
        parti.append("Obbligatorie per legge: " + "; ".join(
            f"{o.copertura} ({o.norma})" for o in professione.obblighi) + ".")
    elif not professione.nota:
        parti.append("Nessuna assicurazione obbligatoria per legge: RC professionale comunque consigliata.")
    if professione.nota:
        parti.append(professione.nota)
    return " ".join(parti)


# ----------------------------------------------------------------------
# Obblighi di legge e massimali minimi
# ----------------------------------------------------------------------
def _euro(importo: float) -> str:
    return f"{importo:,.0f} €".replace(",", ".")


def _obbligo(ramo, copertura, norma, descrizione="", minimo=None, nota_massimale="") -> dict:
    return {
        "ramo": ramo, "copertura": copertura, "norma": norma, "descrizione": descrizione,
        "massimale_minimo": minimo, "nota_massimale": nota_massimale,
    }


def _massimale_avvocato(fatturato: float | None) -> tuple[float | None, str]:
    """Massimale minimo dell'avvocato che esercita da solo (DM 22/09/2016, art. 3)."""
    if fatturato is None:
        return None, ("minimo da 350.000 € a 1.000.000 € per sinistro e per anno secondo il fatturato "
                      "(DM 22/09/2016, art. 3): indica il volume d'affari per calcolarlo")
    minimo = 350_000 if fatturato <= 30_000 else 500_000 if fatturato <= 70_000 else 1_000_000
    return minimo, (f"minimo {_euro(minimo)} per sinistro e per anno con un volume d'affari di "
                    f"{_euro(fatturato)} (DM 22/09/2016, art. 3)")


def _massimale_studio_legale(fatturato: float | None, professionisti: int | None) -> tuple[float | None, str]:
    """Massimale minimo dell'avvocatura in forma associata (DM 22/09/2016, art. 3)."""
    if professionisti is not None and professionisti > 10:
        minimo, annuo = 5_000_000, 10_000_000
    elif fatturato is None:
        return None, ("minimo da 1.000.000 € a 5.000.000 € per sinistro secondo professionisti e fatturato "
                      "(DM 22/09/2016, art. 3): indica il fatturato per calcolarlo")
    elif fatturato > 500_000:
        minimo, annuo = 2_000_000, 4_000_000
    else:
        minimo, annuo = 1_000_000, 2_000_000
    return minimo, f"minimo {_euro(minimo)} per sinistro e {_euro(annuo)} annui (DM 22/09/2016, art. 3)"


def _rischio_alto(professione: Professione, voci) -> bool:
    testo = " | ".join(normalizza(v) for v in voci or ())
    return any(normalizza(k) in testo for k in professione.rischio_alto)


def obblighi_di_legge(
    tipo: str,
    professione: Professione | None,
    *,
    inquadramento: str | None = None,
    forma_giuridica: str | None = None,
    fatturato: float | None = None,
    numero_professionisti: int | None = None,
    voci=(),
) -> tuple[list[dict], list[str]]:
    """Coperture obbligatorie per legge del cliente e avvertenze per l'intermediario.

    ``voci`` sono specializzazioni e attività svolte: per i sanitari decidono la
    classe di massimale del DM 232/2023 (chirurgia, ortopedia, anestesia, parto).
    """
    if professione is None or tipo not in ("professionista", "studio"):
        return [], []
    avvertenze = [professione.nota] if professione.nota else []
    if tipo == "studio":
        return _obblighi_studio(professione, forma_giuridica, fatturato, numero_professionisti, avvertenze), avvertenze

    elenco = []
    for o in professione.obblighi:
        if professione.gelli_bianco and o.ramo == "rc_professionale":
            elenco.extend(_obblighi_sanitario(professione, inquadramento, voci))
            continue
        minimo, nota = (None, "")
        if professione.chiave == "avvocato" and o.ramo == "rc_professionale":
            minimo, nota = _massimale_avvocato(fatturato)
        elif professione.chiave == "notaio":
            nota = "copertura complessiva minima 3.000.000 € per sinistro e per anno (DM 19/10/2012, art. 2)"
        elenco.append(_obbligo(o.ramo, o.copertura, o.norma, o.descrizione, minimo, nota))
    return elenco, avvertenze


def _obblighi_sanitario(professione, inquadramento, voci) -> list[dict]:
    """RC dei sanitari secondo l'inquadramento (L. 24/2017, artt. 7, 9 e 10; DM 232/2023).

    Chi opera in una struttura o in convenzione con il SSN è coperto dalla
    struttura (o dalla ASL) verso il paziente e deve assicurare la colpa grave;
    per l'attività privata serve la RC professionale propria.
    """
    elenco = []
    if inquadramento in INQUADRAMENTI_DIPENDENTE or inquadramento in ("misto", "convenzionato"):
        elenco.append(_obbligo(
            "rc_professionale", "RC per colpa grave", "L. 24/2017, art. 10 c. 3; DM 232/2023",
            ("Per le prestazioni in convenzione risponde la ASL, che può rivalersi per colpa grave: la polizza "
             "per colpa grave è obbligatoria e a carico del medico." if inquadramento == "convenzionato" else
             "Chi opera in una struttura è coperto dalla struttura verso il paziente, ma la struttura (o la Corte "
             "dei conti) può rivalersi per colpa grave: la polizza è obbligatoria e a suo carico."),
            None,
            "massimale pari ai limiti della rivalsa: il triplo della retribuzione lorda, del corrispettivo "
            "convenzionale o del reddito professionale (L. 24/2017, art. 9; DM 232/2023, art. 4 c. 3)",
        ))
    if inquadramento in INQUADRAMENTI_DIPENDENTE:
        return elenco
    alto = _rischio_alto(professione, voci)
    minimo = 2_000_000 if alto else 1_000_000
    if inquadramento == "misto":
        copertura = "RC professionale per l'attività privata"
        descrizione = ("Per l'attività privata fuori dalla struttura (studio, extramoenia) serve anche la RC "
                       "professionale propria; l'intramoenia è coperta dalla struttura.")
    elif inquadramento == "convenzionato":
        copertura = "RC professionale per l'attività privata"
        descrizione = ("Obbligatoria per le prestazioni private fuori convenzione. Se una RC propria serva anche "
                       "per l'attività in convenzione è controverso (DM 232/2023, art. 1): per prudenza conviene "
                       "una polizza unica che copra RC verso terzi e colpa grave.")
    else:
        copertura = "RC professionale"
        descrizione = ("Esercitando in proprio risponde direttamente verso il paziente: RC professionale con "
                       "retroattività e ultrattività decennali (DM 232/2023, art. 5).")
    elenco.append(_obbligo(
        "rc_professionale", copertura, "L. 24/2017, art. 10 c. 2; DM 232/2023", descrizione, minimo,
        f"minimo {_euro(minimo)} per sinistro e {_euro(3 * minimo)} annui (DM 232/2023, art. 4)"
        + (" per attività chirurgica, ortopedica, anestesiologica o di parto" if alto else ""),
    ))
    return elenco


def _obblighi_studio(professione, forma, fatturato, professionisti, avvertenze) -> list[dict]:
    if professione.chiave == "avvocato":
        minimo, nota = _massimale_studio_legale(fatturato, professionisti)
        return [
            _obbligo("rc_professionale", "RC professionale dello studio", "L. 247/2012, art. 12 c. 1; DM 22/09/2016",
                     "Per gli avvocati l'obbligo riguarda direttamente anche l'associazione e la società tra "
                     "avvocati, oltre ai singoli professionisti.", minimo, nota),
            _obbligo("infortuni", "Infortuni di collaboratori, dipendenti e praticanti",
                     "L. 247/2012, art. 12 c. 2; DM 22/09/2016, art. 4",
                     "Per chi non è coperto dall'INAIL, anche come sostituto o collaboratore esterno occasionale."),
        ]
    if forma and forma.startswith("STP"):
        return [_obbligo(
            "rc_professionale", "RC professionale della società", "L. 183/2011, art. 10 c. 4 lett. c-bis); DM 34/2013",
            "L'atto costitutivo della STP deve prevedere la polizza per i danni causati ai clienti dai soci "
            "professionisti.",
        )]
    if professione.gelli_bianco and forma == "Struttura sanitaria privata autorizzata":
        return [_obbligo(
            "rc_professionale", "RC della struttura sanitaria", "L. 24/2017, art. 10 c. 1; DM 232/2023",
            "La struttura risponde verso i pazienti anche per l'operato dei professionisti di cui si avvale "
            "(art. 7) e deve assicurarsi verso terzi e verso i prestatori d'opera.",
        )]
    if professione.obblighi:
        avvertenze.append(
            "Nello studio associato l'obbligo di RC resta in capo ai singoli professionisti: verifica le loro "
            "polizze e proponi una RC dello studio per i danni imputabili alla struttura."
        )
    return []


# ----------------------------------------------------------------------
# Elenchi di voci (specializzazioni, attività) salvati come testo
# ----------------------------------------------------------------------
SEPARATORE = "; "
_SEPARATORI_SALVATI = re.compile(r"[;\n]+")
_SEPARATORI_TESTO_LIBERO = re.compile(r"[;,\n]+")


def dividi_voci(testo: str | None) -> list[str]:
    """Voci salvate: «Civilista; Penalista» → ["Civilista", "Penalista"]."""
    return [v.strip() for v in _SEPARATORI_SALVATI.split(testo or "") if v.strip()]


def unisci_voci(*gruppi) -> str | None:
    """Unisce più elenchi di voci senza doppioni (anche per maiuscole/accenti).

    Un elenco (le caselle spuntate) porta voci intere; un testo (il campo
    «Altre») è scritto a mano e si divide anche sulle virgole.
    """
    visti, voci = set(), []
    for gruppo in gruppi:
        elenco = _SEPARATORI_TESTO_LIBERO.split(gruppo) if isinstance(gruppo, str) else gruppo or []
        for voce in elenco:
            voce = re.sub(r"\s+", " ", str(voce).replace(";", ",")).strip()[:120]
            chiave = normalizza(voce)
            if chiave and chiave not in visti:
                visti.add(chiave)
                voci.append(voce)
    return SEPARATORE.join(voci) or None


def separa_voci(testo: str | None, catalogo) -> tuple[set[str], str]:
    """Voci del catalogo presenti (normalizzate) e le altre, come testo libero."""
    nel_catalogo = {normalizza(v) for v in catalogo or ()}
    scelte, altre = set(), []
    for voce in dividi_voci(testo):
        if normalizza(voce) in nel_catalogo:
            scelte.add(normalizza(voce))
        else:
            altre.append(voce)
    return scelte, ", ".join(altre)


# ----------------------------------------------------------------------
# Catalogo (le voci non contengono virgole: restano intere una volta salvate)
# ----------------------------------------------------------------------
PROFESSIONI: tuple[Professione, ...] = (
    # --- Area legale ----------------------------------------------------
    Professione(
        "avvocato", "Avvocato", "legale", "Ordine degli Avvocati",
        ("avvocat", "avv.", "legale", "civilista", "penalista", "giuslavorista", "amministrativista",
         "matrimonialista", "cassazionista"),
        ("Civilista", "Penalista", "Amministrativista", "Giuslavorista", "Tributarista", "Famiglia e minori",
         "Commerciale e societario", "Crisi d'impresa e procedure concorsuali", "Bancario e finanziario",
         "Locazioni e condominio", "Responsabilità civile e assicurazioni", "Successioni",
         "Esecuzioni e recupero crediti", "Proprietà industriale e intellettuale", "Privacy e diritto digitale",
         "Internazionale e UE", "Immigrazione e protezione internazionale", "Ambiente"),
        ("Contenzioso giudiziale", "Consulenza stragiudiziale", "Domiciliazioni e sostituzioni d'udienza",
         "Curatore o commissario giudiziale", "Gestore della crisi (OCC)", "Amministratore di sostegno o tutore",
         "Mediatore civile", "Arbitro", "Custode giudiziario o delegato alle vendite", "Amministratore di condominio",
         "Sindaco o revisore", "Organismo di vigilanza 231", "DPO (privacy)"),
        "Studio legale",
        (Obbligo("rc_professionale", "RC professionale", "L. 247/2012, art. 12 c. 1; DM 22/09/2016",
                 "Obbligatoria per esercitare, con gli estremi comunicati al cliente: copre anche la colpa grave e "
                 "i fatti di collaboratori e praticanti, con retroattività illimitata e ultrattività decennale per "
                 "chi cessa. Curatele, mediazioni, arbitrati e amministrazioni di condominio vanno estesi "
                 "espressamente."),
         Obbligo("infortuni", "Infortuni di collaboratori, dipendenti e praticanti",
                 "L. 247/2012, art. 12 c. 2; DM 22/09/2016, art. 4",
                 "Obbligatoria se ha collaboratori, dipendenti o praticanti non coperti dall'INAIL; dal 2017 non "
                 "riguarda più l'avvocato stesso (DL 148/2017).")),
    ),
    Professione(
        "notaio", "Notaio", "legale", "Consiglio notarile distrettuale",
        ("notai", "notaro"),
        ("Immobiliare", "Societario e operazioni straordinarie", "Successioni e donazioni",
         "Famiglia e convenzioni matrimoniali", "Mutui e finanziamenti", "Volontaria giurisdizione",
         "Terzo settore e fondazioni"),
        ("Compravendite immobiliari", "Mutui e ipoteche", "Atti societari", "Testamenti e donazioni",
         "Autentiche di firme e procure", "Deposito del prezzo e custodia di somme", "Delegato alle vendite giudiziarie"),
        "Studio notarile",
        (Obbligo("rc_professionale", "RC professionale individuale a secondo rischio",
                 "L. 89/1913, art. 19; DM Giustizia 19/10/2012",
                 "La polizza collettiva del Consiglio Nazionale del Notariato copre almeno 150.000 €; ogni notaio "
                 "deve avere una copertura di almeno 3.000.000 € per sinistro e per anno: se la collettiva non la "
                 "raggiunge serve una polizza individuale in eccedenza."),),
    ),
    # --- Professioni sanitarie -------------------------------------------
    Professione(
        "medico", "Medico chirurgo", "sanitaria", "Ordine dei Medici Chirurghi e degli Odontoiatri",
        ("medic", "medico legale", "neuropsichiatr", "chirurg", "cardiolog", "ginecolog", "ortoped", "dermatolog",
         "oculist", "oftalmolog", "otorino", "neurolog", "psichiatr", "anestesist", "radiolog", "urolog",
         "gastroenterolog", "endocrinolog", "oncolog", "geriatr", "fisiatr", "allergolog", "internista"),
        ("Anestesia e rianimazione", "Cardiologia", "Chirurgia generale", "Chirurgia plastica ed estetica",
         "Dermatologia", "Gastroenterologia", "Ginecologia e ostetricia", "Medicina interna",
         "Medicina d'emergenza-urgenza", "Medicina del lavoro", "Medicina dello sport", "Medicina legale",
         "Neurologia", "Neuropsichiatria infantile", "Oculistica", "Oncologia", "Ortopedia e traumatologia",
         "Otorinolaringoiatria", "Psichiatria", "Radiologia", "Urologia", "Endocrinologia",
         "Allergologia e immunologia", "Geriatria", "Fisiatria"),
        ("Visite ambulatoriali", "Interventi chirurgici", "Procedure invasive ed endoscopiche", "Anestesia",
         "Assistenza al parto", "Medicina estetica", "Pronto soccorso", "Visite domiciliari",
         "Libera professione intramoenia", "Libera professione extramoenia", "Perizie medico-legali e CTU",
         "Telemedicina", "Medico competente (D.Lgs. 81/2008)"),
        "Studio medico",
        (_RC_SANITARIA,), gelli_bianco=True,
        rischio_alto=("chirurg", "ortoped", "anestesi", "ostetricia", "assistenza al parto"),
    ),
    Professione(
        "medico_base", "Medico di medicina generale", "sanitaria", "Ordine dei Medici Chirurghi e degli Odontoiatri",
        ("medicina generale", "medico di base", "medico di famiglia", "medico generico", "mmg",
         "medico di assistenza primaria", "guardia medica"),
        ("Assistenza primaria", "Continuità assistenziale", "Emergenza territoriale 118",
         "Cure palliative e domiciliari", "Medicina turistica", "Medicina penitenziaria", "Medicina dei servizi"),
        ("Visite ambulatoriali", "Visite domiciliari", "Certificati di malattia e idoneità",
         "Certificati sportivi non agonistici", "Diagnostica di primo livello in studio",
         "Piccola chirurgia ambulatoriale", "Vaccinazioni", "Telemedicina", "Visite private"),
        "Studio medico associato",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "pediatra", "Pediatra", "sanitaria", "Ordine dei Medici Chirurghi e degli Odontoiatri",
        ("pediatr", "neonatolog", "pls"),
        ("Pediatria generale", "Neonatologia", "Terapia intensiva neonatale", "Pediatria d'urgenza",
         "Allergologia e immunologia pediatrica", "Gastroenterologia pediatrica", "Cardiologia pediatrica",
         "Endocrinologia pediatrica e auxologia", "Neurologia pediatrica", "Pneumologia pediatrica",
         "Nefrologia pediatrica", "Oncoematologia pediatrica", "Reumatologia pediatrica",
         "Infettivologia pediatrica", "Dermatologia pediatrica", "Medicina dell'adolescenza"),
        ("Visite ambulatoriali private", "Visite domiciliari", "Bilanci di salute", "Vaccinazioni",
         "Reparto ospedaliero o pronto soccorso pediatrico", "Assistenza neonatale in sala parto e nido",
         "Guardia medica pediatrica", "Ecografie e diagnostica ambulatoriale", "Certificati sportivi non agonistici",
         "Telemedicina e consulenza telefonica", "Libera professione intramoenia"),
        "Studio pediatrico",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "odontoiatra", "Odontoiatra", "sanitaria", "Ordine dei Medici Chirurghi e degli Odontoiatri (albo odontoiatri)",
        ("odontoiatr", "dentist", "ortodontist", "implantolog", "endodontist", "parodontolog"),
        ("Conservativa ed endodonzia", "Parodontologia", "Implantologia", "Chirurgia orale", "Ortodonzia",
         "Protesi", "Pedodonzia", "Gnatologia", "Estetica dentale", "Igiene e prevenzione"),
        ("Cure conservative", "Estrazioni e chirurgia orale", "Implantologia", "Rialzo del seno mascellare",
         "Ortodonzia con allineatori", "Protesi fissa e mobile", "Sedazione cosciente", "Radiologia endorale e CBCT",
         "Sbiancamento e trattamenti estetici", "Direttore sanitario di struttura odontoiatrica"),
        "Studio dentistico",
        (_RC_SANITARIA,), gelli_bianco=True,
        rischio_alto=("chirurgia orale", "implantolog", "rialzo del seno"),
    ),
    Professione(
        "veterinario", "Medico veterinario", "sanitaria", "Ordine dei Medici Veterinari",
        ("veterinar",),
        ("Animali da compagnia", "Animali da reddito", "Equini", "Animali esotici", "Chirurgia veterinaria",
         "Medicina interna veterinaria", "Ortopedia veterinaria", "Dermatologia veterinaria",
         "Diagnostica per immagini", "Riproduzione animale", "Medicina comportamentale", "Igiene degli alimenti"),
        ("Visite ambulatoriali", "Interventi chirurgici e anestesia", "Visite in allevamento",
         "Medicina equina sportiva", "Pronto soccorso h24 e degenza", "Custodia di animali in degenza o pensione",
         "Vaccinazioni e microchip", "Certificazioni sanitarie per l'export", "Veterinario ufficiale ASL",
         "Direttore sanitario di struttura veterinaria"),
        "Clinica veterinaria",
        (_RC_ORDINE,),
    ),
    Professione(
        "farmacista", "Farmacista", "sanitaria", "Ordine dei Farmacisti",
        ("farmacist", "titolare di farmacia", "parafarmacia"),
        ("Farmacia territoriale", "Farmacia ospedaliera", "Galenica", "Farmacia dei servizi", "Dermocosmesi",
         "Fitoterapia", "Omeopatia", "Nutrizione e integratori", "Farmaci veterinari", "Parafarmacia"),
        ("Titolare o direttore di farmacia", "Farmacista collaboratore", "Preparazioni galeniche",
         "Vaccinazioni in farmacia", "Test diagnostici e autoanalisi", "Telemedicina (ECG e holter)",
         "Distribuzione per conto (DPC)", "Consegna a domicilio", "Vendita online di farmaci da banco"),
        "Farmacia",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "psicologo", "Psicologo / psicoterapeuta", "sanitaria", "Ordine degli Psicologi",
        ("psicolog", "psicoterapeut", "neuropsicolog"),
        ("Psicoterapia", "Psicologia clinica", "Età evolutiva", "Neuropsicologia", "Psicologia del lavoro",
         "Psicologia giuridica e forense", "Psicologia scolastica", "Psicologia dello sport",
         "Psicologia dell'emergenza", "Psico-oncologia", "Psicologia perinatale", "Sessuologia", "Dipendenze"),
        ("Colloqui di sostegno", "Psicoterapia individuale", "Psicoterapia di coppia e familiare",
         "Psicoterapia di gruppo", "Test e valutazioni psicodiagnostiche", "Interventi con minori", "Sedute online",
         "Perizie CTU e CTP", "Sportello d'ascolto scolastico", "Ipnosi clinica ed EMDR",
         "Selezione e formazione del personale"),
        "Studio di psicologia",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "infermiere", "Infermiere", "sanitaria", "Ordine delle Professioni Infermieristiche (OPI)",
        ("infermier",),
        ("Area critica e terapia intensiva", "Emergenza 118", "Sala operatoria", "Pediatria", "Famiglia e comunità",
         "Assistenza domiciliare", "Wound care", "Stomaterapia", "Cure palliative", "Salute mentale", "Dialisi",
         "Geriatria e RSA"),
        ("Libera professione domiciliare", "Prestazioni ambulatoriali in studio", "Prelievi e terapie infusionali",
         "Medicazioni avanzate", "Gestione di cateteri e PICC", "Assistenza in RSA o strutture private",
         "Assistenza in sala operatoria", "Somministrazione di vaccini", "Telemonitoraggio"),
        "Studio infermieristico",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "fisioterapista", "Fisioterapista", "sanitaria", "Ordine dei Fisioterapisti",
        ("fisioterap", "fisiokinesiterap"),
        ("Muscoloscheletrica", "Neurologica", "Cardiorespiratoria", "Pediatrica", "Sportiva", "Geriatrica",
         "Terapia manuale", "Pavimento pelvico", "Linfodrenaggio", "Riabilitazione post-operatoria", "Posturologia"),
        ("Trattamenti in studio", "Trattamenti domiciliari", "Terapie fisiche strumentali", "Terapia manuale",
         "Bendaggi e taping", "Idrokinesiterapia", "Fisioterapista di società sportive",
         "Collaborazione con strutture e RSA", "Teleriabilitazione"),
        "Studio di fisioterapia",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "ostetrica", "Ostetrica", "sanitaria", "Ordine della Professione di Ostetrica",
        ("ostetric", "levatric"),
        ("Gravidanza fisiologica", "Assistenza al travaglio e al parto", "Parto a domicilio e case maternità",
         "Puerperio e allattamento", "Prevenzione ginecologica", "Pavimento pelvico", "Accompagnamento alla nascita",
         "Consultorio", "Menopausa"),
        ("Assistenza al parto in struttura", "Parto a domicilio", "Visite in gravidanza",
         "Assistenza domiciliare in puerperio", "Consulenza sull'allattamento", "Pap test e screening",
         "Riabilitazione del pavimento pelvico", "Corsi preparto", "Attività in consultorio"),
        "Studio ostetrico",
        (_RC_SANITARIA,), gelli_bianco=True,
        rischio_alto=("assistenza al parto", "parto a domicilio", "travaglio"),
    ),
    Professione(
        "sanitario_tecnico", "Professionista sanitario tecnico o della riabilitazione", "sanitaria",
        "Ordine TSRM e PSTRP",
        ("logopedist", "dietist", "igienista dentale", "podolog", "ortottist", "tecnico di radiologia", "tsrm",
         "tecnico di laboratorio", "audioprotesist", "tecnico ortopedico", "terapista occupazionale",
         "neuropsicomotricist", "tnpee", "educatore professionale", "tecnico della prevenzione",
         "assistente sanitari", "osteopat"),
        ("Tecnico di radiologia medica", "Tecnico di laboratorio biomedico", "Tecnico di neurofisiopatologia",
         "Tecnico audioprotesista", "Tecnico ortopedico", "Dietista", "Igienista dentale", "Logopedista", "Podologo",
         "Ortottista", "Terapista della neuro e psicomotricità", "Terapista occupazionale", "Educatore professionale",
         "Tecnico della prevenzione", "Assistente sanitario", "Osteopata"),
        ("Prestazioni in studio privato", "Prestazioni domiciliari", "Diagnostica per immagini", "Esami di laboratorio",
         "Trattamenti riabilitativi", "Igiene orale professionale", "Diete su prescrizione medica",
         "Ortesi e protesi su misura", "Attività presso strutture sanitarie", "Teleriabilitazione"),
        "Studio professionale sanitario",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    Professione(
        "biologo", "Biologo / nutrizionista", "sanitaria", "Ordine dei Biologi",
        ("biolog", "nutrizionist"),
        ("Nutrizione", "Analisi cliniche e di laboratorio", "Genetica e biologia molecolare", "Microbiologia",
         "Embriologia e PMA", "Sicurezza alimentare", "Biologia ambientale", "Biologia forense"),
        ("Piani alimentari", "Analisi di laboratorio", "Direttore tecnico di laboratorio", "Embriologia clinica e PMA",
         "Test genetici", "Consulenze HACCP", "Analisi ambientali", "Perizie e CTU", "Consulenze nutrizionali online"),
        "Studio di biologia e nutrizione",
        (_RC_SANITARIA,), gelli_bianco=True,
    ),
    # --- Area tecnica ---------------------------------------------------
    Professione(
        "ingegnere", "Ingegnere", "tecnica", "Ordine degli Ingegneri",
        ("ingegner", "ing.", "strutturist"),
        ("Strutturale", "Edile", "Civile e infrastrutture", "Geotecnica", "Idraulica", "Impianti elettrici",
         "Impianti termotecnici", "Energetica", "Ambientale", "Prevenzione incendi", "Sicurezza nei cantieri",
         "Acustica", "Informatica e telecomunicazioni", "Meccanica", "Gestionale", "Chimica e di processo",
         "Biomedica"),
        ("Progettazione strutturale", "Progettazione impiantistica", "Direzione lavori", "Collaudi",
         "Coordinamento sicurezza (CSP / CSE)", "RSPP esterno", "Certificazione energetica (APE)",
         "Asseverazioni per bonus edilizi", "Prevenzione incendi (SCIA antincendio)",
         "Verifica e validazione di progetti", "Incarichi per opere pubbliche", "Perizie CTU e CTP"),
        "Studio di ingegneria",
        (_RC_ORDINE,),
    ),
    Professione(
        "architetto", "Architetto", "tecnica", "Ordine degli Architetti, Pianificatori, Paesaggisti e Conservatori",
        ("architett", "arch.", "paesaggist", "pianificator"),
        ("Progettazione architettonica", "Ristrutturazione edilizia", "Restauro e conservazione", "Urbanistica",
         "Paesaggio", "Interior design", "Bioedilizia e sostenibilità", "Efficienza energetica", "Progettazione BIM",
         "Accessibilità"),
        ("Progettazione architettonica", "Direzione lavori", "Pratiche edilizie (CILA SCIA permessi)",
         "Coordinamento sicurezza (CSP / CSE)", "Certificazione energetica (APE)", "Asseverazioni per bonus edilizi",
         "Restauro di beni vincolati", "Piani urbanistici", "Incarichi per opere pubbliche", "Perizie CTU e CTP"),
        "Studio di architettura",
        (_RC_ORDINE,),
    ),
    Professione(
        "geometra", "Geometra", "tecnica", "Collegio dei Geometri e Geometri Laureati",
        ("geometr", "geom."),
        ("Progettazione edilizia", "Topografia e rilievi", "Catasto", "Estimo e valutazioni immobiliari",
         "Pratiche edilizie", "Sicurezza nei cantieri", "Certificazione energetica", "Successioni e volture",
         "Amministrazione condominiale", "Prevenzione incendi"),
        ("Progettazione e direzione lavori", "Pratiche catastali (DOCFA PREGEO)", "Rilievi topografici e frazionamenti",
         "Stime e perizie per mutui", "Verifiche di conformità urbanistica", "Coordinamento sicurezza (CSP / CSE)",
         "Certificazione energetica (APE)", "Asseverazioni per bonus edilizi", "Amministratore di condominio",
         "CTU e CTP"),
        "Studio tecnico",
        (_RC_ORDINE,),
    ),
    Professione(
        "perito_industriale", "Perito industriale", "tecnica", "Ordine dei Periti Industriali",
        ("perito industr", "periti industr", "per. ind", "perito elettrotecnic", "perito termotecnic",
         "perito meccanic"),
        ("Elettrotecnica", "Elettronica e telecomunicazioni", "Meccanica", "Termotecnica", "Edilizia", "Chimica",
         "Informatica", "Automazione", "Energie rinnovabili"),
        ("Progettazione di impianti elettrici", "Progettazione di impianti termici", "Impianti fotovoltaici",
         "Prevenzione incendi", "Certificazione energetica (APE)", "Verifiche di impianti e messa a terra",
         "Collaudi e DiRi", "RSPP", "Direzione lavori impiantistici", "Asseverazioni per bonus edilizi",
         "Perizie CTU e CTP"),
        "Studio tecnico",
        (_RC_ORDINE,),
    ),
    Professione(
        "geologo", "Geologo", "tecnica", "Ordine dei Geologi",
        ("geolog",),
        ("Geologia applicata e geotecnica", "Idrogeologia", "Ambiente e bonifiche", "Rischio idrogeologico",
         "Sismica e microzonazione", "Geotermia", "Cave e miniere", "Geofisica"),
        ("Relazioni geologiche", "Indagini geognostiche", "Microzonazione sismica", "Bonifica di siti contaminati",
         "Pozzi e captazioni", "Monitoraggio di frane", "Studi per VIA e VAS", "Perizie CTU e CTP"),
        "Studio di geologia",
        (_RC_ORDINE,),
    ),
    Professione(
        "agronomo", "Agronomo / dottore forestale", "tecnica", "Ordine dei Dottori Agronomi e dei Dottori Forestali",
        ("agronom", "dottore forestal", "dottoressa forestal"),
        ("Produzioni vegetali", "Zootecnia", "Estimo rurale", "Selvicoltura", "Verde urbano e arboricoltura",
         "Paesaggio", "Viticoltura ed enologia", "Agricoltura biologica", "Sviluppo rurale e PAC",
         "Difesa fitosanitaria", "Agrivoltaico"),
        ("Stime e perizie (danni ed espropri)", "Pratiche PAC e PSR", "Valutazione di stabilità degli alberi (VTA)",
         "Progettazione del verde", "Piani di gestione forestale", "Consulenza fitosanitaria",
         "Certificazioni di filiera", "Direzione lavori agricoli", "Perizie CTU e CTP"),
        "Studio agronomico",
        (_RC_ORDINE,),
    ),
    Professione(
        "consulente_informatico", "Consulente informatico", "tecnica", "",
        ("informatic", "consulente it", "sviluppator", "programmator", "sistemist", "web developer"),
        ("Sviluppo software", "Web e app", "Sistemi e infrastrutture", "Sicurezza informatica", "Cloud", "Reti",
         "Database e dati", "Gestionali ed ERP", "Intelligenza artificiale", "Privacy e GDPR", "Assistenza hardware",
         "E-commerce e marketing digitale"),
        ("Sviluppo software su commessa", "Installazione e configurazione di sistemi", "Gestione di reti",
         "Servizi cloud e hosting", "Backup e disaster recovery", "Penetration test", "Assistenza tecnica e help desk",
         "Trattamento di dati per conto dei clienti", "DPO (privacy)", "Formazione"),
        "Società di consulenza informatica",
    ),
    # --- Area economica e fiscale ----------------------------------------
    Professione(
        "commercialista", "Dottore commercialista", "economica",
        "Ordine dei Dottori Commercialisti e degli Esperti Contabili",
        ("commercialist", "esperto contabil", "esperta contabil", "ragionier", "rag.", "dott. comm"),
        ("Fiscale e tributario", "Contabilità e bilancio", "Societario e operazioni straordinarie", "Revisione legale",
         "Crisi d'impresa", "Contenzioso tributario", "Controllo di gestione", "Finanza agevolata",
         "Valutazioni d'azienda", "Fiscalità internazionale", "Terzo settore", "Pianificazione patrimoniale", "Paghe"),
        ("Tenuta della contabilità e bilanci", "Dichiarazioni fiscali e invii telematici", "Visto di conformità",
         "Contenzioso tributario", "Operazioni straordinarie", "Sindaco o revisore legale",
         "Curatore o commissario giudiziale", "Attestatore o esperto della crisi",
         "Amministratore giudiziario o custode", "Organismo di vigilanza 231", "Elaborazione paghe",
         "Amministratore o liquidatore di società"),
        "Studio commercialista",
        (_RC_ORDINE,),
    ),
    Professione(
        "consulente_lavoro", "Consulente del lavoro", "economica", "Ordine dei Consulenti del Lavoro",
        ("consulente del lavoro", "consulenti del lavoro", "consulente lavoro", "consulente paghe"),
        ("Paghe e amministrazione del personale", "Diritto del lavoro", "Previdenza", "Relazioni sindacali",
         "Contenzioso del lavoro", "Sicurezza sul lavoro", "Welfare aziendale", "Selezione del personale",
         "Certificazione dei contratti"),
        ("Elaborazione cedolini", "Comunicazioni obbligatorie e LUL", "Assistenza nelle vertenze",
         "Rappresentanza presso enti e Ispettorato", "Ammortizzatori sociali (CIG e FIS)",
         "Asseverazione contributiva (ASSE.CO)", "Visto di conformità", "Certificazione dei contratti",
         "Selezione del personale"),
        "Studio di consulenza del lavoro",
        (_RC_ORDINE,),
    ),
    Professione(
        "revisore_legale", "Revisore legale", "economica", "Registro dei Revisori Legali (MEF)",
        ("revisore legal", "revisori legal", "revisore contabil", "revisore dei conti"),
        ("Revisione di società", "Collegio sindacale", "Enti locali", "Terzo settore", "Cooperative",
         "Certificazione di crediti d'imposta", "Fondi pubblici e UE"),
        ("Revisore unico di società", "Sindaco con revisione", "Revisore di enti locali",
         "Revisore di enti del terzo settore", "Certificazione di crediti d'imposta", "Revisione volontaria",
         "Rendicontazione di fondi pubblici", "Organismo di vigilanza 231"),
        "Società di revisione",
        nota=("Nessun obbligo specifico per il revisore persona fisica (D.Lgs. 39/2010), ma risponde in solido con "
              "gli amministratori: RC fortemente consigliata. Se è iscritto all'ordine dei commercialisti vale "
              "il loro obbligo."),
    ),
    Professione(
        "tributarista", "Tributarista / consulente fiscale", "economica", "",
        ("tributarist", "consulente fiscal", "consulente tributari"),
        ("Consulenza fiscale", "Contabilità", "Dichiarazioni dei redditi", "IVA", "Fiscalità immobiliare",
         "Successioni", "Regime forfettario"),
        ("Tenuta della contabilità", "Dichiarazioni fiscali", "Invii telematici (Entratel)", "Pratiche di successione",
         "Registrazione di contratti di locazione", "Ravvedimenti e rateizzazioni", "Visto di conformità"),
        "Studio tributario",
        nota=("Professione non ordinistica (L. 4/2013): nessun obbligo, salvo la polizza dedicata per chi rilascia "
              "il visto di conformità."),
    ),
    Professione(
        "intermediario_assicurativo", "Intermediario assicurativo", "economica",
        "Registro Unico degli Intermediari (RUI - IVASS)",
        ("intermediario assicurativ", "agente di assicurazion", "agente assicurativ", "broker", "subagent",
         "sub agente", "collaboratore assicurativ"),
        ("Rami danni", "Rami vita e investimento", "Previdenza complementare", "RC professionale",
         "Rischi aziendali", "Auto e RCA", "Salute e welfare", "Cauzioni e credito", "Trasporti", "Rischi agricoli"),
        ("Agente (sezione A RUI)", "Broker (sezione B RUI)", "Collaboratore (sezione E RUI)", "Incasso dei premi",
         "Gestione sinistri in delega", "Prodotti di investimento assicurativo (IBIP)", "Intermediazione online",
         "Consulenza a pagamento"),
        "Agenzia di assicurazioni",
        (Obbligo("rc_professionale", "RC professionale", "D.Lgs. 209/2005 (CAP), artt. 110 e 112",
                 "Requisito per l'iscrizione al RUI nelle sezioni A e B, con i massimali aggiornati da IVASS."),),
    ),
    Professione(
        "agente_immobiliare", "Agente immobiliare", "economica", "Registro delle imprese (REA)",
        ("agente immobiliar", "agenti immobiliar", "mediatore immobiliar", "agenzia immobiliar",
         "agente d'affari in mediazione"),
        ("Compravendite residenziali", "Locazioni", "Immobili commerciali", "Immobili di pregio", "Terreni e rustici",
         "Cessione di aziende", "Nuove costruzioni", "Affitti brevi", "Aste immobiliari"),
        ("Mediazione in compravendita", "Mediazione in locazione", "Gestione di affitti brevi", "Valutazioni e stime",
         "Ricezione di caparre e depositi", "Verifiche urbanistiche e catastali", "Proposte d'acquisto e preliminari",
         "Registrazione dei contratti di locazione"),
        "Agenzia immobiliare",
        (Obbligo("rc_professionale", "RC professionale", "L. 39/1989, art. 3 c. 5-bis",
                 "Senza idonea garanzia assicurativa la mediazione è sanzionata (da 3.000 a 5.000 €)."),),
    ),
    Professione(
        "amministratore_condominio", "Amministratore di condominio", "economica", "",
        ("amministratore di condomin", "amministratore condomin", "amministratrice di condomin"),
        ("Condomini residenziali", "Supercondomini", "Immobili commerciali", "Gestione locazioni",
         "Lavori straordinari e bonus edilizi"),
        ("Gestione contabile e rendiconto", "Assemblee e verbali", "Recupero morosità", "Lavori straordinari e appalti",
         "Pratiche bonus edilizi", "Manutenzione e sicurezza impianti", "Gestione del personale (portierato)",
         "Gestione dei sinistri condominiali", "Gestione del conto corrente condominiale"),
        "Studio di amministrazioni condominiali",
        nota=("Nessun obbligo generale: l'assemblea può subordinare la nomina a una polizza RC individuale "
              "(art. 1129 c. 3 c.c.), da adeguare se delibera lavori straordinari."),
    ),
    Professione(
        "agente_commercio", "Agente di commercio", "altro", "Registro delle imprese (REA) ed Enasarco",
        ("agente di commercio", "agenti di commercio", "agente commercial", "rappresentante di commercio",
         "plurimandatari", "monomandatari"),
        ("Alimentare e bevande", "Moda", "Arredamento", "Edilizia", "Macchinari", "Elettronica e informatica",
         "Chimico e farmaceutico", "Cosmetica", "Automotive", "Energia", "Servizi alle imprese"),
        ("Monomandatario", "Plurimandatario", "Raccolta ordini", "Incasso per conto della mandante",
         "Star del credere", "Deposito di merci della mandante", "Coordinamento di sub-agenti",
         "Trasporto di campionari", "Fiere"),
        "Agenzia di rappresentanza",
    ),
)
PER_CHIAVE: dict[str, Professione] = {p.chiave: p for p in PROFESSIONI}
