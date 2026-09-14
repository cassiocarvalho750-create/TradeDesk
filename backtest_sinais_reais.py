#!/usr/bin/env python3
"""
Backtest dos sinais REAIS registrados (forward test). Le os historicos gerados
dia a dia pelos scanners (sinais gerados AO VIVO, sem vies de olhar o futuro) e
mede a efetividade real: baixa o preco de cada ativo A PARTIR da data do sinal
e simula o trade (entrada, stop, parcial 2R + breakeven + saida).

Da a efetividade real do scanner E quebra por categoria (quais situacoes valem
mais): no DIDI por tipo (3JUNTOS/ABERTURA/ADXHOJE) e MME70; no Insidebar por
grupo (ENTRAR/RADAR).

USO:
  python backtest_sinais_reais.py didi
  python backtest_sinais_reais.py insidebar

Precisa de dados de preco. Baixa via yfinance (ajuste se preferir CSV local).
Roda quando voce ja tiver ACUMULADO sinais suficientes (idealmente 3+ meses).
"""
import sys, os, csv
from collections import defaultdict

def baixa(tk, desde):
    import yfinance as yf
    d=yf.Ticker(tk).history(start=desde, interval="1d", auto_adjust=True)
    if d is None or d.empty: return None
    d.columns=[c.capitalize() for c in d.columns]
    if d.index.tz is not None: d.index=d.index.tz_localize(None)
    return d

def simula_trade(d, data_sinal, entry, stop, max_hold=60):
    """A partir do dia SEGUINTE ao sinal, simula: parcial 50% em 2R (breakeven)
    + 50% ate 3R. Retorna R do trade (media ponderada) ou None."""
    import pandas as pd
    risk=entry-stop
    if risk<=0: return None
    try:
        idx=d.index.searchsorted(pd.Timestamp(data_sinal))
    except Exception:
        return None
    a1=entry+2*risk; a2=entry+3*risk
    p1=None;p2=None;st=stop
    for j in range(idx+1, min(idx+1+max_hold, len(d))):
        lo=float(d["Low"].iloc[j]); hi=float(d["High"].iloc[j])
        if p1 is None:
            if lo<=st: p1=-1.0;p2=-1.0;break
            if hi>=a1: p1=2.0; st=entry
        if p1 is not None and p2 is None:
            if lo<=st: p2=0.0 if st==entry else -1.0; break
            if hi>=a2: p2=3.0; break
    if p1 is None:
        c=float(d["Close"].iloc[min(idx+max_hold,len(d)-1)]); f=(c-entry)/risk; p1=f;p2=f
    elif p2 is None:
        c=float(d["Close"].iloc[min(idx+max_hold,len(d)-1)]); p2=(c-entry)/risk
    return 0.5*p1+0.5*p2

def st(rs):
    if not rs: return (0,0,0,0)
    n=len(rs); return (n,100*sum(1 for x in rs if x>0)/n,sum(rs)/n,sum(rs))

def main():
    sist = sys.argv[1] if len(sys.argv)>1 else "didi"
    arq = f"historico_sinais_{sist}.csv"
    if not os.path.exists(arq):
        print(f"Arquivo {arq} nao encontrado. Rode os scanners por um tempo primeiro."); return
    linhas=list(csv.DictReader(open(arq,encoding="utf-8")))
    print(f"Forward test — {sist.upper()} | {len(linhas)} sinais registrados\n")

    # cache de precos por ticker (baixa a partir do 1o sinal daquele ticker)
    por_tk=defaultdict(list)
    for r in linhas: por_tk[r["ticker"]].append(r)
    dados={}
    todos=[]; porcat=defaultdict(list)
    tkmarket = lambda r: (r["ticker"]+".SA") if r.get("market")=="B3" else r["ticker"]
    for tk, sinais in por_tk.items():
        desde=min(s["data"] for s in sinais)
        try:
            d=baixa(tkmarket(sinais[0]), desde)
        except Exception as e:
            d=None
        if d is None: continue
        for s in sinais:
            try:
                entry=float(s["entrada"]); stop=float(s["stop"])
            except: continue
            R=simula_trade(d, s["data"], entry, stop)
            if R is None: continue
            todos.append(R)
            if sist=="didi":
                porcat[("tipo",s.get("tipo","?"))].append(R)
                porcat[("mme70",s.get("mme70","?"))].append(R)
                porcat[("tipo+mme70",f"{s.get('tipo','?')}|{s.get('mme70','?')}")].append(R)
            else:
                porcat[("grupo",s.get("grupo","?"))].append(R)

    N,wr,exp,acc=st(todos)
    print(f"GERAL: {N} trades | win {wr:.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R\n")
    print("Por categoria (efetividade de cada situacao):")
    cat_atual=None
    for (cat,val),rs in sorted(porcat.items()):
        if cat!=cat_atual: print(f"\n  [{cat}]"); cat_atual=cat
        n,w,e,a=st(rs)
        print(f"    {val:<22} {n:>4} trades | win {w:4.0f}% | exp {e:+.3f}R | acum {a:+.0f}R")

if __name__=="__main__":
    main()
