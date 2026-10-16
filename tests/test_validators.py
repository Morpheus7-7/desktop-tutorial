"""Test di validazione anagrafica (CF, P.IVA…) e del form cliente."""
from datetime import date

from gestionale.export import csv_text
from gestionale.models import Client
from gestionale.validators import (
    data_nascita_da_cf,
    valida_cap,
    valida_codice_fiscale,
    valida_email,
    valida_partita_iva,
    valida_provincia,
)


def test_partita_iva():
    assert valida_partita_iva("00743110157") is None
    assert valida_partita_iva("12345678903") is None
    assert "cifra di controllo" in valida_partita_iva("12345678901")
    assert "11 cifre" in valida_partita_iva("1234")
    assert valida_partita_iva(None) is None


def test_codice_fiscale_persona_fisica_e_societa():
    assert valida_codice_fiscale("RSSMRA80A01H501U") is None
    assert "controllo" in valida_codice_fiscale("RSSMRA80A01H501X")
    assert "formato" in valida_codice_fiscale("RSSMRA80Z01H501U").lower()
    assert valida_codice_fiscale("00743110157") is None  # CF numerico di società
    assert "Codice fiscale numerico" in valida_codice_fiscale("00743110158")
    assert "16 caratteri" in valida_codice_fiscale("ABC")


def test_codice_fiscale_omocodico():
    # «RSSMRA80A01H501U» con l'ultima cifra del comune sostituita (1 → M): nuovo controllo.
    from gestionale.validators import carattere_controllo_cf

    base = "RSSMRA80A01H50M"
    cf = base + carattere_controllo_cf(base)
    assert valida_codice_fiscale(cf) is None


def test_data_nascita_da_cf():
    assert data_nascita_da_cf("RSSMRA80A01H501U") == date(1980, 1, 1)
    from gestionale.validators import carattere_controllo_cf

    donna = "BNCLRA80A41F205"
    cf = donna + carattere_controllo_cf(donna)
    assert data_nascita_da_cf(cf) == date(1980, 1, 1)
    assert data_nascita_da_cf("00743110157") is None


def test_altri_campi():
    assert valida_cap("20100") is None and valida_cap("2010") is not None
    assert valida_provincia("MI") is None and valida_provincia("Milano") is not None
    assert valida_email("a@b.it") is None and valida_email("non-una-email") is not None


def test_form_cliente_rifiuta_dati_non_validi_e_conserva_input(client, app):
    resp = client.post("/clienti/nuovo", data={
        "tipo": "azienda", "ragione_sociale": "Errata S.r.l.", "partita_iva": "12345678901",
        "citta": "Torino",
    })
    assert resp.status_code == 400
    pagina = resp.get_data(as_text=True)
    assert "cifra di controllo" in pagina
    assert 'value="Errata S.r.l."' in pagina and 'value="Torino"' in pagina
    with app.app_context():
        assert Client.query.count() == 0


def test_form_cliente_normalizza_e_deriva_data_nascita(client, app):
    resp = client.post("/clienti/nuovo", data={
        "tipo": "professionista", "ragione_sociale": "Mario Rossi",
        "codice_fiscale": "rssmra80a01h501u", "partita_iva": "IT 00743110157", "provincia": "mi",
        "data_consenso_privacy": date.today().isoformat(),
    })
    assert resp.status_code == 302
    with app.app_context():
        c = Client.query.one()
        assert c.codice_fiscale == "RSSMRA80A01H501U"
        assert c.partita_iva == "00743110157"
        assert c.provincia == "MI"
        assert c.data_nascita == date(1980, 1, 1)
        assert "Consenso privacy (GDPR) non registrato" not in c.compliance_problemi
        assert "Questionario di adeguatezza mancante" in c.compliance_problemi


def test_form_cliente_avvisa_duplicati(client):
    dati = {"tipo": "azienda", "ragione_sociale": "Primo", "partita_iva": "00743110157"}
    client.post("/clienti/nuovo", data=dati)
    resp = client.post("/clienti/nuovo", data={**dati, "ragione_sociale": "Secondo"}, follow_redirects=True)
    assert "esiste già un cliente" in resp.get_data(as_text=True)


def test_modifica_cliente_non_valida_non_salva(client, app):
    client.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Gamma"})
    with app.app_context():
        cid = Client.query.one().id
    resp = client.post(f"/clienti/{cid}/modifica", data={
        "tipo": "azienda", "ragione_sociale": "Gamma Cambiata", "cap": "abc",
    })
    assert resp.status_code == 400
    with app.app_context():
        assert Client.query.one().ragione_sociale == "Gamma"


def test_csv_formattazione_e_protezione_formule():
    testo = csv_text(["A", "B", "C", "D"], [[1234.5, date(2026, 3, 1), "=SOMMA(A1)", True]])
    assert testo.startswith("﻿")
    riga = testo.splitlines()[1]
    assert riga == "\"1234,50\";01/03/2026;'=SOMMA(A1);Sì" or riga == "1234,50;01/03/2026;'=SOMMA(A1);Sì"
