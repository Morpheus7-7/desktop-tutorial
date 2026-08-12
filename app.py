"""Punto di ingresso: avvia il gestionale con `python app.py` (o `flask run`)."""
from gestionale import create_app
from gestionale.scheduler import start_scheduler

app = create_app()

if __name__ == "__main__":
    # Lo scheduler invia in automatico le notifiche via email in background.
    # Disattiviamo il reloader per non avviare due volte il thread.
    start_scheduler(app)
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
