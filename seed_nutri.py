"""Dati di esempio per NutriStudio: `python seed_nutri.py`.

Crea uno studio già avviato — tre assistiti, un piano pubblicato costruito con
la settimana bilanciata del planner originale, ricette, articoli, misurazioni e
messaggi — così si può girare per l'applicazione senza doverla prima riempire.

È idempotente: se gli assistiti ci sono già non fa nulla (usa `--reset` per
ricominciare da zero).
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta

from nutriapp import create_app
from nutriapp.foodimport import settimana_esempio
from nutriapp.models import (
    Alimento,
    Appuntamento,
    Articolo,
    Assistito,
    IngredienteRicetta,
    Messaggio,
    Misurazione,
    Piano,
    Ricetta,
    Settings,
    User,
    VocePiano,
    db,
)

GIORNI_INDICE = {
    "Lunedì": 0, "Martedì": 1, "Mercoledì": 2, "Giovedì": 3,
    "Venerdì": 4, "Sabato": 5, "Domenica": 6,
}


def _alimento(nome: str) -> Alimento | None:
    return Alimento.query.filter_by(nome=nome).first()


def _piano_da_settimana_esempio(assistito: Assistito) -> Piano:
    """Ricostruisce nel database la settimana già pronta del foglio originale."""
    inizio = date.today() - timedelta(days=date.today().weekday())
    piano = Piano(
        assistito_id=assistito.id,
        titolo="Piano di mantenimento — settembre",
        data_inizio=inizio,
        data_fine=inizio + timedelta(days=27),
        target_kcal=assistito.target_kcal,
        tipo_dieta=assistito.tipo_dieta,
        stato="pubblicato",
        pubblicato_at=datetime.utcnow(),
        note_cliente=(
            "Bevi almeno un litro e mezzo d'acqua al giorno. Lo spuntino del pomeriggio "
            "è facoltativo: saltalo se non hai fame."
        ),
        note_nutrizionista="Controllo fra quattro settimane, valutare le proteine a colazione.",
    )
    db.session.add(piano)
    db.session.commit()

    mancanti = set()
    for giorno in settimana_esempio():
        indice = GIORNI_INDICE.get(giorno["giorno"], 0)
        ordine = 0
        for voce in giorno["voci"]:
            alimento = _alimento(voce["alimento"])
            if alimento is None:
                mancanti.add(voce["alimento"])
                continue
            db.session.add(
                VocePiano(
                    piano_id=piano.id,
                    giorno=indice,
                    pasto=voce["pasto"],
                    ordine=ordine,
                    alimento_id=alimento.id,
                    porzioni=voce["porzioni"] or 1,
                )
            )
            ordine += 1
    db.session.commit()
    if mancanti:
        print(f"  ! {len(mancanti)} alimenti della settimana esempio non trovati in banca dati")
    return piano


def _ricette() -> None:
    definizioni = [
        {
            "titolo": "Ciotola di yogurt greco, mirtilli e mandorle",
            "categoria": "Colazione",
            "tempo_minuti": 5,
            "porzioni": 1,
            "tags": "veloce, proteica, senza glutine",
            "descrizione": "La colazione che regge fino a mezzogiorno senza cucinare nulla.",
            "procedimento": (
                "Versa lo yogurt in una ciotola.\n"
                "Aggiungi i mirtilli e le mandorle tritate grossolanamente.\n"
                "Se serve dolcezza, un cucchiaino di miele: non di più."
            ),
            "ingredienti": [
                ("Yogurt, Greek, plain, nonfat", 170),
                ("Blueberries, raw", 80),
                ("Nuts, almonds, dry roasted, with salt added", 15),
            ],
        },
        {
            "titolo": "Pollo al limone con broccoli al vapore",
            "categoria": "Secondo piatto",
            "tempo_minuti": 25,
            "porzioni": 2,
            "tags": "proteica, senza lattosio",
            "descrizione": "Il secondo di riferimento: si prepara in venticinque minuti e non stanca.",
            "procedimento": (
                "Taglia il petto di pollo a fette spesse un dito.\n"
                "Scalda una padella antiaderente con un filo d'olio, rosola il pollo tre minuti per lato.\n"
                "Sfuma con il succo di mezzo limone e lascia asciugare.\n"
                "Nel frattempo cuoci i broccoli al vapore per otto minuti: devono restare sodi.\n"
                "Servi insieme, con una macinata di pepe."
            ),
            "ingredienti": [
                ("Chicken, breast, boneless, skinless, raw", 300),
                ("Broccoli, raw", 300),
                ("Olio extravergine d'oliva", 10),
            ],
        },
        {
            "titolo": "Insalata di lenticchie, pomodorini e spinaci",
            "categoria": "Primo piatto",
            "tempo_minuti": 30,
            "porzioni": 2,
            "tags": "vegana, ricca di fibre",
            "descrizione": "Piatto unico vegetale, buono anche freddo il giorno dopo.",
            "procedimento": (
                "Lessa le lenticchie in acqua non salata finché sono tenere ma intere.\n"
                "Scolale e falle raffreddare.\n"
                "Unisci gli spinaci lavati, i pomodorini a metà e un filo d'olio.\n"
                "Sala alla fine, altrimenti le lenticchie restano dure."
            ),
            "ingredienti": [
                ("Lentils, dry", 120),
                ("Spinach, baby", 100),
                ("Tomatoes, grape, raw", 150),
                ("Olio extravergine d'oliva", 15),
            ],
        },
        {
            "titolo": "Salmone al forno con patate dolci",
            "categoria": "Secondo piatto",
            "tempo_minuti": 40,
            "porzioni": 2,
            "tags": "omega 3, senza glutine",
            "descrizione": "Una teglia sola, forno a 200 gradi, il resto si fa da sé.",
            "procedimento": (
                "Taglia le patate dolci a cubi di due centimetri e condiscile con olio e rosmarino.\n"
                "Inforna a 200 °C per venti minuti.\n"
                "Aggiungi i tranci di salmone nella stessa teglia e prosegui per dodici minuti.\n"
                "Il salmone è pronto quando si sfalda con la forchetta."
            ),
            "ingredienti": [
                ("Fish, salmon, Atlantic, farm raised, raw", 300),
                ("Sweet potatoes, orange flesh, without skin, raw", 400),
                ("Olio extravergine d'oliva", 15),
            ],
        },
    ]

    for definizione in definizioni:
        ingredienti = definizione.pop("ingredienti")
        ricetta = Ricetta(**definizione)
        ricetta.assegna_slug()
        db.session.add(ricetta)
        db.session.commit()
        for ordine, (nome, grammi) in enumerate(ingredienti):
            alimento = _alimento(nome)
            db.session.add(
                IngredienteRicetta(
                    ricetta_id=ricetta.id,
                    alimento_id=alimento.id if alimento else None,
                    testo=None if alimento else nome,
                    grammi=grammi,
                    ordine=ordine,
                )
            )
        db.session.commit()


def _articoli(autore: str) -> None:
    definizioni = [
        {
            "titolo": "Perché il peso oscilla di due chili in una settimana",
            "categoria": "Educazione alimentare",
            "sommario": "Acqua, glicogeno e sale spiegano quasi tutte le oscillazioni a breve termine. Ecco come leggere la bilancia senza farsi rovinare la giornata.",
            "corpo": (
                "La bilancia misura tutto quello che c'è nel corpo: massa grassa, muscoli, ossa, "
                "contenuto intestinale e soprattutto acqua. L'acqua è la voce che si muove di più "
                "e la più rapida a cambiare.\n\n"
                "Ogni grammo di glicogeno immagazzinato nei muscoli trattiene con sé circa tre "
                "grammi d'acqua. Una cena più ricca di carboidrati del solito può quindi tradursi "
                "in un chilo in più il mattino dopo, senza che sia stato accumulato un solo grammo "
                "di grasso.\n\n"
                "Il sale funziona allo stesso modo: una pizza il sabato sera si legge sulla "
                "bilancia della domenica. È acqua, e se ne va da sola nel giro di due o tre giorni.\n\n"
                "La regola pratica: pesati sempre nelle stesse condizioni — al mattino, a digiuno, "
                "dopo essere andato in bagno — e guarda la media delle ultime due settimane, non il "
                "numero di stamattina. La tendenza è il dato utile; il singolo valore è rumore."
            ),
            "tags": "peso, bilancia, acqua",
        },
        {
            "titolo": "Le proteine a colazione cambiano la fame di mezza giornata",
            "categoria": "Educazione alimentare",
            "sommario": "Una colazione da venticinque grammi di proteine rende lo spuntino delle undici meno urgente. Come costruirla senza stravolgere le abitudini.",
            "corpo": (
                "La colazione italiana classica — caffè e biscotti, oppure cornetto al bar — porta "
                "quasi solo carboidrati raffinati. Il risultato è la fame delle undici, che di "
                "solito viene tamponata con altri carboidrati.\n\n"
                "Aggiungere una quota proteica non significa rivoluzionare tutto. Uno yogurt greco, "
                "due uova, o del latte con una manciata di frutta secca portano la colazione fra i "
                "venti e i venticinque grammi di proteine.\n\n"
                "Non serve eliminare i carboidrati: servono accanto, non da soli. Il pane integrale "
                "con le uova funziona meglio delle uova da sole, perché regge fino a pranzo senza "
                "cali di concentrazione."
            ),
            "tags": "colazione, proteine, sazietà",
        },
        {
            "titolo": "Come leggere un'etichetta in trenta secondi",
            "categoria": "Educazione alimentare",
            "sommario": "Tre punti da guardare al supermercato prima di mettere qualcosa nel carrello.",
            "corpo": (
                "Primo: la lista degli ingredienti è in ordine di peso decrescente. Se lo zucchero "
                "è fra i primi tre, quel prodotto è soprattutto zucchero, qualunque cosa dica la "
                "confezione.\n\n"
                "Secondo: la tabella nutrizionale è per 100 grammi, la porzione reale quasi mai. "
                "Guarda quanti grammi mangi davvero e fai la proporzione.\n\n"
                "Terzo: «senza zuccheri aggiunti» non vuol dire senza zuccheri. Un succo di frutta "
                "senza zuccheri aggiunti resta un bicchiere di zuccheri della frutta.\n\n"
                "Con questi tre passaggi si scarta la maggior parte dei prodotti che sembrano "
                "salutari e non lo sono."
            ),
            "tags": "spesa, etichette, supermercato",
        },
        {
            "titolo": "Camminare non è un ripiego",
            "categoria": "Sport e movimento",
            "sommario": "Ottomila passi al giorno spostano il bilancio energetico più di quanto si creda, e sono l'unica attività che quasi nessuno abbandona.",
            "corpo": (
                "L'attività fisica che funziona è quella che si continua a fare. La camminata ha "
                "un tasso di abbandono bassissimo perché non richiede attrezzatura, palestra o "
                "cambio di vestiti.\n\n"
                "Ottomila passi corrispondono, per una persona di settanta chili, a circa duecento "
                "e cinquanta calorie: nell'arco di una settimana sono quasi milleottocento.\n\n"
                "Il modo più semplice per arrivarci è non cercare di arrivarci in un'unica sessione: "
                "scendere una fermata prima, fare le scale, una passeggiata di venti minuti dopo "
                "cena. Sono tre abitudini piccole che sommate bastano."
            ),
            "tags": "movimento, camminata, abitudini",
        },
        {
            "titolo": "Posso saltare uno spuntino del piano?",
            "categoria": "Domande frequenti",
            "sommario": "Sì, quasi sempre. Ecco quando invece è meglio non farlo.",
            "corpo": (
                "Gli spuntini nel piano servono a due cose: distribuire meglio le proteine nella "
                "giornata e arrivare al pasto successivo senza fame eccessiva. Se non hai fame e "
                "arrivi a cena tranquillo, saltarlo non compromette nulla.\n\n"
                "Va invece mantenuto in tre casi: se ti alleni nel pomeriggio, se fra pranzo e cena "
                "passano più di sei ore, o se salti lo spuntino e poi ceni il doppio.\n\n"
                "Nel dubbio, scrivimi dai messaggi dell'area riservata: si aggiusta in due minuti."
            ),
            "tags": "spuntini, piano, dubbi",
        },
    ]

    for indice, definizione in enumerate(definizioni):
        articolo = Articolo(
            **definizione,
            autore=autore,
            pubblicato=True,
            data_pubblicazione=date.today() - timedelta(days=indice * 9),
        )
        articolo.assegna_slug()
        articolo.calcola_tempo_lettura()
        db.session.add(articolo)
    db.session.commit()


def popola() -> None:
    settings = Settings.get()
    settings.nome_studio = "Studio Nutrizione Verde"
    settings.professionista = "Dott.ssa Elena Ricci, biologa nutrizionista"
    settings.email_studio = "studio@nutrizioneverde.it"
    settings.telefono_studio = "051 000 1122"
    db.session.commit()

    # --- assistiti -----------------------------------------------------
    anagrafiche = [
        {
            "nome": "Giulia", "cognome": "Bianchi", "email": "giulia.bianchi@example.it",
            "telefono": "333 1234567", "data_nascita": date(1990, 4, 12), "sesso": "F",
            "altezza_cm": 168, "peso_iniziale_kg": 72.4, "obiettivo": "Dimagrimento",
            "tipo_dieta": "Standard", "target_kcal": 1800,
            "allergie": "Intolleranza al lattosio (moderata)",
            "preferenze": "Non ama il pesce azzurro. Cucina la sera, pranza in ufficio.",
            "consenso_privacy": True,
        },
        {
            "nome": "Marco", "cognome": "Ferrari", "email": "marco.ferrari@example.it",
            "telefono": "347 7654321", "data_nascita": date(1985, 9, 30), "sesso": "M",
            "altezza_cm": 181, "peso_iniziale_kg": 78.0, "obiettivo": "Nutrizione sportiva",
            "tipo_dieta": "Standard", "target_kcal": 2600,
            "preferenze": "Corre tre volte a settimana, gara di mezza maratona fra due mesi.",
            "consenso_privacy": True,
        },
        {
            "nome": "Sara", "cognome": "Conti", "email": "sara.conti@example.it",
            "data_nascita": date(1998, 1, 22), "sesso": "F",
            "altezza_cm": 163, "peso_iniziale_kg": 58.2, "obiettivo": "Mantenimento",
            "tipo_dieta": "Vegana", "target_kcal": 1900,
            "preferenze": "Vegana da tre anni, chiede attenzione a ferro e B12.",
            "consenso_privacy": True,
        },
    ]

    assistiti = []
    for dati in anagrafiche:
        assistito = Assistito(**dati)
        db.session.add(assistito)
        assistiti.append(assistito)
    db.session.commit()

    # --- misurazioni: dodici settimane di percorso ----------------------
    andamenti = [
        [72.4, 71.8, 71.5, 70.9, 70.6, 70.1, 69.7, 69.4],
        [78.0, 78.3, 78.1, 78.6, 78.4, 78.9, 79.1, 79.0],
        [58.2, 58.0, 58.3, 58.1, 57.9, 58.2, 58.0, 58.1],
    ]
    for assistito, pesi in zip(assistiti, andamenti):
        for settimana, peso in enumerate(pesi):
            giorno = date.today() - timedelta(weeks=len(pesi) - settimana - 1)
            db.session.add(
                Misurazione(
                    assistito_id=assistito.id,
                    data=giorno,
                    peso_kg=peso,
                    vita_cm=round(84 - settimana * 0.6, 1) if assistito is assistiti[0] else None,
                    note="Misurazione iniziale" if settimana == 0 else None,
                )
            )
    db.session.commit()

    # --- accesso all'area riservata per la prima assistita --------------
    utente = User(
        email="giulia.bianchi@example.it",
        nome=assistiti[0].nome_completo,
        ruolo="cliente",
        assistito_id=assistiti[0].id,
        deve_cambiare_password=False,
    )
    utente.set_password("giulia2026")
    db.session.add(utente)
    db.session.commit()

    # --- piano, ricette, articoli ---------------------------------------
    _piano_da_settimana_esempio(assistiti[0])
    _ricette()
    _articoli(settings.professionista)

    # --- appuntamenti e messaggi ----------------------------------------
    db.session.add(
        Appuntamento(
            assistito_id=assistiti[0].id,
            data_ora=datetime.combine(date.today() + timedelta(days=1), datetime.min.time()).replace(hour=17),
            tipo="Controllo",
            luogo="Studio, via Marconi 12",
        )
    )
    db.session.add(
        Appuntamento(
            assistito_id=assistiti[1].id,
            data_ora=datetime.combine(date.today() + timedelta(days=6), datetime.min.time()).replace(hour=10, minute=30),
            tipo="Videochiamata",
        )
    )
    db.session.add(
        Messaggio(
            assistito_id=assistiti[0].id,
            mittente_ruolo="nutrizionista",
            mittente_nome=settings.professionista,
            testo="Ho pubblicato il piano di settembre: le porzioni della cena sono un po' più alte.",
            letto=True,
        )
    )
    db.session.add(
        Messaggio(
            assistito_id=assistiti[0].id,
            mittente_ruolo="cliente",
            mittente_nome=assistiti[0].nome_completo,
            testo="Grazie! Posso sostituire il salmone del giovedì con del pollo?",
        )
    )
    db.session.commit()


def main() -> int:
    app = create_app()
    with app.app_context():
        if "--reset" in sys.argv:
            db.drop_all()
            db.create_all()
            from nutriapp import _prepara_dati_iniziali

            _prepara_dati_iniziali(app)
            print("Database azzerato e ricaricato.")

        if Assistito.query.count():
            print("Ci sono già degli assistiti: non tocco nulla. Usa --reset per ricominciare.")
            return 0

        popola()
        print("Dati di esempio caricati.")
        print("  Studio   nutrizionista@nutristudio.it / nutristudio (da cambiare al primo accesso)")
        print("  Cliente  giulia.bianchi@example.it / giulia2026")
        print(f"  {Alimento.query.count()} alimenti, {Ricetta.query.count()} ricette, "
              f"{Articolo.query.count()} articoli, {Piano.query.count()} piano pubblicato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
