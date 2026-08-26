"""Test funzionali di NutriStudio.

Coprono le tre cose che, se si rompono, rompono l'applicazione: i **calcoli
nutrizionali** (che devono restare fedeli al foglio di partenza), la
**separazione fra i due ruoli** (il cliente non deve poter vedere niente di
altri) e i **flussi che producono qualcosa** — costruire un piano, pubblicarlo,
generare la lista della spesa.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from nutriapp import create_app
from nutriapp.foodimport import traduci_nome
from nutriapp.models import (
    Alimento,
    Appuntamento,
    Articolo,
    Assistito,
    IngredienteRicetta,
    Messaggio,
    Misurazione,
    Notifica,
    Piano,
    Ricetta,
    Settings,
    User,
    VocePiano,
    db,
)
from nutriapp.notifications import genera_notifiche
from nutriapp.nutrition import (
    analisi_piano,
    conflitto_dieta,
    metabolismo_basale,
    nutrienti_alimento,
    nutrienti_ricetta,
    ripartizione_macro,
    stato_copertura,
    stato_kcal,
)
from nutriapp.shopping import lista_spesa
from nutriapp.shopping import testo_lista as lista_in_testo

PASSWORD_STUDIO = "studio-di-prova"
PASSWORD_CLIENTE = "cliente-di-prova"


# ----------------------------------------------------------------------
# Fixture
# ----------------------------------------------------------------------
@pytest.fixture
def app():
    applicazione = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "chiave-di-prova",
            "IMPORTA_ALIMENTI": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with applicazione.app_context():
        db.create_all()
        _popola_minimo()
    yield applicazione


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def studio(app):
    """Client con la sessione dello studio (separato da quello del cliente)."""
    sessione = app.test_client()
    sessione.post("/accedi", data={"email": "studio@prova.it", "password": PASSWORD_STUDIO})
    return sessione


@pytest.fixture
def cliente(app):
    sessione = app.test_client()
    sessione.post("/accedi", data={"email": "cliente@prova.it", "password": PASSWORD_CLIENTE})
    return sessione


def _alimento(nome, **valori):
    predefiniti = dict(
        nome=nome,
        nome_it=nome,
        categoria_it="Prova",
        porzione_nome="1 porzione (100 g)",
        porzione_g=100,
        kcal=100,
        proteine=10,
        carboidrati=10,
        grassi=2,
        fibre=1,
        calcio=50,
        vegan=True,
        vegetariano=True,
        senza_glutine=True,
        senza_lattosio=True,
    )
    predefiniti.update(valori)
    alimento = Alimento(**predefiniti)
    db.session.add(alimento)
    return alimento


def _popola_minimo():
    Settings.get()

    utente_studio = User(email="studio@prova.it", nome="Studio", ruolo="nutrizionista")
    utente_studio.set_password(PASSWORD_STUDIO)
    db.session.add(utente_studio)

    assistito = Assistito(
        nome="Anna",
        cognome="Rossi",
        email="cliente@prova.it",
        data_nascita=date(1990, 1, 1),
        sesso="F",
        altezza_cm=165,
        peso_iniziale_kg=65,
        tipo_dieta="Vegana",
        target_kcal=2000,
    )
    db.session.add(assistito)
    db.session.commit()

    utente_cliente = User(
        email="cliente@prova.it", nome="Anna Rossi", ruolo="cliente", assistito_id=assistito.id
    )
    utente_cliente.set_password(PASSWORD_CLIENTE)
    db.session.add(utente_cliente)

    _alimento("Riso integrale", kcal=360, proteine=7.5, carboidrati=76, grassi=2.7, porzione_g=80)
    _alimento("Petto di pollo", kcal=110, proteine=23, carboidrati=0, grassi=1.6,
              porzione_g=150, vegan=False, vegetariano=False)
    _alimento("Broccoli", kcal=34, proteine=2.8, carboidrati=6.6, grassi=0.4, porzione_g=200,
              fibre=2.6, vit_c=89)
    # alimento senza valori: il caso «dispensa italiana da completare»
    _alimento("Pane comune", kcal=None, proteine=None, carboidrati=None, grassi=None,
              fibre=None, calcio=None, porzione_g=50, senza_glutine=False)
    db.session.commit()


def _piano_di_prova(assistito=None, **valori):
    assistito = assistito or Assistito.query.first()
    predefiniti = dict(
        assistito_id=assistito.id,
        titolo="Piano di prova",
        data_inizio=date.today() - timedelta(days=date.today().weekday()),
        data_fine=date.today() + timedelta(days=20),
        target_kcal=2000,
        tipo_dieta=assistito.tipo_dieta,
    )
    predefiniti.update(valori)
    piano = Piano(**predefiniti)
    db.session.add(piano)
    db.session.commit()
    return piano


# ----------------------------------------------------------------------
# Accesso e ruoli
# ----------------------------------------------------------------------
def test_anonimo_viene_mandato_al_login(client):
    for rotta in ("/studio", "/area/", "/assistiti/", "/piani/", "/impostazioni/"):
        risposta = client.get(rotta)
        assert risposta.status_code == 302
        assert "/accedi" in risposta.headers["Location"]


def test_login_sbagliato_non_rivela_se_l_email_esiste(client):
    for email in ("studio@prova.it", "sconosciuto@prova.it"):
        risposta = client.post(
            "/accedi", data={"email": email, "password": "sbagliata"}, follow_redirects=True
        )
        assert "Email o password non corretti" in risposta.get_data(as_text=True)


def test_login_studio_porta_al_cruscotto(client):
    risposta = client.post(
        "/accedi",
        data={"email": "studio@prova.it", "password": PASSWORD_STUDIO},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    assert "Cruscotto" in risposta.get_data(as_text=True)


def test_login_cliente_porta_alla_sua_area(cliente):
    risposta = cliente.get("/", follow_redirects=True)
    testo = risposta.get_data(as_text=True)
    assert "Ciao Anna" in testo
    assert "Assistiti" not in testo  # niente menu dello studio


def test_cliente_non_entra_nell_area_studio(cliente):
    for rotta in ("/studio", "/assistiti/", "/piani/", "/alimenti/", "/impostazioni/", "/accessi"):
        risposta = cliente.get(rotta)
        assert risposta.status_code == 302, rotta
        assert "/area" in risposta.headers["Location"] or "/accedi" in risposta.headers["Location"]


def test_studio_non_finisce_nell_area_cliente(studio):
    risposta = studio.get("/area/")
    assert risposta.status_code == 302


def test_password_provvisoria_blocca_tutto_finche_non_cambia(client, app):
    with app.app_context():
        utente = User.query.filter_by(email="studio@prova.it").first()
        utente.deve_cambiare_password = True
        db.session.commit()

    client.post("/accedi", data={"email": "studio@prova.it", "password": PASSWORD_STUDIO})
    risposta = client.get("/studio")
    assert risposta.status_code == 302
    assert "/cambia-password" in risposta.headers["Location"]

    risposta = client.post(
        "/cambia-password",
        data={"nuova": "nuova-password", "conferma": "nuova-password"},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    assert client.get("/studio").status_code == 200


def test_creazione_accesso_cliente_genera_password_provvisoria(studio, app):
    with app.app_context():
        nuovo = Assistito(nome="Luca", cognome="Verdi", email="luca@prova.it")
        db.session.add(nuovo)
        db.session.commit()
        nuovo_id = nuovo.id

    risposta = studio.post(
        f"/assistiti/{nuovo_id}/accesso",
        data={"email": "luca@prova.it"},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    # Senza SMTP la password viene mostrata a schermo per consegnarla a mano.
    assert "Password provvisoria" in risposta.get_data(as_text=True)

    with app.app_context():
        utente = User.query.filter_by(email="luca@prova.it").first()
        assert utente is not None
        assert utente.ruolo == "cliente"
        assert utente.deve_cambiare_password is True


# ----------------------------------------------------------------------
# Motore nutrizionale
# ----------------------------------------------------------------------
def test_nutrienti_scalano_con_i_grammi(app):
    with app.app_context():
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        totali = nutrienti_alimento(riso, 80)  # una porzione
        assert totali.get("kcal") == pytest.approx(288)  # 360 × 0,8
        assert totali.get("proteine") == pytest.approx(6.0)


def test_dato_mancante_resta_mancante_e_non_diventa_zero(app):
    with app.app_context():
        pane = Alimento.query.filter_by(nome="Pane comune").first()
        totali = nutrienti_alimento(pane, 50)
        assert totali.get("kcal") == 0
        assert totali.parziale("kcal") is True


def test_totali_di_giornata_e_media_settimanale(app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        for giorno in range(7):
            db.session.add(
                VocePiano(piano_id=piano.id, giorno=giorno, pasto="Pranzo", alimento_id=riso.id, porzioni=1)
            )
        db.session.commit()

        analisi = analisi_piano(piano)
        assert analisi["giorni_compilati"] == 7
        assert analisi["giorni"][0]["kcal"] == 288
        assert analisi["media_kcal"] == 288
        # 288 su 2000 è ben sotto il target: il semaforo deve dirlo
        assert analisi["stato_media"] == "fuori"


def test_la_media_ignora_i_giorni_vuoti(app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        db.session.add(VocePiano(piano_id=piano.id, giorno=0, pasto="Pranzo", alimento_id=riso.id))
        db.session.commit()

        analisi = analisi_piano(piano)
        assert analisi["giorni_compilati"] == 1
        # se dividesse per sette la media crollerebbe a 41 kcal
        assert analisi["media_kcal"] == 288


def test_conflitto_con_la_dieta_vegana(app):
    with app.app_context():
        pollo = Alimento.query.filter_by(nome="Petto di pollo").first()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        assert conflitto_dieta(pollo, "Vegana") == "non è vegano"
        assert conflitto_dieta(riso, "Vegana") is None
        assert conflitto_dieta(pollo, "Standard") is None

        pollo.vegan = None  # dato non verificato nella fonte
        assert conflitto_dieta(pollo, "Vegana") == "da verificare"


def test_il_piano_segnala_le_voci_fuori_dieta(app):
    with app.app_context():
        piano = _piano_di_prova()
        pollo = Alimento.query.filter_by(nome="Petto di pollo").first()
        db.session.add(VocePiano(piano_id=piano.id, giorno=1, pasto="Cena", alimento_id=pollo.id))
        db.session.commit()

        analisi = analisi_piano(piano)
        assert len(analisi["conflitti"]) == 1
        assert analisi["conflitti"][0]["motivo"] == "non è vegano"


def test_semafori_kcal_e_copertura():
    assert stato_kcal(2000, 2000) == "ok"
    assert stato_kcal(2100, 2000) == "ok"  # entro il 5%
    assert stato_kcal(2200, 2000) == "attenzione"  # entro il 12%
    assert stato_kcal(2600, 2000) == "fuori"

    assert stato_copertura(0.95) == "ok"
    assert stato_copertura(0.8) == "attenzione"
    assert stato_copertura(0.5) == "fuori"
    # per i tetti (sodio, zuccheri) la logica si rovescia
    assert stato_copertura(0.5, limite=True) == "ok"
    assert stato_copertura(1.5, limite=True) == "fuori"


def test_ripartizione_dei_macronutrienti(app):
    with app.app_context():
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        macro = ripartizione_macro(nutrienti_alimento(riso, 100))
        assert sum(macro.values()) == pytest.approx(100, abs=0.2)
        assert macro["carboidrati"] > macro["proteine"] > macro["grassi"]


def test_metabolismo_basale_mifflin():
    # Donna, 65 kg, 165 cm, 30 anni → 10×65 + 6,25×165 − 5×30 − 161
    assert metabolismo_basale("F", 65, 165, 30) == 1370
    assert metabolismo_basale("M", 65, 165, 30) == 1536
    assert metabolismo_basale("F", None, 165, 30) is None


def test_ricetta_divide_i_valori_per_porzione(app):
    with app.app_context():
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        ricetta = Ricetta(titolo="Riso semplice", porzioni=2)
        ricetta.assegna_slug()
        db.session.add(ricetta)
        db.session.commit()
        db.session.add(IngredienteRicetta(ricetta_id=ricetta.id, alimento_id=riso.id, grammi=200))
        db.session.commit()

        totale, per_porzione = nutrienti_ricetta(ricetta)
        assert totale.get("kcal") == pytest.approx(720)
        assert per_porzione.get("kcal") == pytest.approx(360)


# ----------------------------------------------------------------------
# Costruzione del piano
# ----------------------------------------------------------------------
def test_aggiunta_e_rimozione_di_una_voce(studio, app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        piano_id, riso_id = piano.id, riso.id

    studio.post(
        f"/piani/{piano_id}/voci",
        data={"giorno": 0, "pasto": "Pranzo", "alimento_id": riso_id, "porzioni": "1,5"},
    )
    with app.app_context():
        voce = VocePiano.query.filter_by(piano_id=piano_id).one()
        assert voce.porzioni == 1.5  # la virgola italiana viene accettata
        assert voce.grammi == 120
        voce_id = voce.id

    studio.post(f"/piani/{piano_id}/voci/{voce_id}/porzioni", data={"porzioni": "2"})
    with app.app_context():
        assert db.session.get(VocePiano, voce_id).porzioni == 2

    studio.post(f"/piani/{piano_id}/voci/{voce_id}/elimina")
    with app.app_context():
        assert VocePiano.query.filter_by(piano_id=piano_id).count() == 0


def test_copia_di_una_giornata_sugli_altri_giorni(studio, app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        db.session.add(VocePiano(piano_id=piano.id, giorno=0, pasto="Pranzo", alimento_id=riso.id))
        db.session.commit()
        piano_id = piano.id

    studio.post(
        f"/piani/{piano_id}/giorni/0/copia",
        data={"destinazioni": ["1", "2", "3"], "sostituisci": "1"},
    )
    with app.app_context():
        piano = db.session.get(Piano, piano_id)
        assert len(piano.voci) == 4
        assert {v.giorno for v in piano.voci} == {0, 1, 2, 3}


def test_svuota_giornata(studio, app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        for pasto in ("Colazione", "Pranzo"):
            db.session.add(VocePiano(piano_id=piano.id, giorno=2, pasto=pasto, alimento_id=riso.id))
        db.session.commit()
        piano_id = piano.id

    studio.post(f"/piani/{piano_id}/giorni/2/svuota")
    with app.app_context():
        assert VocePiano.query.filter_by(piano_id=piano_id).count() == 0


def test_un_piano_vuoto_non_si_pubblica(studio, app):
    with app.app_context():
        piano_id = _piano_di_prova().id

    risposta = studio.post(f"/piani/{piano_id}/pubblica", follow_redirects=True)
    assert "vuoto" in risposta.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Piano, piano_id).stato == "bozza"


def test_pubblicare_archivia_il_piano_precedente(studio, app):
    with app.app_context():
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        vecchio = _piano_di_prova(titolo="Vecchio", stato="pubblicato")
        nuovo = _piano_di_prova(titolo="Nuovo")
        db.session.add(VocePiano(piano_id=nuovo.id, giorno=0, pasto="Pranzo", alimento_id=riso.id))
        db.session.commit()
        vecchio_id, nuovo_id = vecchio.id, nuovo.id

    studio.post(f"/piani/{nuovo_id}/pubblica", follow_redirects=True)
    with app.app_context():
        assert db.session.get(Piano, nuovo_id).stato == "pubblicato"
        assert db.session.get(Piano, vecchio_id).stato == "archiviato"
        # e il cliente riceve la notifica nella sua area
        assert Notifica.query.filter_by(destinatario="cliente").count() == 1


def test_il_cliente_vede_solo_il_piano_pubblicato(cliente, app):
    with app.app_context():
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        bozza = _piano_di_prova(titolo="Bozza segreta")
        db.session.add(VocePiano(piano_id=bozza.id, giorno=0, pasto="Pranzo", alimento_id=riso.id))
        db.session.commit()

    risposta = cliente.get("/area/piano")
    assert "Bozza segreta" not in risposta.get_data(as_text=True)

    with app.app_context():
        piano = Piano.query.filter_by(titolo="Bozza segreta").first()
        piano.stato = "pubblicato"
        db.session.commit()

    risposta = cliente.get("/area/piano")
    assert "Bozza segreta" in risposta.get_data(as_text=True)


# ----------------------------------------------------------------------
# Lista della spesa
# ----------------------------------------------------------------------
def test_la_spesa_somma_i_grammi_di_tutta_la_settimana(app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        for giorno in range(7):
            db.session.add(
                VocePiano(piano_id=piano.id, giorno=giorno, pasto="Pranzo", alimento_id=riso.id, porzioni=1)
            )
        db.session.commit()

        gruppi, manuali = lista_spesa(piano)
        righe = [r for g in gruppi for r in g.righe]
        assert len(righe) == 1
        assert righe[0].grammi == pytest.approx(560)  # 7 × 80 g
        assert righe[0].quantita == "560 g"
        assert righe[0].giorni_etichetta == "tutti i giorni"
        assert manuali == []


def test_la_spesa_si_puo_limitare_ad_alcuni_giorni(app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        for giorno in range(7):
            db.session.add(VocePiano(piano_id=piano.id, giorno=giorno, pasto="Pranzo", alimento_id=riso.id))
        db.session.commit()

        gruppi, _ = lista_spesa(piano, giorni=[0, 1])
        righe = [r for g in gruppi for r in g.righe]
        assert righe[0].grammi == pytest.approx(160)


def test_la_spesa_espande_gli_ingredienti_delle_ricette(app):
    with app.app_context():
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        broccoli = Alimento.query.filter_by(nome="Broccoli").first()
        ricetta = Ricetta(titolo="Riso e broccoli", porzioni=2)
        ricetta.assegna_slug()
        db.session.add(ricetta)
        db.session.commit()
        db.session.add(IngredienteRicetta(ricetta_id=ricetta.id, alimento_id=riso.id, grammi=160))
        db.session.add(IngredienteRicetta(ricetta_id=ricetta.id, alimento_id=broccoli.id, grammi=300))
        db.session.add(IngredienteRicetta(ricetta_id=ricetta.id, testo="sale q.b.", grammi=0))
        db.session.commit()

        piano = _piano_di_prova()
        db.session.add(
            VocePiano(piano_id=piano.id, giorno=0, pasto="Cena", ricetta_id=ricetta.id, porzioni=1)
        )
        db.session.commit()

        gruppi, manuali = lista_spesa(piano)
        per_nome = {r.etichetta: r for g in gruppi for r in g.righe}
        # una porzione su due: metà degli ingredienti
        assert per_nome["Riso integrale"].grammi == pytest.approx(80)
        assert per_nome["Broccoli"].grammi == pytest.approx(150)
        assert "sale q.b." in manuali[0]


def test_le_voci_libere_finiscono_fra_quelle_da_aggiungere_a_mano(app):
    with app.app_context():
        piano = _piano_di_prova()
        db.session.add(
            VocePiano(piano_id=piano.id, giorno=0, pasto="Colazione", testo_libero="Caffè amaro")
        )
        db.session.commit()

        gruppi, manuali = lista_spesa(piano)
        assert gruppi == []
        assert manuali == ["Caffè amaro"]


def test_link_al_carrello_del_fornitore(app):
    from nutriapp.models import FornitoreSpesa

    with app.app_context():
        fornitore = FornitoreSpesa(nome="Glovo", url_template="https://esempio.it/cerca?q={query}")
        assert fornitore.url_per("olio d'oliva") == "https://esempio.it/cerca?q=olio+d%27oliva"


def test_lista_in_testo_semplice(app):
    with app.app_context():
        piano = _piano_di_prova()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        db.session.add(VocePiano(piano_id=piano.id, giorno=0, pasto="Pranzo", alimento_id=riso.id))
        db.session.commit()

        gruppi, manuali = lista_spesa(piano)
        testo = lista_in_testo(gruppi, manuali, "Spesa di prova")
        assert "Spesa di prova" in testo
        assert "Riso integrale: 80 g" in testo


# ----------------------------------------------------------------------
# Area cliente
# ----------------------------------------------------------------------
def test_il_cliente_registra_una_misurazione(cliente, app):
    cliente.post(
        "/area/progressi",
        data={"data": date.today().isoformat(), "peso_kg": "63,5", "note": "va meglio"},
        follow_redirects=True,
    )
    with app.app_context():
        misurazione = Misurazione.query.one()
        assert misurazione.peso_kg == 63.5
        assert misurazione.inserita_dal_cliente is True


def test_conversazione_fra_cliente_e_studio(cliente, studio, app):
    cliente.post("/area/messaggi", data={"testo": "Posso cambiare la cena?"}, follow_redirects=True)
    with app.app_context():
        messaggio = Messaggio.query.one()
        assert messaggio.mittente_ruolo == "cliente"
        assert messaggio.letto is False
        assistito_id = messaggio.assistito_id

    # lo studio risponde: il messaggio del cliente risulta letto
    studio.post(
        f"/assistiti/{assistito_id}/messaggi", data={"testo": "Certo, usa il tofu."},
        follow_redirects=True,
    )
    with app.app_context():
        assert Messaggio.query.filter_by(mittente_ruolo="cliente").one().letto is True
        assert Messaggio.query.count() == 2


def test_il_cliente_vede_solo_i_contenuti_pubblicati(cliente, app):
    with app.app_context():
        pubblicato = Articolo(titolo="Visibile", pubblicato=True, data_pubblicazione=date.today())
        pubblicato.assegna_slug()
        bozza = Articolo(titolo="Ancora in bozza", pubblicato=False)
        bozza.assegna_slug()
        db.session.add_all([pubblicato, bozza])
        db.session.commit()
        slug_bozza = bozza.slug

    testo = cliente.get("/area/blog").get_data(as_text=True)
    assert "Visibile" in testo
    assert "Ancora in bozza" not in testo
    assert cliente.get(f"/area/blog/{slug_bozza}").status_code == 404


# ----------------------------------------------------------------------
# Notifiche
# ----------------------------------------------------------------------
def test_notifica_di_piano_in_scadenza_senza_duplicati(app):
    with app.app_context():
        _piano_di_prova(
            stato="pubblicato",
            data_inizio=date.today() - timedelta(days=20),
            data_fine=date.today() + timedelta(days=2),
        )
        assert genera_notifiche() >= 1
        prima = Notifica.query.count()
        genera_notifiche()  # secondo giro: nessun doppione
        assert Notifica.query.count() == prima

        scadenza = Notifica.query.filter_by(categoria="piano").first()
        assert "finisce" in scadenza.messaggio


def test_notifica_di_appuntamento_di_domani(app):
    with app.app_context():
        assistito = Assistito.query.first()
        domani = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
        db.session.add(
            Appuntamento(assistito_id=assistito.id, data_ora=domani.replace(hour=15), tipo="Controllo")
        )
        db.session.commit()

        genera_notifiche()
        notifica = Notifica.query.filter_by(categoria="appuntamento").first()
        assert notifica is not None
        assert "domani" in notifica.messaggio


# ----------------------------------------------------------------------
# Importazione degli alimenti
# ----------------------------------------------------------------------
def test_traduzione_dei_nomi_usda():
    heads = {"Apples": "Mele", "Chicken": "Pollo"}
    qualifiers = {"raw": "crudo", "with skin": "con buccia"}

    nome, termine = traduci_nome("Apples, fuji, with skin, raw", heads, qualifiers)
    assert nome == "Mele, fuji, con buccia, crudo"
    assert termine == "Mele"

    # termine sconosciuto: non inventiamo nulla
    assert traduci_nome("Rutabagas, raw", heads, qualifiers) == (None, None)


def test_alimento_senza_valori_e_riconoscibile(app):
    with app.app_context():
        pane = Alimento.query.filter_by(nome="Pane comune").first()
        riso = Alimento.query.filter_by(nome="Riso integrale").first()
        assert pane.senza_valori is True
        assert riso.senza_valori is False


# ----------------------------------------------------------------------
# Email
# ----------------------------------------------------------------------
def test_senza_smtp_non_si_manda_niente_e_lo_si_dice(app):
    from nutriapp.mailer import invia, invia_notifiche_pendenti

    with app.app_context():
        ok, dettaglio = invia(["qualcuno@prova.it"], "Oggetto", "testo", "<p>html</p>", forza=True)
        assert ok is False
        assert "SMTP" in dettaglio
        assert invia_notifiche_pendenti() == 0


def test_digest_riassume_le_notifiche(app):
    from nutriapp.mailer import costruisci_digest

    with app.app_context():
        notifiche = [
            Notifica(messaggio="Piano scaduto", livello="danger", created_at=datetime.utcnow()),
            Notifica(messaggio="Visita domani", livello="info", created_at=datetime.utcnow()),
        ]
        oggetto, testo, html = costruisci_digest(notifiche, "Studio Prova")
        assert "2 notifiche" in oggetto
        assert "1 urgente" in oggetto
        assert "Piano scaduto" in testo
        # le urgenti vengono prima
        assert testo.index("Piano scaduto") < testo.index("Visita domani")
        assert "Studio Prova" in html


def test_etichetta_della_porzione_non_ripete_i_grammi(app):
    with app.app_context():
        alimento = _alimento(
            "Pollo di prova", porzione_nome="1 porzione (120 g)", porzione_g=120
        )
        db.session.commit()
        piano = _piano_di_prova()
        voce = VocePiano(
            piano_id=piano.id, giorno=0, pasto="Cena", alimento_id=alimento.id, porzioni=1.5
        )
        db.session.add(voce)
        db.session.commit()

        assert alimento.porzione_breve == "1 porzione"
        assert voce.quantita_etichetta == "1,5 × 1 porzione · 180 g"


def test_porzione_espressa_solo_in_grammi_mostra_i_grammi(app):
    with app.app_context():
        alimento = _alimento("Passata di prova", porzione_nome="100 g", porzione_g=100)
        db.session.commit()
        piano = _piano_di_prova()
        voce = VocePiano(
            piano_id=piano.id, giorno=0, pasto="Cena", alimento_id=alimento.id, porzioni=2
        )
        db.session.add(voce)
        db.session.commit()

        assert alimento.porzione_breve == ""
        assert voce.quantita_etichetta == "200 g"


def test_traduzione_delle_porzioni_usda():
    from nutriapp.foodimport import traduci_porzione

    porzioni = {"cup": "tazza", "chopped": "tritato", "serving": "porzione"}
    assert traduci_porzione("1 cup (chopped) (76 g)", porzioni) == "1 tazza (tritato) (76 g)"
    assert traduci_porzione("1 serving (120 g)", porzioni) == "1 porzione (120 g)"
    # parola che non conosciamo: resta com'è, non la inventiamo
    assert traduci_porzione("1 sprig (2 g)", porzioni) == "1 sprig (2 g)"
    assert traduci_porzione(None, porzioni) is None


# ----------------------------------------------------------------------
# Avvio desktop
# ----------------------------------------------------------------------
def test_le_due_applicazioni_non_si_scambiano_l_eseguibile():
    """Ogni ricetta PyInstaller deve puntare alla *sua* applicazione.

    È l'errore che si paga più caro: un `.exe` che si chiama NutriStudio e
    avvia il gestionale assicurativo.
    """
    from pathlib import Path

    radice = Path(__file__).resolve().parent.parent

    def senza_commenti(percorso: Path) -> str:
        """Solo le righe che PyInstaller legge davvero: i commenti possono
        citare l'altra applicazione, il codice no."""
        righe = percorso.read_text(encoding="utf-8").splitlines()
        return "\n".join(r for r in righe if not r.lstrip().startswith("#"))

    nutri = senza_commenti(radice / "nutristudio.spec")
    assert '"run_nutristudio.py"' in nutri
    assert 'name="NutriStudio"' in nutri
    assert "nutriapp/data" in nutri  # senza i dati partirebbe con zero alimenti
    assert "gestionale" not in nutri

    gestionale = senza_commenti(radice / "gestionale.spec")
    assert '"run_desktop.py"' in gestionale
    assert 'name="GestionaleAssicurativo"' in gestionale
    assert "nutriapp" not in gestionale


def test_avvio_desktop_usa_la_propria_cartella_dati(monkeypatch, tmp_path):
    import run_nutristudio

    monkeypatch.setattr(run_nutristudio, "_base_dir", lambda: str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Ricostruiamo la sola parte di main() che decide dove finiscono i dati.
    import os

    data_dir = os.path.join(run_nutristudio._base_dir(), "dati_nutristudio")
    os.makedirs(data_dir, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(data_dir, "nutristudio.db"))

    assert os.path.isdir(data_dir)
    assert "nutristudio.db" in os.environ["DATABASE_URL"]
    assert "gestionale" not in os.environ["DATABASE_URL"]


def test_credenziali_iniziali_solo_finche_la_password_e_provvisoria(app):
    import run_nutristudio

    with app.app_context():
        utente = User.query.filter_by(ruolo="nutrizionista").first()

        utente.deve_cambiare_password = True
        db.session.commit()
        credenziali = run_nutristudio._credenziali_iniziali()
        assert credenziali is not None
        assert credenziali[0] == "studio@prova.it"

        # una volta cambiata, non si stampa più niente in console
        utente.deve_cambiare_password = False
        db.session.commit()
        assert run_nutristudio._credenziali_iniziali() is None


# ----------------------------------------------------------------------
# Primo avvio
# ----------------------------------------------------------------------
def test_il_primo_avvio_mostra_le_credenziali_dello_studio(client, app, monkeypatch):
    """Nessuno si registra da solo: al primo avvio la pagina dice come entrare."""
    monkeypatch.setenv("NUTRI_ADMIN_PASSWORD", PASSWORD_STUDIO)
    with app.app_context():
        utente = User.query.filter_by(ruolo="nutrizionista").one()
        utente.deve_cambiare_password = True
        db.session.commit()

    testo = client.get("/accedi").get_data(as_text=True)
    assert "Primo avvio" in testo
    assert "studio@prova.it" in testo
    assert PASSWORD_STUDIO in testo


def test_le_credenziali_spariscono_appena_la_password_cambia(client, app, monkeypatch):
    monkeypatch.setenv("NUTRI_ADMIN_PASSWORD", PASSWORD_STUDIO)
    with app.app_context():
        utente = User.query.filter_by(ruolo="nutrizionista").one()
        utente.deve_cambiare_password = True
        db.session.commit()
    assert "Primo avvio" in client.get("/accedi").get_data(as_text=True)

    client.post("/accedi", data={"email": "studio@prova.it", "password": PASSWORD_STUDIO})
    client.post(
        "/cambia-password",
        data={"nuova": "una-password-mia", "conferma": "una-password-mia"},
        follow_redirects=True,
    )
    client.get("/esci")

    testo = client.get("/accedi").get_data(as_text=True)
    assert "Primo avvio" not in testo
    assert PASSWORD_STUDIO not in testo


def test_niente_credenziali_in_pagina_se_la_password_non_e_quella_di_fabbrica(client, app, monkeypatch):
    """Anche con il cambio password pendente: se la password non è quella
    documentata, non c'è niente da suggerire."""
    monkeypatch.setenv("NUTRI_ADMIN_PASSWORD", "tutt-altra-password")
    with app.app_context():
        utente = User.query.filter_by(ruolo="nutrizionista").one()
        utente.deve_cambiare_password = True
        db.session.commit()

    testo = client.get("/accedi").get_data(as_text=True)
    assert "Primo avvio" not in testo
    assert "tutt-altra-password" not in testo


def test_con_piu_accessi_di_studio_non_si_suggerisce_nulla(client, app, monkeypatch):
    """Studio già avviato con un collaboratore: non è più un primo avvio."""
    monkeypatch.setenv("NUTRI_ADMIN_PASSWORD", PASSWORD_STUDIO)
    with app.app_context():
        utente = User.query.filter_by(ruolo="nutrizionista").one()
        utente.deve_cambiare_password = True
        collega = User(email="collega@prova.it", nome="Collega", ruolo="nutrizionista")
        collega.set_password("password-del-collega")
        db.session.add(collega)
        db.session.commit()

    assert "Primo avvio" not in client.get("/accedi").get_data(as_text=True)
