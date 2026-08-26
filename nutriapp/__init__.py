"""NutriStudio — l'applicazione dello studio di nutrizione.

Nasce da un planner in Excel e ne conserva la sostanza (gli alimenti USDA, il
piano settimanale, l'analisi dei nutrienti, il foglio da consegnare) portandola
dove un foglio di calcolo non arriva: **due porte d'accesso**, una per la
nutrizionista e una per ogni cliente, con le notifiche via email, il ricettario,
il blog e la lista della spesa collegata ai carrelli online.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from flask import Flask, g

from .models import FORNITORI_DEFAULT, FornitoreSpesa, Settings, User, db

__version__ = "1.0.0"

# Ogni quanto ricontrollare scadenze e appuntamenti durante la navigazione.
_INTERVALLO_NOTIFICHE = timedelta(minutes=10)


def _prepara_dati_iniziali(app: Flask) -> None:
    """Primo avvio: impostazioni, fornitori di spesa, alimenti e utente studio."""
    from .foodimport import importa_alimenti, importa_dispensa_italiana

    Settings.get()

    if FornitoreSpesa.query.count() == 0:
        for nome, template, icona, colore, ordine in FORNITORI_DEFAULT:
            db.session.add(
                FornitoreSpesa(
                    nome=nome, url_template=template, icona=icona, colore=colore, ordine=ordine
                )
            )
        db.session.commit()

    inseriti = importa_alimenti() + importa_dispensa_italiana()
    if inseriti:
        app.logger.info("Database alimenti: importati %d alimenti.", inseriti)

    if User.query.filter_by(ruolo="nutrizionista").count() == 0:
        from .security import email_studio_iniziale, password_studio_iniziale

        email = email_studio_iniziale()
        password = password_studio_iniziale()
        utente = User(
            email=email,
            nome=os.environ.get("NUTRI_ADMIN_NOME", "Studio"),
            ruolo="nutrizionista",
            # Se la password è quella di default va cambiata al primo accesso.
            deve_cambiare_password="NUTRI_ADMIN_PASSWORD" not in os.environ,
        )
        utente.set_password(password)
        db.session.add(utente)
        db.session.commit()
        app.logger.warning(
            "Creato l'utente studio «%s». Password iniziale: «%s» — cambiala al primo accesso.",
            utente.email,
            password,
        )


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-cambiami-in-produzione"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + os.path.join(app.instance_path, "nutristudio.db"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        IMPORTA_ALIMENTI=True,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        if app.config.get("IMPORTA_ALIMENTI"):
            _prepara_dati_iniziali(app)
        else:  # nei test bastano impostazioni e utente studio
            Settings.get()

    from .routes import register_blueprints

    register_blueprints(app)
    _registra_filtri(app)
    _registra_contesto(app)

    return app


# ----------------------------------------------------------------------
# Filtri Jinja
# ----------------------------------------------------------------------
def _registra_filtri(app: Flask) -> None:
    @app.template_filter("data_it")
    def data_it(valore):
        if valore is None:
            return "—"
        return valore.strftime("%d/%m/%Y")

    @app.template_filter("data_breve")
    def data_breve(valore):
        if valore is None:
            return "—"
        mesi = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
        return f"{valore.day} {mesi[valore.month - 1]}"

    @app.template_filter("ora_it")
    def ora_it(valore):
        if valore is None:
            return "—"
        return valore.strftime("%d/%m/%Y %H:%M")

    @app.template_filter("numero")
    def numero(valore, decimali=1):
        """Numero all'italiana: virgola decimale, trattino se il dato manca."""
        if valore is None:
            return "—"
        testo = f"{valore:,.{decimali}f}"
        return testo.replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("quantita")
    def quantita(grammi):
        if grammi is None:
            return "—"
        if grammi >= 1000:
            return f"{grammi / 1000:.1f}".replace(".", ",") + " kg"
        return f"{grammi:.0f} g"

    from .charts import serie_peso

    app.jinja_env.globals["grafico_peso"] = serie_peso

    @app.template_filter("paragrafi")
    def paragrafi(testo):
        """Testo semplice → paragrafi HTML (l'autoescape resta attivo a monte)."""
        if not testo:
            return ""
        blocchi = [b.strip() for b in testo.replace("\r\n", "\n").split("\n\n") if b.strip()]
        return blocchi


# ----------------------------------------------------------------------
# Variabili globali dei template e controlli periodici
# ----------------------------------------------------------------------
def _registra_contesto(app: Flask) -> None:
    from .models import GIORNI, PASTI
    from .notifications import conta_non_lette, genera_notifiche
    from .security import utente_corrente

    @app.before_request
    def _aggiorna_notifiche():
        """Ricontrolla scadenze e appuntamenti, ma non a ogni singola pagina."""
        utente = utente_corrente()
        if utente is None or not utente.is_nutrizionista:
            return
        ultimo = app.config.get("_ULTIMO_CONTROLLO")
        adesso = datetime.utcnow()
        if ultimo and adesso - ultimo < _INTERVALLO_NOTIFICHE:
            return
        app.config["_ULTIMO_CONTROLLO"] = adesso
        try:
            genera_notifiche()
        except Exception:  # noqa: BLE001 — la navigazione non deve fermarsi per questo
            app.logger.exception("Impossibile aggiornare le notifiche.")

    @app.context_processor
    def _globali():
        utente = utente_corrente()
        dati = {
            "utente": utente,
            "oggi": date.today(),
            "GIORNI": GIORNI,
            "PASTI": PASTI,
            "versione": __version__,
            "impostazioni": Settings.get() if utente else None,
            "notifiche_non_lette": 0,
        }
        if utente and utente.is_nutrizionista:
            dati["notifiche_non_lette"] = conta_non_lette("nutrizionista")
        elif utente and utente.is_cliente and utente.assistito:
            dati["notifiche_non_lette"] = conta_non_lette("cliente", utente.assistito_id)
        return dati

    @app.teardown_appcontext
    def _pulisci(_exc):
        g.pop("utente", None)
