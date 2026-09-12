#!/usr/bin/env python3
"""
Backtest do setup AGULHADA DO DIDI (compra, diario).
Sinal de entrada: mesma logica do scanner (compute_signals_windowed -> signal_win):
  BB abrindo, candle verde, DIDI cruzou na janela e comprado hoje, ADX comprado
  e subindo hoje.

Testa 3 STOPS e 2 SAIDAS, para comparar:
  STOPS:  'min_ent'  = minima do candle de entrada
          'min_ant'  = minima do candle anterior ao de entrada
          'pivo'     = ultimo pivo de baixa 3x3
  SAIDAS: 'trix'  = parcial 50% em 2R + resto sai quando TRIX EMA4 cruza EMA9 p/ baixo
          'adx'   = sai tudo quando o ADX vira p/ baixo (ADX hoje < ADX ontem)

Entrada: fechamento do candle do sinal.
Uso: python backtest_didi.py <pasta>
"""
import glob, sys, os
import numpy as np, pandas as pd
import bt_engine as bt

TRIX_FAST=4; TRIX_SLOW=9   # EMAs do TRIX conforme especificado

def carrega(path):
    d=pd.read_csv(path, parse_dates=["date"]).set_index("date")
    d=d.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})
    return d[["Open","High","Low","Close","Volume"]].dropna()

def swings_low(h,l,pos,k=3):
    lv=l.values
    cand=[i for i in range(k,pos-k+1) if lv[i]==lv[i-k:i+k+1].min() and lv[i-k:i+k+1].argmin()==k]
    return float(l.iloc[cand[-1]]) if cand else None

def trix_ema(close):
    """TRIX (tripla EMA do %change) e suas EMAs 4 e 9 para o cruzamento."""
    e1=close.ewm(span=15,adjust=False).mean()  # TRIX base (len 15 ~ padrao Didi)
    e2=e1.ewm(span=15,adjust=False).mean()
    e3=e2.ewm(span=15,adjust=False).mean()
    tr=e3.pct_change()*100.0
    ema_f=tr.ewm(span=TRIX_FAST,adjust=False).mean()
    ema_s=tr.ewm(span=TRIX_SLOW,adjust=False).mean()
    return ema_f, ema_s

def backtest(d, tk, stop_modo, saida_modo, max_hold=120):
    s=bt.compute_signals_windowed(d)
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    adx=s["adx"]
    trf,trs=trix_ema(c)
    trix_venda=(trf < trs) & (trf.shift(1) >= trs.shift(1))
    adx_kick=(adx < adx.shift(1))
    n=len(d); trades=[]
    i=60
    while i < n-1:
        if not bool(s["signal_win"].iloc[i]): i+=1; continue
        entry=float(c.iloc[i])
        if stop_modo=="min_ent":  stop=float(l.iloc[i])
        elif stop_modo=="min_ant": stop=float(l.iloc[i-1])
        else:                      sp=swings_low(h,l,i,3); stop=sp if sp is not None else float(l.iloc[i])
        risk=entry-stop
        if risk<=0: i+=1; continue
        saiu_em=i+1  # candle em que o trade fecha (p/ evitar sobreposicao)
        if saida_modo=="adx":
            res=None
            for j in range(i+1,min(i+max_hold,n)):
                saiu_em=j
                if float(l.iloc[j])<=stop: res=-1.0; break
                if bool(adx_kick.iloc[j]): res=(float(c.iloc[j])-entry)/risk; break
            if res is None: res=(float(c.iloc[min(i+max_hold,n-1)])-entry)/risk; saiu_em=min(i+max_hold,n-1)
            trades.append(res)
        else:
            alvo1=entry+2*risk; p1=None;p2=None;st=stop
            for j in range(i+1,min(i+max_hold,n)):
                saiu_em=j
                lo=float(l.iloc[j]);hi=float(h.iloc[j])
                if p1 is None:
                    if lo<=st: p1=-1.0;p2=-1.0;break
                    if hi>=alvo1: p1=2.0; st=entry
                if p1 is not None and p2 is None:
                    if lo<=st: p2=0.0 if st==entry else -1.0; break
                    if bool(trix_venda.iloc[j]): p2=(float(c.iloc[j])-entry)/risk; break
            if p1 is None: fim=(float(c.iloc[min(i+max_hold,n-1)])-entry)/risk; p1=fim;p2=fim; saiu_em=min(i+max_hold,n-1)
            elif p2 is None: p2=(float(c.iloc[min(i+max_hold,n-1)])-entry)/risk; saiu_em=min(i+max_hold,n-1)
            trades.append(0.5*p1+0.5*p2)
        i = saiu_em + 1   # PULA ate depois do trade fechar (sem sobreposicao)
    return trades

def st(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

def main():
    pasta=sys.argv[1] if len(sys.argv)>1 else "prices"
    arqs=sorted(glob.glob(f"{pasta}/*.csv"))
    dfs=[]
    for a in arqs:
        tk=os.path.basename(a).replace(".csv","").upper()
        try:
            d=carrega(a)
            if len(d)>=150: dfs.append((tk,d))
        except: pass
    print(f"Backtest AGULHADA DO DIDI | cesta '{pasta}' | {len(dfs)} ativos\n")
    print(f"  {'stop':<10}{'saida':<8}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
    for stop_modo in ["min_ent","min_ant","pivo"]:
        for saida_modo in ["trix","adx"]:
            todos=[]
            for tk,d in dfs:
                try: todos+=backtest(d,tk,stop_modo,saida_modo)
                except: pass
            N,wr,exp,acc=st(todos)
            print(f"  {stop_modo:<10}{saida_modo:<8}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")

if __name__=="__main__":
    main()
