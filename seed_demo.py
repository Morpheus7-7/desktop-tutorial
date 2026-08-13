"""Carica dati di esempio nel gestionale: `python seed_demo.py`.

Crea clienti (aziende e professionisti), polizze con scadenze varie,
follow-up e un'analisi rischi, per provare subito tutte le funzioni.
"""
import json
from datetime import date, timedelta

from gestionale import create_app
from gestionale.models import Client, FollowUp, Opportunity, Policy, RiskAnalysis, db
from gestionale.risk_engine import analyze_client

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
        partita_iva="01234567890",
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
        ragione_sociale="Ing. Laura Bianchi",
        codice_fiscale="BNCLRA80A41F205X",
        partita_iva="09876543210",
        professione="Ingegnere civile",
        settore="Progettazione strutturale",
        citta="Milano",
        provincia="MI",
        email="laura.bianchi@pec.ordineingegneri.it",
        telefono="02 8765432",
        numero_dipendenti=1,
        fatturato_annuo=180_000,
        descrizione_attivita=(
            "Studio di ingegneria civile: progettazione strutturale, direzione "
            "lavori e collaudi in cantiere. Consulenza tecnica d'ufficio per "
            "tribunali. Una collaboratrice, trasferte frequenti sui cantieri, "
            "gestione documentale in cloud."
        ),
    )
    ristorante = Client(
        tipo="azienda",
        ragione_sociale="Trattoria Da Peppe di Esposito Giuseppe & C. S.a.s.",
        referente="Giuseppe Esposito",
        partita_iva="04455667788",
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
        codice_fiscale="VRDMRC85M12F205Z",
        professione="Capo officina",
        datore_lavoro="Meccanica Padana S.r.l.",
        indirizzo="Via Emilia 45",
        citta="Modena",
        provincia="MO",
        email="marco.verdi@email.it",
        telefono="059 223344",
        descrizione_attivita=(
            "Lavoratore dipendente con famiglia (moglie e due figli minori) e mutuo "
            "sulla prima casa. Pratica sci e moto nel tempo libero. Interessato a "
            "tutela del reddito e salute."
        ),
    )
    db.session.add_all([falegnameria, studio, ristorante, dipendente])
    db.session.flush()

    polizze = [
        Policy(
            client_id=falegnameria.id, compagnia="Generali", numero_polizza="GEN-2024-1181",
            ramo="incendio", premio_annuo=3_800, massimale=2_000_000, provvigione_perc=18,
            data_decorrenza=oggi - timedelta(days=340), data_scadenza=oggi + timedelta(days=25),
            tacito_rinnovo=False, stato="attiva",
        ),
        Policy(
            client_id=falegnameria.id, compagnia="Allianz", numero_polizza="ALZ-88422",
            ramo="rct_rco", premio_annuo=2_450, massimale=3_000_000, provvigione_perc=20,
            data_decorrenza=oggi - timedelta(days=200), data_scadenza=oggi + timedelta(days=165),
            tacito_rinnovo=True, stato="attiva",
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
            data_decorrenza=oggi - timedelta(days=100), data_scadenza=oggi + timedelta(days=265),
            tacito_rinnovo=True, stato="attiva",
        ),
    ]
    db.session.add_all(polizze)

    followups = [
        FollowUp(
            client_id=falegnameria.id, tipo="rinnovo", priorita="alta",
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

    for cliente in (falegnameria, studio, ristorante, dipendente):
        results = analyze_client(cliente)
        db.session.add(
            RiskAnalysis(
                client_id=cliente.id,
                input_text=cliente.descrizione_attivita,
                results_json=json.dumps(results, ensure_ascii=False),
            )
        )

    db.session.commit()
    print("Dati demo caricati: 4 clienti, 5 polizze, 3 follow-up, 3 opportunità, 4 analisi rischi.")
