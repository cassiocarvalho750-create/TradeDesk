#!/usr/bin/env python3
"""
Compara trades da AGULHADA pela proporcao do CORPO do candle de entrada:
  CORPO GRANDE = |Close-Open| >= 60% do range (High-Low)  -> convicção
  CORPO PEQUENO= |Close-Open| <= 40% do range             -> indecisão (tails longos)
Saida vencedora: stop pivo 3x3 + parcial 2R (BE) + saida TRIX.
Uso: python backtest_didi_corpo.py <pasta>
"""
import glob, sys, os
import numpy as np, pandas as pd
import bt_engine as bt
import backtest_didi as bd

GRANDE=0.60; PEQUENO=0.40

def swings_low(h,l,pos,k=3):
    lv=l.values
    cand=[i for i in range(k,pos-k+1) if lv[i]==lv[i-k:i+k+1].min() and lv[i-k:i+k+1].argmin()==k]
    return float(l.iloc[cand[-1]]) if cand else None

def backtest(d, tk):
    s=bt.compute_signals_windowed(d)
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    trf,trs=bd.trix_ema(c)
    trix_venda=(trf<trs)&(trf.shift(1)>=trs.shift(1))
    n=len(d); grande=[];pequeno=[]
    i=80
    while i<n-1:
        if not bool(s["signal_win"].iloc[i]): i+=1; continue
        rng=float(h.iloc[i])-float(l.iloc[i])
        corpo=abs(float(c.iloc[i])-float(o.iloc[i]))
        frac = corpo/rng if rng>0 else 0
        grupo = "grande" if frac>=GRANDE else ("pequeno" if frac<=PEQUENO else None)
        if grupo is None: i+=1; continue   # zona intermediaria: ignora
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
        (grande if grupo=="grande" else pequeno).append(R)
        i=saiu+1
    return grande,pequeno

def st(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

def main():
    pasta=sys.argv[1] if len(sys.argv)>1 else "prices"
    G=[];P=[]
    for a in sorted(glob.glob(f"{pasta}/*.csv")):
        try:
            d=bd.carrega(a)
            if len(d)<150: continue
            g,p=backtest(d, os.path.basename(a)); G+=g;P+=p
        except: pass
    print(f"Agulhada por CORPO do candle de entrada | cesta '{pasta}'")
    print(f"grande>= {int(GRANDE*100)}% do range | pequeno<= {int(PEQUENO*100)}% | saida pivo+2R+TRIX\n")
    print(f"  {'grupo':<24}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
    for nome,rs in [("CORPO GRANDE (conviccao)",G),("CORPO PEQUENO (tails)",P)]:
        N,wr,exp,acc=st(rs)
        print(f"  {nome:<24}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")

if __name__=="__main__":
    main()
