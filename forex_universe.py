#!/usr/bin/env python3
"""
Universo de pares de moedas (Forex) para o painel Forex.
20 pares: 7 majores (contra USD) + 13 minores (cruzamentos sem USD).
Formato yfinance para Forex: sufixo =X (ex.: EURUSD=X).
"""

FOREX_PARES = {
    "EURUSD=X": "EUR/USD — Euro / Dólar",
    "GBPUSD=X": "GBP/USD — Libra / Dólar",
    "USDJPY=X": "USD/JPY — Dólar / Iene",
    "USDCHF=X": "USD/CHF — Dólar / Franco Suíço",
    "AUDUSD=X": "AUD/USD — Dólar Australiano / Dólar",
    "USDCAD=X": "USD/CAD — Dólar / Dólar Canadense",
    "NZDUSD=X": "NZD/USD — Dólar Neozelandês / Dólar",
    "EURGBP=X": "EUR/GBP — Euro / Libra",
    "EURJPY=X": "EUR/JPY — Euro / Iene",
    "GBPJPY=X": "GBP/JPY — Libra / Iene",
    "EURCHF=X": "EUR/CHF — Euro / Franco Suíço",
    "AUDJPY=X": "AUD/JPY — Dólar Australiano / Iene",
    "EURAUD=X": "EUR/AUD — Euro / Dólar Australiano",
    "GBPCHF=X": "GBP/CHF — Libra / Franco Suíço",
    "CADJPY=X": "CAD/JPY — Dólar Canadense / Iene",
    "AUDNZD=X": "AUD/NZD — Dólar Australiano / Neozelandês",
    "EURCAD=X": "EUR/CAD — Euro / Dólar Canadense",
    "GBPAUD=X": "GBP/AUD — Libra / Dólar Australiano",
    "CHFJPY=X": "CHF/JPY — Franco Suíço / Iene",
    "NZDJPY=X": "NZD/JPY — Dólar Neozelandês / Iene",
}

def get_pares(): return list(FOREX_PARES.keys())

# ETFs de commodity (metais, energia, agricolas, cestas). Diferente do Forex,
# ESTES tem volume real -> passam pelo filtro de liquidez normalmente.
COMMODITIES = {
    "GLD":  "Ouro (SPDR Gold)",
    "SLV":  "Prata (iShares Silver)",
    "PPLT": "Platina (abrdn Platinum)",
    "PALL": "Paládio (abrdn Palladium)",
    "CPER": "Cobre (US Copper)",
    "DBB":  "Metais Base (cobre/aluminio/zinco)",
    "USO":  "Petroleo WTI (US Oil)",
    "BNO":  "Petroleo Brent (US Brent Oil)",
    "UNG":  "Gas Natural (US Natural Gas)",
    "UGA":  "Gasolina (US Gasoline)",
    "CORN": "Milho (Teucrium Corn)",
    "WEAT": "Trigo (Teucrium Wheat)",
    "SOYB": "Soja (Teucrium Soybean)",
    "CANE": "Acucar (Teucrium Sugar)",
    "COW":  "Gado/Pecuaria (iPath Livestock)",
    "JO":   "Cafe (iPath Coffee)",
    "NIB":  "Cacau (iPath Cocoa)",
    "DBC":  "Cesta de Commodities (Invesco DB)",
    "DBA":  "Cesta Agricola (Invesco DB Agri)",
    "GSG":  "Cesta Ampla (iShares S&P GSCI)",
}
def get_commodities(): return list(COMMODITIES.keys())

def is_forex(tk): return tk in FOREX_PARES  # pares de moeda usam sufixo =X

def nome_de(tk):
    if tk in FOREX_PARES: return FOREX_PARES[tk]
    if tk in COMMODITIES: return COMMODITIES[tk]
    return tk.replace("=X","")