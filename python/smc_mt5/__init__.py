"""SMC-MT5: cervello Python (analisi SMC/LDP/divergenze) + esecuzione MetaTrader 5.

Architettura:
    Python (questo pacchetto)  -> studia, elabora, decide
    TradingView (webhook)      -> conferme/trigger dagli alert Pine
    MetaTrader 5               -> esegue gli ordini
"""

__version__ = "1.0.0"
