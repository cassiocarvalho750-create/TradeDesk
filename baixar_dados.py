#!/usr/bin/env python3
"""
Baixa historico diario de uma lista de tickers (via Yahoo/yfinance) e salva um
CSV por ativo, no MESMO formato do backtest (date,open,high,low,close,volume,
div,split). Use para montar cestas de teste (ex.: robustez em ativos diferentes).

USO:
  python baixar_dados.py                 -> baixa a CESTA_TESTE abaixo em prices_teste/
  python baixar_dados.py MINHA_PASTA T1 T2 T3   -> baixa T1,T2,T3 em MINHA_PASTA/

Requer: pip install yfinance pandas
"""
import os, sys
import yfinance as yf

# Cesta AMPLA e VARIADA (oposto de techs) — bancos, energia, consumo, saude,
# industria, etc. Boa para testar se o setup e robusto fora das techs vencedoras.
# US + algumas B3 (.SA). Troque a vontade.
CESTA_TESTE = [
    # bancos / financeiro
    "JPM","BAC","WFC","GS","AXP",
    # energia / petroleo
    "XOM","CVX","COP",
    # consumo / varejo
    "KO","PEP","PG","WMT","MCD","COST",
    # saude / farma
    "JNJ","PFE","MRK","UNH","ABT",
    # industria / transporte
    "CAT","DE","UPS","BA","HON",
    # utilities / telecom
    "NEE","DUK","SO","VZ","T",
    # B3 (brasileiras) — variadas
    "ITUB4.SA","BBDC4.SA","PETR4.SA","VALE3.SA","ABEV3.SA",
    "WEGE3.SA","RADL3.SA","EQTL3.SA","SUZB3.SA","RENT3.SA",
]

def baixa_um(tk, pasta, period="10y"):
    try:
        d = yf.Ticker(tk).history(period=period, interval="1d", auto_adjust=True, actions=True)
        if d is None or d.empty:
            print(f"  {tk}: SEM dados"); return False
        d = d.reset_index()
        # normaliza nomes de coluna
        d.columns = [str(c).lower() for c in d.columns]
        # data
        col_data = "date" if "date" in d.columns else d.columns[0]
        out = d.rename(columns={col_data:"date"})
        for c in ["open","high","low","close","volume"]:
            if c not in out.columns: out[c]=""
        # dividendos e splits (se existirem)
        out["div"]   = out["dividends"]   if "dividends"   in out.columns else ""
        out["split"] = out["stock splits"] if "stock splits" in out.columns else ""
        out["date"] = out["date"].astype(str).str[:10]
        out = out[["date","open","high","low","close","volume","div","split"]]
        # zera div/split iguais a 0 (deixa vazio, como nos dados originais)
        for c in ["div","split"]:
            out[c] = out[c].apply(lambda v: "" if (v in (0,0.0,"0","0.0")) else v)
        nome = tk.lower().replace(".sa",".sa")  # mantem sufixo
        path = os.path.join(pasta, f"{nome}.csv")
        out.to_csv(path, index=False)
        print(f"  {tk}: {len(out)} candles -> {path}")
        return True
    except Exception as e:
        print(f"  {tk}: ERRO {str(e)[:50]}"); return False

def main():
    args = sys.argv[1:]
    if args:
        pasta = args[0]; tickers = args[1:] if len(args)>1 else CESTA_TESTE
    else:
        pasta = "prices_teste"; tickers = CESTA_TESTE
    os.makedirs(pasta, exist_ok=True)
    print(f"Baixando {len(tickers)} ativos para '{pasta}/' ...\n")
    ok=0
    for tk in tickers:
        if baixa_um(tk, pasta): ok+=1
    print(f"\nConcluido: {ok}/{len(tickers)} baixados em '{pasta}/'")
    print(f"Para rodar o backtest nesta cesta:")
    print(f"  python backtest_insidebar.py {pasta}")

if __name__=="__main__":
    main()
