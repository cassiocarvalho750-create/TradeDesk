#!/usr/bin/env python3
"""Compara estrategias de saida no backtest do Insidebar:
  A) tudo em 3R (atual)
  B) tudo em 2R
  C) parcial: 50% em 1R, 50% em 3R, stop do restante vai a breakeven apos 1R
Resultado por trade em R (ja ponderado pelo tamanho de cada metade)."""
import glob, numpy as np
import backtest_insidebar as bt, otimizar_insidebar as ot, insidebar_engine as ib

def simula(preps, modo):
    res=[]
    for P in preps:
        h,l,c=P["h"],P["l"],P["c"]; n=P["n"]
        D=max(ib.EMA_LEN,ib.ATR_SLOW,ib.CONS_MAX)+2*ib.SWING_K+2
        while D<n-1:
            ibh=ot.avaliar(P,D)
            if ibh is not None:
                nx=D+1
                if nx<n and float(c.iloc[nx])>ibh:
                    entry=float(c.iloc[nx]); sp=ot.stop_pivo(P,nx,ib.SWING_K)
                    stop=sp if sp is not None else float(l.iloc[D]); risk=entry-stop
                    if risk<=0: D=nx+1; continue
                    if modo in ("3R","2R"):
                        alvoR=3.0 if modo=="3R" else 2.0
                        alvo=entry+alvoR*risk; r=None
                        for j in range(nx+1,min(nx+61,n)):
                            if float(l.iloc[j])<=stop: r=-1.0; break
                            if float(h.iloc[j])>=alvo: r=alvoR; break
                        if r is None: r=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        res.append(r)
                    else:  # parcial 50% em 1R + 50% em 3R, breakeven apos 1R
                        alvo1=entry+1*risk; alvo2=entry+3*risk
                        parte1=None; parte2=None; st=stop
                        for j in range(nx+1,min(nx+61,n)):
                            lo=float(l.iloc[j]); hi=float(h.iloc[j])
                            # se ainda nao saiu a 1a parte
                            if parte1 is None:
                                if lo<=st: parte1=-1.0; parte2=-1.0; break  # bateu stop antes de 1R
                                if hi>=alvo1: parte1=1.0; st=entry  # realizou 1R, sobe stop p/ BE
                            # 2a parte (so avaliada depois que a 1a saiu)
                            if parte1 is not None and parte2 is None:
                                if lo<=st: parte2=0.0 if st==entry else -1.0; break  # BE=0
                                if hi>=alvo2: parte2=3.0; break
                        if parte1 is None:  # nada aconteceu no horizonte
                            fim=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                            parte1=fim; parte2=fim
                        elif parte2 is None:  # 1a saiu, 2a nao resolveu
                            parte2=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        res.append(0.5*parte1 + 0.5*parte2)   # media ponderada das metades
                    D=nx+1; continue
            D+=1
    return res

def st(rs):
    N=len(rs); w=sum(1 for x in rs if x>0)
    return N,100*w/N,sum(rs)/N,sum(rs)

preps=[ot.prep(bt.carrega(a)) for a in sorted(glob.glob("prices/*.csv"))]
print(f"{len(preps)} ativos\n")
for modo in ["2R","3R","parcial"]:
    N,wr,exp,acc=st(simula(preps,modo))
    print(f"  {modo:<8} {N:>3} trades | win {wr:4.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R")
