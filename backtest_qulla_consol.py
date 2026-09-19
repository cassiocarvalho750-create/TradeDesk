#!/usr/bin/env python3
"""
COMPARA o filtro de CONSOLIDACAO do Qullamaggie — quao apertado deve ser.
Mesmo setup (momentum absoluto + rompimento + alvo 3R). Varia SO os dois
parametros da consolidacao:
  - ATR_CONTRACAO: atr5 < atr20 * X  (X maior = aceita mais volatilidade)
  - DIST_EMA_MAX:  preco a no maximo Y da EMA20 (Y maior = aceita mais esticado)

Objetivo: ver se AFROUXAR pega mais setups (como a NTNX) sem estragar a
expectancia. Se afrouxar mantiver exp e win, vale; se derrubar, o rigido
protege.

Uso: python backtest_qulla_consol.py <pasta>
"""
import glob, sys, os, argparse
import numpy as np, pandas as pd
import backtest_didi as bd

MOM_1M, MOM_3M, MOM_6M = 30.0, 90.0, 150.0
CONSOL_MIN, CONSOL_MAX = 5, 15
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

def eh_lider(r): return (r["mom1"]>=MOM_1M) or (r["mom3"]>=MOM_3M) or (r["mom6"]>=MOM_6M)

def consol_ok(d, i, atr_mult, dist_max):
    c,h,l = d["Close"],d["High"],d["Low"]
    for n in range(CONSOL_MAX, CONSOL_MIN-1, -1):
        if i-n < 1: continue
        jan = slice(i-n, i)
        hh=h.iloc[jan].max(); ll=l.iloc[jan].min(); e20=d["ema20"].iloc[jan].mean()
        if not (d["atr5"].iloc[i-1] < d["atr20"].iloc[i-1]*atr_mult): continue
        if e20<=0 or abs(c.iloc[i-1]-e20)/e20 > dist_max: continue
        if ll < e20*0.90: continue
        return True, float(hh)
    return False, None

def roda(dfs, atr_mult, dist_max):
    trades = []
    for tk, d in dfs:
        c,h,l = d["Close"],d["High"],d["Low"]; n=len(d); i=130
        while i < n-1:
            if not eh_lider(d.iloc[i]): i+=1; continue
            ok, topo = consol_ok(d, i, atr_mult, dist_max)
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
    print(f"COMPARA CONSOLIDACAO | cesta '{a.pasta}' | {len(dfs)} ativos")
    print(f"Setup: momentum absoluto + rompimento + alvo {ALVO_R:.0f}R\n")
    print(f"  {'ATR<':<8}{'dist EMA':<10}{'trades':>7}{'win':>6}{'exp':>9}{'acum':>10}{'payoff':>8}")
    print("  "+"-"*52)
    # atual = (1.0, 0.10). Testa afrouxamentos progressivos.
    combos=[
        (1.00, 0.10, "atual"),
        (1.10, 0.10, "ATR+10%"),
        (1.25, 0.10, "ATR+25%"),
        (1.00, 0.15, "dist 15%"),
        (1.25, 0.15, "ambos frouxo"),
        (0.90, 0.08, "mais RIGIDO"),
    ]
    for atr_mult, dist_max, rot in combos:
        N,wr,exp,acc,po=estat(roda(dfs, atr_mult, dist_max))
        print(f"  {atr_mult:<8.2f}{dist_max:<10.2f}{N:>7}{wr:>5.0f}%{exp:>+8.3f}R{acc:>+9.1f}R{po:>8.2f}  {rot}")
    print("\n  Leitura: afrouxar so vale se PEGAR MAIS trades (N sobe) mantendo exp positiva/estavel.")
    print("  Se exp cai quando afrouxa, o filtro rigido esta protegendo — melhor manter.")

if __name__=="__main__":
    main()
