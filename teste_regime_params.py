#!/usr/bin/env python3
"""Varia os parametros do filtro de regime (VTI) para achar a melhor config.
Estrategia definitiva (2R+BE+3R), filtro so em acoes US. Roda na pasta passada.
Testa: periodo da media (SMA), lookback do 'caindo', e a regra (abaixo/caindo/ambos)."""
import glob, sys, os
import numpy as np, pandas as pd
import backtest_insidebar as bt, insidebar_engine as ib

def is_naous(tk): return tk.endswith(".SA") or tk.upper().endswith(".TW") or tk in ("0050",)

def regime_ruim(vti_close, sma_len, slope_lb, regra):
    sma=vti_close.rolling(sma_len).mean()
    abaixo = vti_close < sma
    caindo = sma < sma.shift(slope_lb)
    if regra=="abaixo":       return abaixo
    if regra=="caindo":       return caindo
    return abaixo & caindo    # ambos (padrao)

def roda(arqs, vti_close, sma_len, slope_lb, regra):
    ruim = regime_ruim(vti_close, sma_len, slope_lb, regra) if vti_close is not None else None
    Rs=[]
    for tk,d in arqs:
        o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
        base=ib._series_base(d); n=len(d)
        D=max(ib.EMA_LEN,ib.ATR_SLOW,ib.CONS_MAX)+2*ib.SWING_K+2
        while D<n-1:
            r=ib.avaliar_em(d,D,base=base)
            if r.get("ok"):
                nx=D+1
                if nx<n and float(c.iloc[nx])>r["ib_high"]:
                    data=d.index[nx]
                    if ruim is not None and (not is_naous(tk)):
                        if data in ruim.index and bool(ruim.loc[data]):
                            D=nx+1; continue
                    entry=float(c.iloc[nx])
                    _,ll=ib._swings(h.iloc[:nx+1],l.iloc[:nx+1],ib.SWING_K)
                    stop=float(l.iloc[ll[-1]]) if ll else float(r["ib_low"]); risk=entry-stop
                    if risk>0:
                        a1=entry+2*risk;a2=entry+3*risk;p1=None;p2=None;st=stop
                        for j in range(nx+1,min(nx+61,n)):
                            lo=float(l.iloc[j]);hi=float(h.iloc[j])
                            if p1 is None:
                                if lo<=st:p1=-1.0;p2=-1.0;break
                                if hi>=a1:p1=2.0;st=entry
                            if p1 is not None and p2 is None:
                                if lo<=st:p2=0.0 if st==entry else -1.0;break
                                if hi>=a2:p2=3.0;break
                        if p1 is None:fim=(float(c.iloc[min(nx+60,n-1)])-entry)/risk;p1=fim;p2=fim
                        elif p2 is None:p2=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        Rs.append(0.5*p1+0.5*p2)
                    D=nx+1;continue
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
vp=os.path.join(pasta,"vti.csv")
vti=bt.carrega(vp)["Close"] if os.path.exists(vp) else None
print(f"Cesta '{pasta}' | {len(arqs)} ativos | VTI: {'sim' if vti is not None else 'NAO'}\n")

N,wr,exp,acc=st(roda(arqs,None,0,0,"nenhum"))
print(f"  SEM filtro            {N:>4}t win{wr:4.0f}% exp{exp:+.3f}R acum{acc:+.0f}R\n")

print("--- REGRA (SMA200, caindo=5d) ---")
for regra in ["abaixo","caindo","ambos"]:
    N,wr,exp,acc=st(roda(arqs,vti,200,5,regra))
    print(f"  {regra:<8}            {N:>4}t win{wr:4.0f}% exp{exp:+.3f}R acum{acc:+.0f}R")
print()
print("--- PERIODO da media (regra=ambos, caindo=5d) ---")
for smal in [100,150,200]:
    N,wr,exp,acc=st(roda(arqs,vti,smal,5,"ambos"))
    print(f"  SMA{smal:<4}            {N:>4}t win{wr:4.0f}% exp{exp:+.3f}R acum{acc:+.0f}R")
print()
print("--- LOOKBACK do 'caindo' (SMA200, regra=ambos) ---")
for lb in [1,5,10,20]:
    N,wr,exp,acc=st(roda(arqs,vti,200,lb,"ambos"))
    print(f"  caindo={lb:<3}d         {N:>4}t win{wr:4.0f}% exp{exp:+.3f}R acum{acc:+.0f}R")
