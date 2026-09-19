#!/usr/bin/env python3
"""
COMPARA os CORTES de momentum do Qullamaggie.
Mesmo setup (consolidacao ATR 1.10 + rompimento + alvo 3R). Varia SO os cortes
de momentum (1M/3M/6M), pra ver se baixar a barra (pegando lideres moderados
como a NTNX) mantem a expectancia ou estraga.

Uso: python backtest_qulla_momentum.py <pasta>
"""
import glob, sys, os, argparse
import numpy as np, pandas as pd
import backtest_didi as bd

CONSOL_MIN, CONSOL_MAX = 5, 15
ATR_CONTRACAO = 1.10
DIST_EMA_MAX = 0.10
ALVO_R = 3.0
MAX_HOLD = 120

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(h, l, c, n):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def prep(d):
    c, h, l = d["Close"], d["High"], d["Low"]; d = d.copy()
    d["ema20"] = ema(c, 20); d["atr5"] = atr(h,l,c,5); d["atr20"] = atr(h,l,c,20)
    d["mom1"]=(c/c.shift(21)-1)*100; d["mom3"]=(c/c.shift(63)-1)*100; d["mom6"]=(c/c.shift(126)-1)*100
    return d

def consol_ok(d, i):
    c,h,l = d["Close"],d["High"],d["Low"]
    for n in range(CONSOL_MAX, CONSOL_MIN-1, -1):
        if i-n < 1: continue
        jan = slice(i-n, i)
        hh=h.iloc[jan].max(); ll=l.iloc[jan].min(); e20=d["ema20"].iloc[jan].mean()
        if not (d["atr5"].iloc[i-1] < d["atr20"].iloc[i-1]*ATR_CONTRACAO): continue
        if e20<=0 or abs(c.iloc[i-1]-e20)/e20 > DIST_EMA_MAX: continue
        if ll < e20*0.90: continue
        return True, float(hh)
    return False, None

def roda(dfs, m1, m3, m6):
    trades = []
    for tk, d in dfs:
        c,h,l = d["Close"],d["High"],d["Low"]; n=len(d); i=130
        while i < n-1:
            r=d.iloc[i]
            lider=(r["mom1"]>=m1) or (r["mom3"]>=m3) or (r["mom6"]>=m6)
            if not lider: i+=1; continue
            ok, topo = consol_ok(d, i)
            if not ok: i+=1; continue
            if not (float(h.iloc[i])>topo): i+=1; continue
            entry=max(topo,float(d["Open"].iloc[i])); stop=float(l.iloc[i]); risk=entry-stop
            if risk<=0: i+=1; continue
            alvo=entry+ALVO_R*risk; res=None; saiu=i+1
            for j in range(i+1,min(i+MAX_HOLD,n)):
                saiu=j
                if float(l.iloc[j])<=stop: res=-1.0; break
                if float(h.iloc[j])>=alvo: res=ALVO_R; break
            if res is None: res=(float(c.iloc[min(i+MAX_HOLD,n-1)])-entry)/risk; saiu=min(i+MAX_HOLD,n-1)
            trades.append(res); i=saiu+1
    return trades

def estat(rs):
    if not rs: return (0,0,0,0,0)
    a=np.array(rs); N=len(a); wr=100*(a>0).mean(); exp=a.mean(); acc=a.sum()
    g=a[a>0]; p=a[a<=0]; po=(g.mean()/abs(p.mean())) if len(g) and len(p) else 0
    return (N,wr,exp,acc,po)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("pasta",nargs="?",default="prices_todos"); a=ap.parse_args()
    arqs=sorted(glob.glob(f"{a.pasta}/*.csv")); dfs=[]
    for arq in arqs:
        tk=os.path.basename(arq).replace(".csv","").upper()
        if tk=="SP500": continue
        try:
            d=bd.carrega(arq)
            if len(d)>=200: dfs.append((tk, prep(d)))
        except: pass
    print(f"COMPARA CORTES DE MOMENTUM | cesta '{a.pasta}' | {len(dfs)} ativos")
    print(f"Setup: consolidacao ATR{ATR_CONTRACAO} + rompimento + alvo {ALVO_R:.0f}R\n")
    print(f"  {'cortes 1M/3M/6M':<18}{'trades':>7}{'win':>6}{'exp':>9}{'acum':>10}{'payoff':>8}")
    print("  "+"-"*58)
    combos=[
        (30, 90, 150, "PURO (atual)"),
        (25, 75, 125, "medio-alto"),
        (20, 60, 100, "moderado (pega NTNX?)"),
        (15, 45, 80,  "baixo"),
        (40, 120, 200,"so foguetes"),
    ]
    for m1,m3,m6,rot in combos:
        N,wr,exp,acc,po=estat(roda(dfs, m1, m3, m6))
        print(f"  {f'+{m1}/+{m3}/+{m6}':<18}{N:>7}{wr:>5.0f}%{exp:>+8.3f}R{acc:>+9.1f}R{po:>8.2f}  {rot}")
    print("\n  Leitura: baixar os cortes so vale se a exp SEGURAR positiva/estavel com mais trades.")
    print("  Se a exp cai ao baixar, os cortes puros protegem a qualidade (foguetes de verdade).")

if __name__=="__main__":
    main()
