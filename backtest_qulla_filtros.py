#!/usr/bin/env python3
"""
============================================================================
COMPARA FILTROS DE MOMENTUM — Qullamaggie
============================================================================
Mesmo setup (consolidacao + rompimento + alvo 3R). Muda SO o filtro de
momentum, p/ ver qual seleciona melhor os lideres:

  1) ABSOLUTO (atual): +30%/1M ou +90%/3M ou +150%/6M (cortes fixos)
  2) FORCA RELATIVA:   top X% de retorno de 3M/6M entre TODOS os ativos
                       naquele dia (adaptativo ao mercado)
  3) COMBINADO:        forca relativa alta E piso minimo absoluto

Uso: python backtest_qulla_filtros.py <pasta>
============================================================================
"""
import glob, sys, os, argparse
import numpy as np, pandas as pd
import backtest_didi as bd

CONSOL_MIN, CONSOL_MAX = 5, 15
ATR_CONTRACAO = 1.0
DIST_EMA_MAX = 0.10
ALVO_R = 3.0
MAX_HOLD = 120

# cortes
ABS_1M, ABS_3M, ABS_6M = 30.0, 90.0, 150.0   # filtro absoluto
RS_TOP_PCT = 10.0        # forca relativa: top 10% de mom3
RS_PISO_3M = 20.0        # combinado: piso minimo de +20% em 3M

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(h, l, c, n):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def prep(d):
    c, h, l = d["Close"], d["High"], d["Low"]; d = d.copy()
    d["ema20"] = ema(c, 20)
    d["atr5"] = atr(h,l,c,5); d["atr20"] = atr(h,l,c,20)
    d["mom1"] = (c/c.shift(21)-1)*100
    d["mom3"] = (c/c.shift(63)-1)*100
    d["mom6"] = (c/c.shift(126)-1)*100
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

def simula_trade(d, i):
    c,h,l = d["Close"],d["High"],d["Low"]
    ok, topo = consol_ok(d, i)
    if not ok: return None, i+1
    if not (float(h.iloc[i])>topo): return None, i+1
    entry = max(topo, float(d["Open"].iloc[i])); stop=float(l.iloc[i]); risk=entry-stop
    if risk<=0: return None, i+1
    alvo = entry + ALVO_R*risk; res=None; saiu=i+1
    for j in range(i+1, min(i+MAX_HOLD, len(d))):
        saiu=j
        if float(l.iloc[j])<=stop: res=-1.0; break
        if float(h.iloc[j])>=alvo: res=ALVO_R; break
    if res is None:
        res=(float(c.iloc[min(i+MAX_HOLD,len(d)-1)])-entry)/risk; saiu=min(i+MAX_HOLD,len(d)-1)
    return res, saiu+1

def roda(dfs, criterio):
    """criterio(d, i, ranks) -> bool (se e lider naquele candle)."""
    trades = []
    for tk, d in dfs:
        n=len(d); i=130
        while i < n-1:
            if not criterio(d, i): i+=1; continue
            res, prox = simula_trade(d, i)
            if res is None: i = prox; continue
            trades.append(res); i = prox
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

    # --- para a FORCA RELATIVA: monta o percentil de mom3 por DATA ---
    # junta todos os mom3 num painel [data x ticker] e calcula o limiar do top X%.
    mom3_por_data = {}
    for tk, d in dfs:
        for dt, v in d["mom3"].items():
            if not np.isnan(v):
                mom3_por_data.setdefault(dt, []).append(v)
    limiar_rs = {dt: np.percentile(vals, 100-RS_TOP_PCT) for dt, vals in mom3_por_data.items() if len(vals)>=10}

    def crit_absoluto(d, i):
        r=d.iloc[i]
        return (r["mom1"]>=ABS_1M) or (r["mom3"]>=ABS_3M) or (r["mom6"]>=ABS_6M)
    def crit_rs(d, i):
        dt=d.index[i]; v=d["mom3"].iloc[i]
        lim=limiar_rs.get(dt)
        return (lim is not None) and (not np.isnan(v)) and (v>=lim)
    def crit_combo(d, i):
        return crit_rs(d, i) and (d["mom3"].iloc[i]>=RS_PISO_3M)

    print(f"COMPARA FILTROS DE MOMENTUM | cesta '{a.pasta}' | {len(dfs)} ativos")
    print(f"Setup fixo: consolidacao {CONSOL_MIN}-{CONSOL_MAX}d + rompimento + alvo {ALVO_R:.0f}R\n")
    print(f"  {'filtro':<24}{'trades':>7}{'win':>6}{'exp':>9}{'acum':>10}{'payoff':>8}")
    print("  "+"-"*62)
    for nome, crit in [
        (f"ABSOLUTO (+{ABS_1M:.0f}/+{ABS_3M:.0f}/+{ABS_6M:.0f})", crit_absoluto),
        (f"FORCA RELATIVA (top {RS_TOP_PCT:.0f}%)", crit_rs),
        (f"COMBINADO (RS + piso {RS_PISO_3M:.0f}%)", crit_combo),
    ]:
        N,wr,exp,acc,po = estat(roda(dfs, crit))
        print(f"  {nome:<24}{N:>7}{wr:>5.0f}%{exp:>+8.3f}R{acc:>+9.1f}R{po:>8.2f}")
    print("\n  Melhor = maior EXP mantendo trades suficientes (>100) e win razoavel.")

if __name__=="__main__":
    main()
