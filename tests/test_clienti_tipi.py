"""Tipi di cliente: libero professionista (una persona) e studio professionale
(studio associato / STP) sono gestiti in modo distinto, con professione,
specializzazioni, attività svolte, albo, inquadramento e obblighi di legge."""
import csv
import io
import re
from datetime import date, timedelta

from sqlalchemy import text

from gestionale import _migra_settore_professionisti
from gestionale.models import Client, Policy, db
from gestionale.professioni import (
    PER_CHIAVE,
    PROFESSIONI,
    dividi_voci,
    separa_voci,
    trova_professione,
    unisci_voci,
)
from gestionale.risk_engine import analyze_client, analyze_risks
from gestionale.titoli import add_months

OGGI = date.today()


def _crea(app, **dati):
    with app.app_context():
        c = Client(**dati)
        db.session.add(c)
        db.session.commit()
        return c.id


def _polizza(app, client_id, ramo, **kw):
    with app.app_context():
        p = Policy(
            client_id=client_id, compagnia="Generali", numero_polizza=f"P-{ramo}-{client_id}", ramo=ramo,
            premio_annuo=1000.0, frazionamento="annuale", data_decorrenza=OGGI - timedelta(days=30),
            data_scadenza=add_months(OGGI - timedelta(days=30), 12), stato="attiva", **kw,
        )
        db.session.add(p)
        db.session.commit()
        return p.id


# ----------------------------------------------------------------------
# Catalogo delle professioni
# ----------------------------------------------------------------------
def test_riconosce_la_professione_scritta_a_mano():
    attese = {
        "Avvocato": "avvocato",
        "Avv. penalista": "avvocato",
        "Studio legale associato": "avvocato",
        "Medico pediatra": "pediatra",
        "Studio medico pediatrico": "pediatra",
        "Medico veterinario": "veterinario",
        "Medico di base": "medico_base",
        "Medico di medicina generale": "medico_base",
        "Medico legale": "medico",
        "Medico chirurgo": "medico",
        "Ingegnere informatico": "ingegnere",
        "Ing. civile": "ingegnere",
        "Infermiere pediatrico": "infermiere",
        "Consulente informatico": "consulente_informatico",
        "Dottore commercialista": "commercialista",
        "Dentista": "odontoiatra",
        "PEDIATRA": "pediatra",
    }
    for testo, chiave in attese.items():
        trovata = trova_professione(testo)
        assert trovata is not None and trovata.chiave == chiave, testo
    assert trova_professione("Marketing manager") is None
    assert trova_professione("") is None and trova_professione(None) is None


def test_catalogo_coerente():
    chiavi = [p.chiave for p in PROFESSIONI]
    assert len(chiavi) == len(set(chiavi))
    for p in PROFESSIONI:
        assert p.specializzazioni and p.attivita and p.nome_studio
        assert len({v.lower() for v in p.specializzazioni}) == len(p.specializzazioni), p.chiave
        # Ogni voce resta una voce sola anche se finisce nel campo «Altre» (niente separatori dentro).
        for voce in (*p.specializzazioni, *p.attivita):
            assert dividi_voci(voce) == [voce] and "," not in voce, voce
        assert trova_professione(p.nome) is p
    avvocato = PER_CHIAVE["avvocato"]
    assert {"Civilista", "Penalista"} <= set(avvocato.specializzazioni)
    assert {o.ramo for o in avvocato.obblighi} == {"rc_professionale", "infortuni"}


def test_voci_unite_senza_doppioni_e_separate_dal_catalogo():
    assert unisci_voci(["Civilista", "Penalista"], "civilista, Diritto agrario; ") == \
        "Civilista; Penalista; Diritto agrario"
    assert unisci_voci([], "") is None
    scelte, altre = separa_voci("Civilista; Diritto agrario", PER_CHIAVE["avvocato"].specializzazioni)
    assert scelte == {"civilista"} and altre == "Diritto agrario"


# ----------------------------------------------------------------------
# Modulo cliente
# ----------------------------------------------------------------------
def test_modulo_mostra_i_campi_giusti_per_tipo(client):
    pagina = client.get("/clienti/nuovo?tipo=professionista").get_data(as_text=True)
    # Il professionista non ha dipendenti, referente, forma giuridica né ATECO.
    assert re.search(r'data-tipi="azienda studio" hidden>\s*<label[^>]*for="clients-form-numero-dipendenti"', pagina)
    assert re.search(r'data-tipi="azienda studio" hidden>\s*<label[^>]*for="clients-form-referente"', pagina)
    # Ha professione, specializzazioni, albo, inquadramento e volume d'affari.
    assert 'id="cf-professione"' in pagina and 'name="inquadramento"' in pagina
    assert "Volume d&#39;affari annuo (€)" in pagina or "Volume d'affari annuo (€)" in pagina
    assert 'value="Civilista"' in pagina and 'value="Pediatria generale"' in pagina
    for tipo in ("azienda", "studio", "dipendente", "privato"):
        assert client.get(f"/clienti/nuovo?tipo={tipo}").status_code == 200
    studio = client.get("/clienti/nuovo?tipo=studio").get_data(as_text=True)
    assert "Denominazione dello studio *" in studio and "STP S.r.l." in studio


def test_professionista_non_salva_i_dati_da_azienda(client, app):
    resp = client.post("/clienti/nuovo", data={
        "tipo": "professionista", "ragione_sociale": "Giulia Ferri", "professione": "Avvocato",
        "specializzazioni": ["Civilista", "Penalista"], "specializzazioni_altre": "Diritto agrario, civilista",
        "attivita_svolte": ["Mediatore civile"], "attivita_altre": "Docenza",
        "inquadramento": "libero_professionista", "albo_ordine": "Ordine degli Avvocati di Milano",
        "albo_numero": "m123", "albo_data_iscrizione": "2010-05-01", "fatturato_annuo": "85.000",
        # Campi da azienda inviati per errore (es. senza JavaScript): vanno ignorati.
        "numero_dipendenti": "7", "referente": "Segreteria", "forma_giuridica": "S.r.l.",
        "codice_ateco": "69.10", "settore": "Legale", "numero_professionisti": "3",
        "codice_fiscale": "RSSMRA80A01H501U",
    })
    assert resp.status_code == 302
    with app.app_context():
        c = Client.query.one()
        assert c.specializzazioni == "Civilista; Penalista; Diritto agrario"
        assert c.attivita_svolte == "Mediatore civile; Docenza"
        assert (c.albo_numero, c.albo_data_iscrizione, c.fatturato_annuo) == ("M123", date(2010, 5, 1), 85000.0)
        assert c.numero_dipendenti is None and c.referente is None and c.forma_giuridica is None
        assert c.codice_ateco is None and c.settore is None and c.numero_professionisti is None
        assert c.data_nascita == date(1980, 1, 1)
        assert c.attivita_sintesi == "Avvocato · Civilista, Penalista…"


def test_studio_professionale_e_una_societa(client, app):
    resp = client.post("/clienti/nuovo", data={
        "tipo": "studio", "ragione_sociale": "Studio Pediatrico Bimbi Sani", "forma_giuridica": "STP S.r.l.",
        "professione": "Pediatra", "specializzazioni": ["Neonatologia"], "numero_professionisti": "4",
        "numero_dipendenti": "3", "fatturato_annuo": "600000", "referente": "Dott.ssa Bianchi",
        "inquadramento": "convenzionato", "data_nascita": "1980-01-01",
    })
    assert resp.status_code == 302
    with app.app_context():
        s = Client.query.one()
        assert (s.forma_giuridica, s.numero_professionisti, s.numero_dipendenti) == ("STP S.r.l.", 4, 3)
        assert s.referente == "Dott.ssa Bianchi" and s.specializzazioni == "Neonatologia"
        # Una società non ha inquadramento né data di nascita.
        assert s.inquadramento is None and s.data_nascita is None and not s.persona_fisica
        sid = s.id
    # Forma giuridica di un altro tipo: scartata.
    client.post(f"/clienti/{sid}/modifica", data={
        "tipo": "studio", "ragione_sociale": "Studio Pediatrico Bimbi Sani", "professione": "Pediatra",
        "forma_giuridica": "S.p.A.",
    })
    with app.app_context():
        assert db.session.get(Client, sid).forma_giuridica is None


def test_professione_obbligatoria_per_professionista_e_studio(client, app):
    for tipo, messaggio in (("professionista", "Indica la professione del libero professionista"),
                            ("studio", "Indica la professione esercitata dallo studio")):
        resp = client.post("/clienti/nuovo", data={"tipo": tipo, "ragione_sociale": "Senza professione"})
        assert resp.status_code == 400 and messaggio in resp.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0


def test_privato_senza_partita_iva(client, app):
    client.post("/clienti/nuovo", data={
        "tipo": "privato", "ragione_sociale": "Anna Russo", "professione": "Pensionato",
        "partita_iva": "00743110157", "codice_fiscale": "RSSMRA80A01H501U", "numero_dipendenti": "2",
    })
    with app.app_context():
        c = Client.query.one()
        assert c.partita_iva is None and c.numero_dipendenti is None
        assert c.professione == "Pensionato" and c.data_nascita == date(1980, 1, 1) and c.persona_fisica


def test_modifica_ripresenta_specializzazioni_selezionate_e_altre(client, app):
    cid = _crea(app, tipo="professionista", ragione_sociale="Paolo Neri", professione="Medico pediatra",
                specializzazioni="Neonatologia; Pediatria dello sport", attivita_svolte="Vaccinazioni")
    pagina = client.get(f"/clienti/{cid}/modifica").get_data(as_text=True)
    gruppo = re.search(r'data-professione="pediatra"\s*>(.*?)</div>\s*</fieldset>', pagina, re.S)
    assert gruppo, "il gruppo del pediatra deve essere visibile"
    assert re.search(r'value="Neonatologia"[^>]*checked', pagina)
    assert re.search(r'name="specializzazioni_altre"[^>]*value="Pediatria dello sport"', pagina)
    assert re.search(r'value="Vaccinazioni"[^>]*checked', pagina)
    # Gli altri gruppi restano nascosti.
    assert re.search(r'data-professione="avvocato" hidden', pagina)


def test_data_iscrizione_albo_coerente(client, app):
    resp = client.post("/clienti/nuovo", data={
        "tipo": "professionista", "ragione_sociale": "Mario Rossi", "professione": "Ingegnere",
        "data_nascita": "1980-01-01", "albo_data_iscrizione": "1979-06-01",
    })
    assert resp.status_code == 400 and "iscrizione all&#39;albo è precedente" in resp.get_data(as_text=True)
    resp = client.post("/clienti/nuovo", data={
        "tipo": "professionista", "ragione_sociale": "Mario Rossi", "professione": "Ingegnere",
        "albo_data_iscrizione": (OGGI + timedelta(days=3)).isoformat(),
    })
    assert resp.status_code == 400


# ----------------------------------------------------------------------
# Professionista collegato allo studio
# ----------------------------------------------------------------------
def test_professionista_collegato_allo_studio(client, app):
    sid = _crea(app, tipo="studio", ragione_sociale="Studio Legale Ferri", professione="Avvocato")
    aid = _crea(app, tipo="azienda", ragione_sociale="ACME S.r.l.")
    pagina = client.get(f"/clienti/nuovo?tipo=professionista&studio={sid}").get_data(as_text=True)
    assert re.search(rf'<option value="{sid}" selected>Studio Legale Ferri', pagina)
    assert 'value="Avvocato"' in pagina
    # Un'azienda non può essere lo studio di appartenenza.
    resp = client.post("/clienti/nuovo", data={"tipo": "professionista", "ragione_sociale": "X",
                                               "professione": "Avvocato", "studio_id": str(aid)})
    assert resp.status_code == 400
    client.post("/clienti/nuovo", data={"tipo": "professionista", "ragione_sociale": "Giulia Ferri",
                                        "professione": "Avvocato", "studio_id": str(sid)})
    with app.app_context():
        studio = db.session.get(Client, sid)
        assert [p.ragione_sociale for p in studio.professionisti] == ["Giulia Ferri"]
    scheda = client.get(f"/clienti/{sid}").get_data(as_text=True)
    assert "Giulia Ferri" in scheda and "Aggiungi professionista" in scheda


def test_studio_che_cambia_tipo_o_viene_eliminato_scollega_i_professionisti(client, app):
    sid = _crea(app, tipo="studio", ragione_sociale="Studio Uno", professione="Avvocato")
    pid = _crea(app, tipo="professionista", ragione_sociale="Avv. Uno", professione="Avvocato", studio_id=sid)
    resp = client.post(f"/clienti/{sid}/modifica", data={"tipo": "azienda", "ragione_sociale": "Studio Uno"},
                       follow_redirects=True)
    assert "1 professionista scollegato" in resp.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Client, pid).studio_id is None
    sid2 = _crea(app, tipo="studio", ragione_sociale="Studio Due", professione="Avvocato")
    with app.app_context():
        db.session.get(Client, pid).studio_id = sid2
        db.session.commit()
    client.post(f"/clienti/{sid2}/elimina")
    with app.app_context():
        assert db.session.get(Client, sid2) is None
        assert db.session.get(Client, pid).studio_id is None


# ----------------------------------------------------------------------
# Obblighi assicurativi di legge
# ----------------------------------------------------------------------
def test_obblighi_avvocato_e_copertura_dello_studio(app):
    sid = _crea(app, tipo="studio", ragione_sociale="Studio Legale", professione="Avvocato")
    pid = _crea(app, tipo="professionista", ragione_sociale="Avv. Rossi", professione="Avvocato", studio_id=sid)
    _polizza(app, sid, "rc_professionale")
    _polizza(app, pid, "infortuni")
    with app.app_context():
        obblighi = {o["ramo"]: o for o in db.session.get(Client, pid).obblighi_assicurativi}
        assert obblighi["rc_professionale"]["in_portafoglio"] == "studio"
        assert obblighi["infortuni"]["in_portafoglio"] == "proprio"
        assert "247/2012" in obblighi["infortuni"]["norma"]


def test_sanitario_dipendente_deve_avere_la_colpa_grave(app):
    pid = _crea(app, tipo="professionista", ragione_sociale="Dott. Bianchi", professione="Cardiologo",
                inquadramento="dipendente_pubblico")
    lid = _crea(app, tipo="professionista", ragione_sociale="Dott. Verdi", professione="Pediatra",
                inquadramento="libero_professionista")
    with app.app_context():
        dip = db.session.get(Client, pid)
        assert dip.professione_catalogo.chiave == "medico"
        assert dip.obblighi_assicurativi[0]["copertura"] == "RC per colpa grave"
        assert db.session.get(Client, lid).obblighi_assicurativi[0]["copertura"] == "RC professionale"
        assert db.session.get(Client, lid).obblighi_assicurativi[0]["in_portafoglio"] is None


def test_scheda_mostra_gli_obblighi(client, app):
    cid = _crea(app, tipo="professionista", ragione_sociale="Avv. Rossi", professione="Avvocato",
                specializzazioni="Civilista; Penalista")
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Assicurazioni obbligatorie per legge" in pagina and "non in portafoglio" in pagina
    assert "Civilista" in pagina and "Penalista" in pagina


def test_convenzionato_ssn_colpa_grave_e_rc_per_attivita_privata(app):
    cid = _crea(app, tipo="professionista", ragione_sociale="Dott. Neri", professione="Pediatra",
                inquadramento="convenzionato", attivita_svolte="Visite ambulatoriali private")
    with app.app_context():
        obblighi = db.session.get(Client, cid).obblighi_assicurativi
        assert [o["copertura"] for o in obblighi] == ["RC per colpa grave", "RC professionale per l'attività privata"]
        assert obblighi[1]["massimale_minimo"] == 1_000_000 and "3.000.000 €" in obblighi[1]["nota_massimale"]


def test_massimali_minimi_di_legge(app):
    from gestionale.professioni import obblighi_di_legge

    avvocato = PER_CHIAVE["avvocato"]
    for fatturato, minimo in ((25_000, 350_000), (50_000, 500_000), (120_000, 1_000_000)):
        rc = obblighi_di_legge("professionista", avvocato, fatturato=fatturato)[0][0]
        assert rc["massimale_minimo"] == minimo
    assert obblighi_di_legge("professionista", avvocato)[0][0]["massimale_minimo"] is None
    studio = obblighi_di_legge("studio", avvocato, fatturato=600_000, numero_professionisti=4)[0][0]
    assert studio["massimale_minimo"] == 2_000_000
    assert obblighi_di_legge("studio", avvocato, numero_professionisti=12)[0][0]["massimale_minimo"] == 5_000_000
    # Sanitari: 2 milioni per chirurgia, ortopedia, anestesia e parto (DM 232/2023, art. 4).
    chirurgo = obblighi_di_legge("professionista", PER_CHIAVE["medico"], inquadramento="libero_professionista",
                                 voci=["Interventi chirurgici"])[0][0]
    assert chirurgo["massimale_minimo"] == 2_000_000
    assert obblighi_di_legge("professionista", PER_CHIAVE["psicologo"])[0][0]["massimale_minimo"] == 1_000_000


def test_massimale_in_polizza_sotto_il_minimo(client, app):
    cid = _crea(app, tipo="professionista", ragione_sociale="Avv. Bassi", professione="Avvocato",
                fatturato_annuo=90_000)
    _polizza(app, cid, "rc_professionale", massimale=500_000)
    with app.app_context():
        rc = db.session.get(Client, cid).obblighi_assicurativi[0]
        assert rc["in_portafoglio"] == "proprio" and rc["massimale_insufficiente"]
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "inferiore al minimo di legge" in pagina


def test_obblighi_di_notai_stp_studi_associati_e_veterinari(app):
    from gestionale.professioni import obblighi_di_legge

    notaio, _ = obblighi_di_legge("professionista", PER_CHIAVE["notaio"])
    assert "secondo rischio" in notaio[0]["copertura"] and "3.000.000" in notaio[0]["nota_massimale"]
    stp, _ = obblighi_di_legge("studio", PER_CHIAVE["ingegnere"], forma_giuridica="STP S.r.l.")
    assert "L. 183/2011" in stp[0]["norma"]
    associato, avvertenze = obblighi_di_legge("studio", PER_CHIAVE["pediatra"], forma_giuridica="Studio associato")
    assert associato == [] and "singoli professionisti" in avvertenze[0]
    struttura, _ = obblighi_di_legge("studio", PER_CHIAVE["pediatra"],
                                     forma_giuridica="Struttura sanitaria privata autorizzata")
    assert "art. 10 c. 1" in struttura[0]["norma"]
    # Il veterinario non è soggetto alla Gelli-Bianco: niente colpa grave anche da dipendente.
    veterinario, _ = obblighi_di_legge("professionista", PER_CHIAVE["veterinario"], inquadramento="dipendente_pubblico")
    assert [o["copertura"] for o in veterinario] == ["RC professionale"] and "DPR 137/2012" in veterinario[0]["norma"]
    # Professioni senza obbligo: solo l'avvertenza.
    revisore, avvisi = obblighi_di_legge("professionista", PER_CHIAVE["revisore_legale"])
    assert revisore == [] and "D.Lgs. 39/2010" in avvisi[0]


# ----------------------------------------------------------------------
# Analisi dei rischi
# ----------------------------------------------------------------------
def test_analisi_avvocato_con_obblighi_e_incarichi():
    res = analyze_risks(
        "Avvocato civilista, consulenza e contenzioso", client_type="professionista",
        professione=PER_CHIAVE["avvocato"], inquadramento="libero_professionista",
        attivita=["Curatore o commissario giudiziale", "Contenzioso giudiziale"], revenue=50_000,
    )
    ids = [r["id"] for r in res["rischi"]]
    assert ids[:2] == ["obbligo_rc_professionale", "obbligo_infortuni"]
    # Il pericolo generico sullo stesso ramo è assorbito dall'obbligo (con le parole chiave).
    assert "rc_professionale" not in ids and "rc_professionale_base" not in ids
    assert res["rischi"][0]["parole_chiave"] and res["rischi"][0]["obbligatoria"]
    assert "attivita_incarichi_giudiziari" in ids
    assert res["sintesi"]["obblighi_di_legge"] == 2
    assert any("500.000 €" in c for c in res["rischi"][0]["coperture_consigliate"])


def test_analisi_convenzionato_e_professione_senza_obbligo():
    res = analyze_risks("Pediatra di libera scelta", client_type="professionista",
                        professione=PER_CHIAVE["pediatra"], inquadramento="convenzionato")
    assert [r["id"] for r in res["rischi"][:2]] == ["obbligo_rc_professionale", "obbligo_rc_professionale_bis"]
    revisore = analyze_risks("Revisore", client_type="professionista", professione=PER_CHIAVE["revisore_legale"])
    assert revisore["avvertenze"] and revisore["sintesi"]["obblighi_di_legge"] == 0


def test_analisi_sanitario_dipendente_e_privato_e_studio():
    res = analyze_risks("Cardiologo ospedaliero", client_type="professionista",
                        professione=PER_CHIAVE["medico"], inquadramento="dipendente_pubblico")
    assert res["rischi"][0]["nome"].startswith("RC per colpa grave")
    assert "tutela_legale_sanitaria" in [r["id"] for r in res["rischi"]]
    privato = analyze_risks("Pensionata con casa di proprietà", client_type="privato")
    assert {"rc_capofamiglia_base", "casa_base"} <= {r["id"] for r in privato["rischi"]}
    studio = analyze_risks("Studio legale", client_type="studio", professione=PER_CHIAVE["avvocato"])
    ids = {r["id"] for r in studio["rischi"]}
    assert {"obbligo_rc_professionale", "multirischi_studio_base"} <= ids


def test_analyze_client_usa_professione_e_polizza_dello_studio(app):
    sid = _crea(app, tipo="studio", ragione_sociale="Studio", professione="Avvocato")
    pid = _crea(app, tipo="professionista", ragione_sociale="Avv. Rossi", professione="Avvocato",
                studio_id=sid, attivita_svolte="Amministratore di condominio")
    _polizza(app, sid, "rc_professionale")
    with app.app_context():
        res = analyze_client(db.session.get(Client, pid), description="Avvocato")
        assert "rc_professionale" in {c["ramo"] for c in res["coperture_presenti"]}
        assert "attivita_amministratore_condominio" in {r["id"] for r in res["rischi"]}


# ----------------------------------------------------------------------
# Migrazione, elenchi, esportazione e cruscotto
# ----------------------------------------------------------------------
def test_migrazione_settore_dei_professionisti(app):
    with app.app_context():
        db.session.execute(text(
            "INSERT INTO clients (tipo, ragione_sociale, settore, consenso_marketing) "
            "VALUES ('professionista', 'Ing. Vecchio', 'Progettazione strutturale', 0), "
            "('azienda', 'Vecchia S.r.l.', 'Edilizia', 0)"
        ))
        db.session.commit()
        _migra_settore_professionisti()
        prof = Client.query.filter_by(ragione_sociale="Ing. Vecchio").one()
        assert (prof.settore, prof.specializzazioni) == (None, "Progettazione strutturale")
        assert Client.query.filter_by(ragione_sociale="Vecchia S.r.l.").one().settore == "Edilizia"


def test_elenco_ricerca_esportazione_e_cruscotto(client, app):
    sid = _crea(app, tipo="studio", ragione_sociale="Studio Legale Ferri", professione="Avvocato",
                forma_giuridica="Studio associato", numero_professionisti=3)
    _crea(app, tipo="professionista", ragione_sociale="Giulia Ferri", professione="Avvocato",
          specializzazioni="Civilista; Famiglia e minori", studio_id=sid, albo_numero="M1")
    _crea(app, tipo="privato", ragione_sociale="Anna Russo", professione="Pensionato")
    elenco = client.get("/clienti/?q=civilista").get_data(as_text=True)
    assert "Giulia Ferri" in elenco and "Avvocato · Civilista, Famiglia e minori" in elenco
    assert "Giulia Ferri" in client.get("/cerca?q=famiglia").get_data(as_text=True)
    righe = list(csv.reader(io.StringIO(client.get("/clienti/esporta.csv").get_data(as_text=True).lstrip("﻿")),
                            delimiter=";"))
    intestazione = righe[0]
    for colonna in ("Specializzazioni", "Studio di appartenenza", "N. iscrizione albo", "Forma giuridica"):
        assert colonna in intestazione
    ferri = next(r for r in righe if r[0] == "Giulia Ferri")
    assert ferri[intestazione.index("Studio di appartenenza")] == "Studio Legale Ferri"
    cruscotto = client.get("/").get_data(as_text=True)
    assert "1 studio · 1 prof. · 1 privato" in cruscotto
    assert client.get("/clienti/?tipo=studio").get_data(as_text=True).count("Studio Legale Ferri") >= 1
