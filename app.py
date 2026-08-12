"""Punto di ingresso: avvia il gestionale con `python app.py` (o `flask run`)."""
from gestionale import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
