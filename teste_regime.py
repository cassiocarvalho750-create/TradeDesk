#!/usr/bin/env python3
"""Testa o filtro de REGIME de mercado: nao operar acoes US quando
VTI < SMA200 E SMA200 caindo. Compara backtest COM e SEM o filtro.
Estrategia: definitiva (parcial 2R+BE+3R). Roda na pasta passada."""
import glob, sys, os
import numpy as np, pandas as pd
import backtest_insidebar as bt, insidebar_engine as ib

SMA_LEN=200; SMA_SLOPE_LB=5   # SMA200; "caindo" = SMA200 hoje < SMA200 de 5 dias atras

def carrega_vti(pasta):
    p=os.path.join(pasta,"vti.csv")
    if not os.path.exists(p): return None
    d=bt.carrega(p)
    sma=d["Close"].rolling(SMA_LEN).mean()
    # regime RUIM (nao operar): close<sma E sma caindo
    regime_ruim = (d["Close"]<sma) & (sma < sma.shift(SMA_SLOPE_LB))
    return regime_ruim  # Series indexada por data

def is_b3(tk): return tk.endswith(".SA") or tk.upper().endswith(".TW") or tk in ("0050",)

def roda(preps_arqs, vti_regime, usar_filtro):
    Rs=[]
    for tk,d in preps_arqs:
        o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
        base=ib._series_base(d); n=len(d)
        D=max(ib.EMA_LEN,ib.ATR_SLOW,ib.CONS_MAX)+2*ib.SWING_K+2
        while D<n-1:
            r=ib.avaliar_em(d,D,base=base)
            if r.get("ok"):
                nx=D+1
                if nx<n and float(c.iloc[nx])>r["ib_high"]:
                    data_entrada=d.index[nx]
                    # FILTRO DE REGIME: so aplica em acoes US (nao B3/TW)
                    if usar_filtro and (not is_b3(tk)) and vti_regime is not None:
                        if data_entrada in vti_regime.index and bool(vti_regime.loc[data_entrada]):
                            D=nx+1; continue   # mercado ruim: pula o trade
                    entry=float(c.iloc[nx])
                    _,ll=ib._swings(h.iloc[:nx+1],l.iloc[:nx+1],ib.SWING_K)
                    stop=float(l.iloc[ll[-1]]) if ll else float(r["ib_low"])
                    risk=entry-stop
                    if risk>0:
                        a1=entry+2*risk; a2=entry+3*risk; p1=None;p2=None;st=stop
                        for j in range(nx+1,min(nx+61,n)):
                            lo=float(l.iloc[j]);hi=float(h.iloc[j])
                            if p1 is None:
                                if lo<=st: p1=-1.0;p2=-1.0;break
                                if hi>=a1: p1=2.0; st=entry
                            if p1 is not None and p2 is None:
                                if lo<=st: p2=0.0 if st==entry else -1.0; break
                                if hi>=a2: p2=3.0; break
                        if p1 is None: fim=(float(c.iloc[min(nx+60,n-1)])-entry)/risk; p1=fim;p2=fim
                        elif p2 is None: p2=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        Rs.append(0.5*p1+0.5*p2)
                    D=nx+1; continue
            D+=1
    return Rs

def st(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

pasta=sys.argv[1] if len(sys.argv)>1 else "prices"
arqs=[]
for a in sorted(glob.glob(f"{pasta}/*.csv")):
    tk=os.path.basename(a).replace(".csv","")
    try:
        d=bt.carrega(a)
        if len(d)>=150: arqs.append((tk,d))
    except: pass
vti=carrega_vti(pasta)
print(f"Cesta '{pasta}' | {len(arqs)} ativos | estrategia 2R+BE+3R")
print(f"VTI carregado: {'sim' if vti is not None else 'NAO (filtro nao aplica)'}\n")
print(f"  {'versao':<20}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
N,wr,exp,acc=st(roda(arqs,vti,False))
print(f"  {'SEM filtro':<20}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")
N,wr,exp,acc=st(roda(arqs,vti,True))
print(f"  {'COM filtro regime':<20}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")
