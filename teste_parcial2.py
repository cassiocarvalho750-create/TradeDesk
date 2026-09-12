#!/usr/bin/env python3
"""Compara saidas: puras (1R,2R,3R) vs parciais (50% em 1R + 50% em 2R/3R,
com breakeven apos a 1a parcial). Roda na pasta passada como argumento."""
import glob, sys
import backtest_insidebar as bt, otimizar_insidebar as ot, insidebar_engine as ib

def simula(preps, modo):
    """modo: 'puro1','puro2','puro3','parc2','parc3'"""
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
                    if modo.startswith("puro"):
                        aR=float(modo[-1]); alvo=entry+aR*risk; r=None
                        for j in range(nx+1,min(nx+61,n)):
                            if float(l.iloc[j])<=stop: r=-1.0; break
                            if float(h.iloc[j])>=alvo: r=aR; break
                        if r is None: r=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        res.append(r)
                    else:
                        aR2=2.0 if modo=="parc2" else 3.0
                        alvo1=entry+1*risk; alvo2=entry+aR2*risk
                        p1=None;p2=None;st=stop
                        for j in range(nx+1,min(nx+61,n)):
                            lo=float(l.iloc[j]);hi=float(h.iloc[j])
                            if p1 is None:
                                if lo<=st: p1=-1.0;p2=-1.0;break
                                if hi>=alvo1: p1=1.0; st=entry
                            if p1 is not None and p2 is None:
                                if lo<=st: p2=0.0 if st==entry else -1.0; break
                                if hi>=alvo2: p2=aR2; break
                        if p1 is None:
                            fim=(float(c.iloc[min(nx+60,n-1)])-entry)/risk; p1=fim;p2=fim
                        elif p2 is None:
                            p2=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        res.append(0.5*p1+0.5*p2)
                    D=nx+1; continue
            D+=1
    return res

def st(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

pasta=sys.argv[1] if len(sys.argv)>1 else "prices"
preps=[ot.prep(bt.carrega(a)) for a in sorted(glob.glob(f"{pasta}/*.csv"))]
print(f"Cesta '{pasta}' | {len(preps)} ativos\n")
print(f"  {'saida':<16}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
nomes=[("puro1","1R integral"),("puro2","2R integral"),("puro3","3R integral"),
       ("parc2","50%1R+50%2R"),("parc3","50%1R+50%3R")]
for modo,nome in nomes:
    N,wr,exp,acc=st(simula(preps,modo))
    print(f"  {nome:<16}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")
