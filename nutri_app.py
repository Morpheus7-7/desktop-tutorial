"""Avvio di NutriStudio: `python nutri_app.py`, poi http://127.0.0.1:5001."""
from nutriapp import create_app
from nutriapp.scheduler import start_scheduler

app = create_app()

if __name__ == "__main__":
    # Lo scheduler manda in automatico il riepilogo via email: niente reloader,
    # altrimenti il thread partirebbe due volte.
    start_scheduler(app)
    app.run(debug=True, host="127.0.0.1", port=5001, use_reloader=False)
