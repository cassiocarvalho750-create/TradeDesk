#!/usr/bin/env python3
"""Compara a parcial 1R+3R COM breakeven vs SEM breakeven (mantem stop no pivo).
Roda na pasta passada como argumento."""
import glob, sys
import backtest_insidebar as bt, otimizar_insidebar as ot, insidebar_engine as ib

def simula(preps, breakeven):
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
                    alvo1=entry+1*risk; alvo2=entry+3*risk
                    p1=None;p2=None;st=stop
                    for j in range(nx+1,min(nx+61,n)):
                        lo=float(l.iloc[j]);hi=float(h.iloc[j])
                        if p1 is None:
                            if lo<=st: p1=-1.0;p2=-1.0;break
                            if hi>=alvo1:
                                p1=1.0
                                if breakeven: st=entry   # sobe stop p/ BE
                                # se nao breakeven, st continua no pivo
                        if p1 is not None and p2 is None:
                            if lo<=st:
                                # 2a metade sai: BE=0 se st subiu, senao -1R (pivo)
                                p2=0.0 if st==entry else -1.0; break
                            if hi>=alvo2: p2=3.0; break
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
print(f"Cesta '{pasta}' | {len(preps)} ativos | parcial 50% 1R + 50% 3R\n")
print(f"  {'versao':<22}{'trades':>7}{'win':>7}{'exp':>9}{'acum':>8}")
for be,nome in [(True,"COM breakeven"),(False,"SEM breakeven (pivo)")]:
    N,wr,exp,acc=st(simula(preps,be))
    print(f"  {nome:<22}{N:>7}{wr:>6.0f}%{exp:>+8.3f}R{acc:>+7.0f}R")
