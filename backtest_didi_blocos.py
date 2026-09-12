#!/usr/bin/env python3
"""
Backtest da AGULHADA segmentado por BLOCOS do painel, cruzando:
  Eixo 1 (gatilho): 3+abertura | abertura | ADX hoje
  Eixo 2 (MME70):   acima+subindo | abaixo
Saida vencedora: stop pivo 3x3 + parcial 50% em 2R (BE) + resto sai no TRIX.
Mostra a expectancia de cada celula -> qual bloco vale mais.
Uso: python backtest_didi_blocos.py <pasta>
"""
import glob, sys, os
import numpy as np, pandas as pd
import bt_engine as bt
import backtest_didi as bd

EMA70=70; EMA70_LB=5

def swings_low(h,l,pos,k=3):
    lv=l.values
    cand=[i for i in range(k,pos-k+1) if lv[i]==lv[i-k:i+k+1].min() and lv[i-k:i+k+1].argmin()==k]
    return float(l.iloc[cand[-1]]) if cand else None

def classifica_gatilho(s, i, adx_win=3):
    """Retorna '3mais', 'abertura', 'adxhoje' ou None (atrasado/nao classificado)."""
    prim = bool(s["bb_primeira_abertura"].iloc[i])
    # didi_ago e adx_ago: quantos candles desde o evento
    didi0 = bool(s["didi_cross"].iloc[i]) if "didi_cross" in s.columns else False
    adx0  = bool(s["adx_event"].iloc[i]) if "adx_event" in s.columns else False
    conf = didi0 and adx0
    if conf and prim: return "3mais"
    if prim:          return "abertura"
    if adx0:          return "adxhoje"
    return None

def backtest(d, tk):
    s=bt.compute_signals_windowed(d)
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    ema70=c.ewm(span=EMA70,adjust=False).mean()
    trf,trs=bd.trix_ema(c)
    trix_venda=(trf<trs)&(trf.shift(1)>=trs.shift(1))
    n=len(d); res={}   # chave: "gatilho|mme" -> lista de R
    i=80
    while i<n-1:
        if not bool(s["signal_win"].iloc[i]): i+=1; continue
        gat=classifica_gatilho(s,i)
        if gat is None: i+=1; continue
        # MME70
        acima = float(c.iloc[i])>=float(ema70.iloc[i])
        subindo = float(ema70.iloc[i])>float(ema70.iloc[i-EMA70_LB])
        mme = "acima_sub" if (acima and subindo) else ("abaixo" if not acima else "acima_lat")
        # so classificamos nas 2 categorias pedidas: acima+subindo, e abaixo
        if mme=="acima_lat":  # acima mas nao subindo: agrupa em 'abaixo' p/ nao poluir? melhor ignorar
            i+=1; continue
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
        key=f"{gat}|{mme}"
        res.setdefault(key,[]).append(0.5*p1+0.5*p2)
        i=saiu+1
    return res

def st(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

def main():
    pasta=sys.argv[1] if len(sys.argv)>1 else "prices"
    arqs=sorted(glob.glob(f"{pasta}/*.csv"))
    agreg={}
    for a in arqs:
        try:
            d=bd.carrega(a)
            if len(d)<150: continue
            r=backtest(d, os.path.basename(a))
            for k,v in r.items(): agreg.setdefault(k,[]).extend(v)
        except Exception as e:
            pass
    print(f"Backtest AGULHADA por BLOCOS | cesta '{pasta}' | saida pivo+2R+TRIX\n")
    print(f"  {'bloco':<26}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
    ordem=["3mais|acima_sub","3mais|abaixo","abertura|acima_sub","abertura|abaixo",
           "adxhoje|acima_sub","adxhoje|abaixo"]
    nomes={"3mais|acima_sub":"3 JUNTOS+ab | MME70^",
           "3mais|abaixo":"3 JUNTOS+ab | abaixo",
           "abertura|acima_sub":"ABERTURA | MME70^",
           "abertura|abaixo":"ABERTURA | abaixo",
           "adxhoje|acima_sub":"ADX HOJE | MME70^",
           "adxhoje|abaixo":"ADX HOJE | abaixo"}
    linhas=[]
    for k in ordem:
        N,wr,exp,acc=st(agreg.get(k,[]))
        linhas.append((exp,k,N,wr,acc))
        print(f"  {nomes[k]:<26}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")
    # ranking por expectancia
    print(f"\n  RANKING por expectancia:")
    for exp,k,N,wr,acc in sorted(linhas,reverse=True):
        if N>0: print(f"    {nomes[k]:<26} exp {exp:+.3f}R ({N} trades)")

if __name__=="__main__":
    main()
