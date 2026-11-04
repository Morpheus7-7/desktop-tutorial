"""«Come impostare la trattativa»: guida per il cliente reale, collegata all'Accademia."""
from gestionale import trattativa
from gestionale.models import Client, FollowUp, db


def _cliente(app, **kw):
    with app.app_context():
        c = Client(**kw)
        db.session.add(c)
        db.session.commit()
        return c.id


def test_avvocato_domande_legali_obblighi_e_obiezioni(client, app):
    cid = _cliente(app, tipo="professionista", ragione_sociale="Giulia Ferri", nome="Giulia", cognome="Ferri",
                   professione="Avvocato")
    pagina = client.get(f"/clienti/{cid}/trattativa").get_data(as_text=True)
    assert "Come impostare la trattativa" in pagina
    assert "termine processuale" in pagina  # domande per l'area legale
    assert "L. 247/2012" in pagina  # obbligo di legge della professione
    assert "convenzionata con il mio ordine" in pagina  # obiezione tipica
    assert "/accademia/allenamento?id=convenzione-ordine" in pagina
    assert "Come impostare la trattativa" in client.get(f"/clienti/{cid}").get_data(as_text=True)


def test_medico_ospedaliero_e_role_play(app):
    cid = _cliente(app, tipo="professionista", ragione_sociale="Sara Neri", professione="Medico anestesista")
    with app.app_context():
        gd = trattativa.guida(db.session.get(Client, cid))
        assert gd["profilo"] == "sanitaria"
        assert [s["id"] for s in gd["scenari"]] == ["medico-ospedaliero"]


def test_famiglia_dipendente_e_prossimo_passo(client, app):
    cid = _cliente(app, tipo="dipendente", ragione_sociale="Luca Verdi", nome="Luca", cognome="Verdi")
    with app.app_context():
        from datetime import date, timedelta
        db.session.add(FollowUp(client_id=cid, titolo="Incontro con la moglie", data_scadenza=date.today() + timedelta(days=3)))
        db.session.commit()
    pagina = client.get(f"/clienti/{cid}/trattativa").get_data(as_text=True)
    assert "Mi copre già l&#39;INAIL" in pagina or "Mi copre già l'INAIL" in pagina
    assert "Incontro con la moglie" in pagina and "Prossimo passo" in pagina
    assert "raccolta-privato" in pagina


def test_tutti_i_profili_hanno_contenuti_validi():
    from gestionale import academy as ac
    for chiave in trattativa.DOMANDE:
        assert set(trattativa.DOMANDE[chiave]) == {"situazione", "problema", "implicazione", "bisogno"}
        assert all(ac.get_obiezione(i) for i in trattativa.OBIEZIONI_PROFILO[chiave])
        assert all(ac.get_scenario(i) for i in trattativa.SCENARI_PROFILO[chiave])
    assert len(trattativa._lezioni(trattativa.LEZIONI_BASE)) == len(trattativa.LEZIONI_BASE)
