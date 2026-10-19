"""Carica dati di esempio nel gestionale: `python seed_demo.py`.

Crea clienti (aziende, uno studio legale associato, liberi professionisti,
un dipendente), polizze con scadenze
varie, titoli da incassare e incassati, sinistri, follow-up, opportunità e
analisi rischi, per provare subito tutte le funzioni.

Non crea utenti: al primo accesso il gestionale chiede di creare
l'amministratore.
"""
import json
from datetime import date, timedelta

from gestionale import create_app
from gestionale.models import (
    Claim,
    ClaimNote,
    Client,
    FollowUp,
    Opportunity,
    Policy,
    RiskAnalysis,
    db,
)
from gestionale.risk_engine import analyze_client
from gestionale.titoli import add_months, genera_titoli

app = create_app()

with app.app_context():
    if Client.query.count():
        print("Il database contiene già dei clienti: nessun dato demo caricato.")
        raise SystemExit(0)

    oggi = date.today()

    falegnameria = Client(
        tipo="azienda",
        ragione_sociale="Falegnameria Rossi S.r.l.",
        referente="Mario Rossi",
        partita_iva="01234567897",
        codice_ateco="16.23",
        settore="Lavorazione del legno",
        indirizzo="Via delle Industrie 12",
        citta="Treviso",
        cap="31100",
        provincia="TV",
        email="info@falegnameriarossi.it",
        telefono="0422 123456",
        numero_dipendenti=8,
        fatturato_annuo=1_450_000,
        data_consenso_privacy=oggi - timedelta(days=300),
        data_adeguatezza=oggi - timedelta(days=300),
        descrizione_attivita=(
            "Falegnameria con capannone di 900 mq, magazzino legname e deposito "
            "vernici e solventi. Otto dipendenti tra operai e montatori. Produzione "
            "di mobili su misura venduti anche online tramite e-commerce; consegne "
            "e montaggio presso i clienti con due furgoni aziendali. Partecipa ad "
            "appalti per arredi di scuole e uffici pubblici."
        ),
    )
    studio = Client(
        tipo="professionista",
        ragione_sociale="Laura Bianchi",
        codice_fiscale="BNCLRA80A41F205G",
        partita_iva="09876543217",
        professione="Ingegnere",
        specializzazioni="Strutturale; Edile",
        attivita_svolte="Progettazione strutturale; Direzione lavori; Collaudi; Perizie CTU e CTP",
        inquadramento="libero_professionista",
        albo_ordine="Ordine degli Ingegneri della Provincia di Milano",
        albo_numero="A21456",
        albo_data_iscrizione=date(2006, 3, 15),
        citta="Milano",
        provincia="MI",
        email="laura.bianchi@pec.ordineingegneri.it",
        telefono="02 8765432",
        fatturato_annuo=180_000,
        data_nascita=date(1980, 1, 1),
        data_consenso_privacy=oggi - timedelta(days=400),
        data_adeguatezza=oggi - timedelta(days=400),
        documento_tipo="carta_identita",
        documento_numero="CA12345AB",
        documento_scadenza=oggi + timedelta(days=20),
        descrizione_attivita=(
            "Ingegnere strutturista: progettazione strutturale, direzione "
            "lavori e collaudi in cantiere. Consulenza tecnica d'ufficio per "
            "tribunali. Una collaboratrice, trasferte frequenti sui cantieri, "
            "gestione documentale in cloud."
        ),
    )
    studio_legale = Client(
        tipo="studio",
        ragione_sociale="Studio Legale Associato Ferri & Conti",
        forma_giuridica="Studio associato",
        referente="Avv. Giulia Ferri",
        partita_iva="07219830960",
        codice_ateco="69.10.10",
        professione="Avvocato",
        specializzazioni="Civilista; Giuslavorista; Famiglia e minori",
        attivita_svolte="Contenzioso giudiziale; Consulenza stragiudiziale; Curatore o commissario giudiziale",
        numero_professionisti=3,
        numero_dipendenti=2,
        fatturato_annuo=420_000,
        indirizzo="Corso di Porta Vittoria 18",
        citta="Milano",
        cap="20122",
        provincia="MI",
        email="segreteria@ferriconti.it",
        pec="ferriconti@pec.it",
        telefono="02 5512345",
        data_consenso_privacy=oggi - timedelta(days=200),
        data_adeguatezza=oggi - timedelta(days=200),
        descrizione_attivita=(
            "Studio legale associato con tre avvocati, una praticante e due "
            "segretarie: contenzioso civile e del lavoro, diritto di famiglia, "
            "curatele fallimentari per il Tribunale di Milano. Sede in affitto, "
            "archivio digitale in cloud con dati giudiziari dei clienti."
        ),
    )
    pediatra = Client(
        tipo="professionista",
        ragione_sociale="Paolo Neri",
        codice_fiscale="NREPLA75C10L736K",
        partita_iva="03344556679",
        professione="Pediatra",
        specializzazioni="Pediatria generale; Allergologia e immunologia pediatrica",
        attivita_svolte="Visite ambulatoriali private; Bilanci di salute; Vaccinazioni",
        inquadramento="convenzionato",
        albo_ordine="Ordine dei Medici Chirurghi e degli Odontoiatri di Venezia",
        albo_numero="9876",
        albo_data_iscrizione=date(2001, 11, 5),
        citta="Venezia",
        provincia="VE",
        email="dott.neri@email.it",
        telefono="041 778899",
        fatturato_annuo=95_000,
        data_nascita=date(1975, 3, 10),
        data_consenso_privacy=oggi - timedelta(days=30),
        descrizione_attivita=(
            "Pediatra di libera scelta con circa 800 assistiti; nel pomeriggio "
            "visite private e test allergologici in ambulatorio. Usa una "
            "cartella clinica elettronica in cloud."
        ),
    )
    ristorante = Client(
        tipo="azienda",
        ragione_sociale="Trattoria Da Peppe di Esposito Giuseppe & C. S.a.s.",
        referente="Giuseppe Esposito",
        partita_iva="04455667784",
        codice_ateco="56.10",
        settore="Ristorazione",
        citta="Napoli",
        provincia="NA",
        email="dapeppe@gmail.com",
        telefono="081 5544332",
        numero_dipendenti=6,
        fatturato_annuo=520_000,
        descrizione_attivita=(
            "Trattoria con cucina a legna e forno per pizza, 60 coperti interni e "
            "dehors estivo aperto al pubblico. Sei dipendenti tra cucina e sala. "
            "Cantina con merce e cella frigorifera. Servizio di consegna a "
            "domicilio con due scooter. Prenotazioni e pagamenti online."
        ),
    )
    dipendente = Client(
        tipo="dipendente",
        ragione_sociale="Marco Verdi",
        codice_fiscale="VRDMRC85M12F205X",
        professione="Capo officina",
        datore_lavoro="Meccanica Padana S.r.l.",
        indirizzo="Via Emilia 45",
        citta="Modena",
        provincia="MO",
        email="marco.verdi@email.it",
        telefono="059 223344",
        data_nascita=date(1985, 8, 12),
        data_consenso_privacy=oggi - timedelta(days=100),
        consenso_marketing=True,
        data_adeguatezza=oggi - timedelta(days=100),
        documento_tipo="patente",
        documento_numero="MO1234567X",
        documento_scadenza=oggi + timedelta(days=900),
        descrizione_attivita=(
            "Lavoratore dipendente con famiglia (moglie e due figli minori) e mutuo "
            "sulla prima casa. Pratica sci e moto nel tempo libero. Interessato a "
            "tutela del reddito e salute."
        ),
    )
    db.session.add_all([falegnameria, studio, studio_legale, pediatra, ristorante, dipendente])
    db.session.flush()
    # L'avvocata Ferri è socia dello studio legale (cliente anche lei).
    avvocata = Client(
        tipo="professionista",
        ragione_sociale="Giulia Ferri",
        codice_fiscale="FRRGLI82D45F205U",
        professione="Avvocato",
        specializzazioni="Civilista; Famiglia e minori",
        attivita_svolte="Contenzioso giudiziale; Mediatore civile",
        inquadramento="libero_professionista",
        albo_ordine="Ordine degli Avvocati di Milano",
        albo_numero="M34567",
        albo_data_iscrizione=date(2009, 1, 20),
        studio_id=studio_legale.id,
        citta="Milano",
        provincia="MI",
        email="g.ferri@ferriconti.it",
        data_nascita=date(1982, 4, 5),
        data_consenso_privacy=oggi - timedelta(days=200),
        descrizione_attivita="Avvocata civilista e mediatrice, socia dello studio Ferri & Conti.",
    )
    db.session.add(avvocata)
    db.session.flush()

    polizze = [
        Policy(
            client_id=falegnameria.id, compagnia="Generali", numero_polizza="GEN-2024-1181",
            ramo="incendio", premio_annuo=3_800, massimale=2_000_000, provvigione_perc=18,
            frazionamento="semestrale",
            data_decorrenza=oggi - timedelta(days=340), data_scadenza=oggi + timedelta(days=25),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=falegnameria.id, compagnia="Allianz", numero_polizza="ALZ-88422",
            ramo="rct_rco", premio_annuo=2_450, massimale=3_000_000, provvigione_perc=20,
            frazionamento="trimestrale",
            data_decorrenza=oggi - timedelta(days=200), data_scadenza=oggi + timedelta(days=165),
            tacito_rinnovo=True, preavviso_disdetta_giorni=60, stato="attiva",
        ),
        Policy(
            client_id=studio.id, compagnia="Lloyd's", numero_polizza="LL-RCPRO-5521",
            ramo="rc_professionale", premio_annuo=1_950, massimale=1_500_000, provvigione_perc=15,
            data_decorrenza=oggi - timedelta(days=360), data_scadenza=oggi + timedelta(days=5),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=ristorante.id, compagnia="UnipolSai", numero_polizza="UNI-77103",
            ramo="rct_rco", premio_annuo=1_600, massimale=2_000_000, provvigione_perc=22,
            data_decorrenza=oggi - timedelta(days=400), data_scadenza=oggi - timedelta(days=12),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=dipendente.id, compagnia="Poste Vita", numero_polizza="PV-INF-3390",
            ramo="infortuni", premio_annuo=420, massimale=200_000, provvigione_perc=25,
            frazionamento="mensile",
            data_decorrenza=oggi - timedelta(days=100), data_scadenza=oggi + timedelta(days=265),
            tacito_rinnovo=True, stato="attiva",
        ),
        # Date future: polizza che decorre tra 20 giorni (non ancora in vigore),
        # poliennale di 3 anni e polizza con il termine di disdetta tra 15 giorni.
        Policy(
            client_id=falegnameria.id, compagnia="AXA", numero_polizza="AXA-CYB-2031",
            ramo="cyber", premio_annuo=1_200, massimale=500_000, provvigione_perc=15,
            data_decorrenza=oggi + timedelta(days=20), data_scadenza=add_months(oggi + timedelta(days=20), 12),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=ristorante.id, compagnia="Cattolica", numero_polizza="CAT-INC-4410",
            ramo="incendio", premio_annuo=2_100, massimale=1_000_000, provvigione_perc=17,
            frazionamento="semestrale",
            data_decorrenza=oggi - timedelta(days=420),
            data_scadenza=add_months(oggi - timedelta(days=420), 36),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=studio_legale.id, compagnia="AIG", numero_polizza="AIG-RCPRO-7788",
            ramo="rc_professionale", premio_annuo=3_400, massimale=2_000_000, provvigione_perc=15,
            data_decorrenza=oggi - timedelta(days=150), data_scadenza=oggi + timedelta(days=215),
            tacito_rinnovo=False, stato="attiva",
        ),
        # RC del pediatra con massimale sotto il minimo del DM 232/2023: la
        # scheda lo segnala.
        Policy(
            client_id=pediatra.id, compagnia="AmTrust", numero_polizza="AMT-MED-3321",
            ramo="rc_professionale", premio_annuo=780, massimale=500_000, provvigione_perc=15,
            data_decorrenza=oggi - timedelta(days=60), data_scadenza=add_months(oggi - timedelta(days=60), 12),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=studio.id, compagnia="Reale Mutua", numero_polizza="RM-FUR-0937",
            ramo="furto", premio_annuo=680, massimale=50_000, provvigione_perc=20,
            data_decorrenza=oggi - timedelta(days=290), data_scadenza=oggi + timedelta(days=75),
            tacito_rinnovo=True, preavviso_disdetta_giorni=60, stato="attiva",
        ),
    ]
    db.session.add_all(polizze)
    db.session.flush()

    # Titoli dell'annualità in corso: incassati quelli già scaduti, tranne
    # uno lasciato arretrato per mostrare l'avviso di copertura sospesa.
    for polizza in polizze:
        for titolo in genera_titoli(polizza):
            if titolo.data_effetto <= oggi - timedelta(days=5):
                titolo.stato = "incassato"
                titolo.data_incasso = titolo.data_effetto + timedelta(days=3)
                titolo.mezzo_pagamento = "bonifico"
    # L'ultima rata pagata (non il primo premio) torna da incassare: arretrata.
    arretrato = max(
        (t for t in polizze[1].titoli if t.stato == "incassato" and t.tipo != "perfezionamento"),
        key=lambda t: t.data_effetto,
    )
    arretrato.stato, arretrato.data_incasso, arretrato.mezzo_pagamento = "da_incassare", None, None

    sinistri = [
        Claim(
            numero=f"SIN-{oggi.year}-0001", client_id=falegnameria.id, policy_id=polizze[1].id,
            tipologia="danni_terzi", data_evento=oggi - timedelta(days=40),
            data_denuncia=oggi - timedelta(days=38), luogo="Cantiere scuola media, Treviso",
            descrizione="Durante il montaggio di un armadio a muro un pannello è caduto danneggiando il pavimento in parquet.",
            controparte="Comune di Treviso", perito="Studio Peritale Nordest",
            importo_richiesto=6_500, importo_riservato=5_000, stato="perizia",
        ),
        Claim(
            numero=f"SIN-{oggi.year}-0002", client_id=ristorante.id,
            tipologia="acqua", data_evento=oggi - timedelta(days=4),
            luogo="Cantina della trattoria", descrizione="Rottura del tubo della cella frigorifera con allagamento della cantina.",
            importo_richiesto=3_200, stato="aperto",
        ),
    ]
    db.session.add_all(sinistri)
    db.session.flush()
    sinistri[0].eventi.extend([
        ClaimNote(tipo="stato", testo="Sinistro aperto.", username="demo"),
        ClaimNote(tipo="stato", testo="Stato: Aperto → In perizia. Sopralluogo fissato.", username="demo"),
    ])
    sinistri[1].eventi.append(ClaimNote(tipo="stato", testo="Sinistro aperto.", username="demo"))

    followups = [
        FollowUp(
            client_id=falegnameria.id, policy_id=polizze[0].id, tipo="rinnovo", priorita="alta",
            titolo="Preparare rinnovo polizza incendio GEN-2024-1181",
            descrizione="Chiedere aggiornamento valori di magazzino prima del rinnovo.",
            data_scadenza=oggi + timedelta(days=10),
        ),
        FollowUp(
            client_id=studio.id, tipo="chiamata", priorita="alta",
            titolo="Richiamare per rinnovo RC professionale",
            data_scadenza=oggi,
        ),
        FollowUp(
            client_id=ristorante.id, tipo="preventivo", priorita="media",
            titolo="Preventivo polizza incendio + furto per la trattoria",
            descrizione="Il cliente è rimasto senza copertura RCT: sollecitare.",
            data_scadenza=oggi - timedelta(days=3),
        ),
    ]
    db.session.add_all(followups)

    opportunita = [
        Opportunity(
            client_id=falegnameria.id, titolo="Proposta Cyber Risk",
            ramo="cyber", fase="preventivo", premio_stimato=1_400, provvigione_perc=20,
            priorita="alta", origine="analisi_rischi",
            note="Vendono online: esposti a ransomware e GDPR. Copertura scoperta dall'analisi.",
        ),
        Opportunity(
            client_id=ristorante.id, titolo="Pacchetto Incendio + Furto",
            ramo="incendio", fase="trattativa", premio_stimato=2_100, provvigione_perc=20,
            priorita="alta", origine="analisi_rischi",
            note="Cliente rimasto senza RCT: occasione per proporre pacchetto completo.",
        ),
        Opportunity(
            client_id=dipendente.id, titolo="Polizza salute famiglia",
            ramo="malattia", fase="contatto", premio_stimato=900, provvigione_perc=22,
            priorita="media", origine="analisi_rischi",
        ),
    ]
    db.session.add_all(opportunita)

    for cliente in (falegnameria, studio, studio_legale, pediatra, ristorante, dipendente):
        results = analyze_client(cliente)
        db.session.add(
            RiskAnalysis(
                client_id=cliente.id,
                input_text=cliente.descrizione_attivita,
                results_json=json.dumps(results, ensure_ascii=False),
            )
        )

    db.session.commit()
    print(
        "Dati demo caricati: 7 clienti (tra cui uno studio legale associato con un'avvocata "
        "collegata e un pediatra), 10 polizze con i relativi titoli, 2 sinistri, "
        "3 follow-up, 3 opportunità, 6 analisi rischi.\n"
        "Avvia il gestionale: al primo accesso ti verrà chiesto di creare l'amministratore."
    )
