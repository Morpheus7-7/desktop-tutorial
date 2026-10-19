"""Avvio da sorgente per lo sviluppo: ``python app.py``.

Per l'uso quotidiano avvia il gestionale con ``python run_desktop.py`` (o con
l'eseguibile): usa il server waitress, apre il browser, conserva i dati nella
cartella dell'utente e avvia lo scheduler di email e backup.

Questo file usa invece il server di sviluppo di Flask, adatto solo alle prove
su questo computer: non usarlo in produzione né in rete. Il debugger
interattivo di Werkzeug si attiva solo se richiesto esplicitamente:

    FLASK_DEBUG=1 python app.py

Attenzione: con ``flask --app app run`` il modulo viene solo importato e lo
scheduler (invio automatico delle email e backup giornaliero) **non parte**.
I comandi di manutenzione funzionano normalmente, ad esempio
``flask --app app reimposta-password NOMEUTENTE``.
"""
import os

from gestionale import create_app
from gestionale.backup import normalizza_cartelle
from gestionale.scheduler import start_scheduler
from run_desktop import registra_tipi_mime

registra_tipi_mime()
app = create_app()
# UPLOAD_FOLDER/BACKUP_FOLDER relativi: risolti rispetto a instance/, come il database.
normalizza_cartelle(app)


def debug_attivo(env=None) -> bool:
    """Debugger di Werkzeug solo con FLASK_DEBUG=1 (mai per impostazione predefinita)."""
    env = os.environ if env is None else env
    return (env.get("FLASK_DEBUG") or "").strip() == "1"


def main() -> None:
    # Lo scheduler invia in automatico le notifiche via email in background.
    # Disattiviamo il reloader per non avviare due volte il thread.
    start_scheduler(app)
    app.run(debug=debug_attivo(), host="127.0.0.1", port=5000, use_reloader=False)


if __name__ == "__main__":
    main()
