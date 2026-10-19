"""Aspetto personale: tema di colore e modalità chiara/scura."""
from gestionale.models import User

from conftest import add_user, login


def test_scelta_tema_e_modalita(client, app):
    pagina = client.get("/profilo/aspetto").get_data(as_text=True)
    assert "Verde smeraldo" in pagina and 'data-tema="blu"' in pagina and 'data-aspetto="auto"' in pagina
    assert client.post("/profilo/aspetto", data={"tema": "smeraldo", "aspetto": "scuro"}).status_code == 302
    pagina = client.get("/").get_data(as_text=True)
    assert 'data-tema="smeraldo"' in pagina and 'data-aspetto="scuro"' in pagina and "aspetto.js" in pagina
    # Valori non previsti: si torna ai predefiniti.
    client.post("/profilo/aspetto", data={"tema": "<script>", "aspetto": "neon"})
    with app.app_context():
        u = User.query.filter_by(username="admin").one()
        assert (u.tema, u.aspetto) == ("blu", "auto")


def test_anche_la_sola_consultazione_sceglie_il_proprio_aspetto(app):
    add_user(app, "lettore", "password-lett-1", ruolo="consultazione")
    c = app.test_client()
    login(c, "lettore", "password-lett-1")
    assert c.post("/profilo/aspetto", data={"tema": "viola", "aspetto": "chiaro"}).status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="lettore").one().tema == "viola"


def test_icona_del_programma(client):
    assert client.get("/static/icona.png").mimetype == "image/png"
    assert client.get("/static/aspetto.js").status_code == 200
