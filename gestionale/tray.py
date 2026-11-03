"""Icona di Deal Combined vicino all'orologio di Windows (pystray).

Si importa solo nel programma installato su Windows: pystray e Pillow non
servono altrove e su Linux senza schermo l'import fallirebbe.
"""
from __future__ import annotations

from typing import Callable


def immagine_icona(lato: int = 64):
    """Il marchio disegnato: copertina verde dell'agenda con il nastro."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, lato - 3, lato - 3), radius=lato // 6, fill=(29, 59, 48, 255))
    nastro = lato * 0.62
    d.polygon([(nastro, 0), (nastro + lato * 0.16, 0), (nastro + lato * 0.16, lato * 0.72),
               (nastro + lato * 0.08, lato * 0.62), (nastro, lato * 0.72)], fill=(190, 18, 60, 255))
    d.rectangle((lato * 0.2, lato * 0.3, lato * 0.5, lato * 0.36), fill=(255, 255, 255, 230))
    d.rectangle((lato * 0.2, lato * 0.46, lato * 0.5, lato * 0.52), fill=(255, 255, 255, 170))
    d.rectangle((lato * 0.2, lato * 0.62, lato * 0.42, lato * 0.68), fill=(255, 255, 255, 120))
    return img


def crea(apri: Callable[[], None], esci: Callable[[], None]):
    """Crea e avvia l'icona; restituisce l'oggetto pystray.Icon (con notify)."""
    import pystray

    menu = pystray.Menu(
        pystray.MenuItem("Apri Deal Combined", lambda icon, item: apri(), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Esci", lambda icon, item: esci()),
    )
    icona = pystray.Icon("Deal Combined", immagine_icona(), "Deal Combined", menu)
    icona.run_detached()
    return icona
