"""Grafici disegnati come SVG in linea: nessuna libreria, niente rete.

Serve un solo tipo di grafico — l'andamento del peso — e serve che funzioni
anche offline e in stampa. Ottanta righe di geometria costano meno di una
dipendenza JavaScript.
"""
from __future__ import annotations


def serie_peso(misurazioni, larghezza: int = 640, altezza: int = 180, margine: int = 24) -> dict | None:
    """Coordinate pronte per l'SVG a partire dalle misurazioni (dalla più vecchia).

    Ritorna None se i punti non bastano a disegnare una linea.
    """
    punti_dati = [(m.data, m.peso_kg) for m in misurazioni if m.peso_kg]
    if len(punti_dati) < 2:
        return None

    pesi = [p for _, p in punti_dati]
    minimo, massimo = min(pesi), max(pesi)
    if massimo - minimo < 1:  # percorso piatto: apriamo la scala per non appiattire tutto
        centro = (massimo + minimo) / 2
        minimo, massimo = centro - 1, centro + 1

    larghezza_utile = larghezza - 2 * margine
    altezza_utile = altezza - 2 * margine
    passo = larghezza_utile / (len(punti_dati) - 1)

    punti = []
    for indice, (giorno, peso) in enumerate(punti_dati):
        x = margine + indice * passo
        y = margine + altezza_utile * (massimo - peso) / (massimo - minimo)
        punti.append({"x": round(x, 1), "y": round(y, 1), "data": giorno, "peso": peso})

    linea = " ".join(f"{p['x']},{p['y']}" for p in punti)
    area = (
        f"M {punti[0]['x']},{altezza - margine} "
        + " ".join(f"L {p['x']},{p['y']}" for p in punti)
        + f" L {punti[-1]['x']},{altezza - margine} Z"
    )

    return {
        "larghezza": larghezza,
        "altezza": altezza,
        "margine": margine,
        "punti": punti,
        "linea": linea,
        "area": area,
        "minimo": round(minimo, 1),
        "massimo": round(massimo, 1),
        "primo": punti_dati[0],
        "ultimo": punti_dati[-1],
        "variazione": round(punti_dati[-1][1] - punti_dati[0][1], 1),
    }
