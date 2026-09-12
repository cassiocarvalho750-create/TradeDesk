#!/usr/bin/env python3
"""
Compara trades da AGULHADA COM vs SEM dois filtros extras no candle de entrada:
  - Estocastico lento (8,3,3) comprado: %K > %D
  - TRIX (9,4) comprado: linha do TRIX > linha de sinal
Saida vencedora: stop pivo 3x3 + parcial 2R (BE) + saida TRIX.
Uso: python backtest_didi_filtros.py <pasta>
"""
import glob, sys, os
import numpy as np, pandas as pd
import bt_engine as bt
import backtest_didi as bd

def swings_low(h,l,pos,k=3):
    lv=l.values
    cand=[i for i in range(k,pos-k+1) if lv[i]==lv[i-k:i+k+1].min() and lv[i-k:i+k+1].argmin()==k]
    return float(l.iloc[cand[-1]]) if cand else None

def backtest(d, tk):
    s=bt.compute_signals_windowed(d)
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    # filtros no candle de entrada
    kS,dS=bt.stochastic(d, k=8, d=3, smooth=3)
    stoch_ok = kS > dS                      # %K acima de %D
    trx,sig = bt.trix(c, length=9, signal=4)
    trix_ok = trx > sig                     # linha do TRIX acima do sinal
    # saida (TRIX vira p/ baixo) — mesmo trix da saida vencedora
    trf,trs=bd.trix_ema(c)
    trix_venda=(trf<trs)&(trf.shift(1)>=trs.shift(1))
    n=len(d)
    com=[]; sem=[]
    i=80
    while i<n-1:
        if not bool(s["signal_win"].iloc[i]): i+=1; continue
        # os dois filtros valem HOJE?
        filtros = bool(stoch_ok.iloc[i]) and bool(trix_ok.iloc[i])
        entry=float(c.iloc[i]); sp=swings_low(h,l,i,3); stop=sp if sp is not None else float(l.iloc[i])
        risk=entry-stop
        if risk<=0: i+=1; continue
        a1=entry+2*risk; p1=None;p2=None;st=stop; saiu=i+1
        for j in range(i+1,min(i+120,n)):
            saiu=j; lo=float(l.iloc[j]);hi=float(h.iloc[j])
            if p1 is None:
                if lo<=st:p1=-1.0;p2=-1.0;break
                if hi>=a1:p1=2.0;st=entry
            if p1 is not None and p2 is None:
                if lo<=st:p2=0.0 if st==entry else -1.0;break
                if bool(trix_venda.iloc[j]):p2=(float(c.iloc[j])-entry)/risk;break
        if p1 is None:fim=(float(c.iloc[min(i+119,n-1)])-entry)/risk;p1=fim;p2=fim;saiu=min(i+119,n-1)
        elif p2 is None:p2=(float(c.iloc[min(i+119,n-1)])-entry)/risk;saiu=min(i+119,n-1)
        R=0.5*p1+0.5*p2
        (com if filtros else sem).append(R)
        i=saiu+1
    return com, sem

def st(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

def main():
    pasta=sys.argv[1] if len(sys.argv)>1 else "prices"
    COM=[]; SEM=[]
    for a in sorted(glob.glob(f"{pasta}/*.csv")):
        try:
            d=bd.carrega(a)
            if len(d)<150: continue
            c1,c2=backtest(d, os.path.basename(a))
            COM+=c1; SEM+=c2
        except: pass
    print(f"Agulhada + filtros (Estocastico %K>%D E TRIX>sinal) | cesta '{pasta}'")
    print(f"Saida: pivo + parcial 2R + TRIX\n")
    print(f"  {'grupo':<28}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
    for nome,rs in [("COM os 2 filtros",COM),("SEM (falta pelo menos 1)",SEM),("TODOS (com+sem)",COM+SEM)]:
        N,wr,exp,acc=st(rs)
        print(f"  {nome:<28}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")

if __name__=="__main__":
    main()
