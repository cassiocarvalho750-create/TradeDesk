#!/usr/bin/env python3
"""
Otimizador do Insidebar (versao rapida): pre-calcula swings uma vez por ativo.
Varia UM parametro por vez para ver o efeito isolado (evita overfitting de
testar 243 combinacoes). Uso: python otimizar_insidebar.py prices
"""
import os, glob, sys
import numpy as np, pandas as pd
import insidebar_engine as ib
import backtest_insidebar as bt

def swings_all(h, l, k):
    """Todos os pivos (idx) confirmados, calculado UMA vez. Um pivo em i so fica
    'disponivel' a partir de i+k (precisa de k candles a direita)."""
    hv=h.values; lv=l.values; n=len(hv); hi=[]; lo=[]
    for i in range(k, n-k):
        if hv[i]==hv[i-k:i+k+1].max() and hv[i-k:i+k+1].argmax()==k: hi.append(i)
        if lv[i]==lv[i-k:i+k+1].min() and lv[i-k:i+k+1].argmin()==k: lo.append(i)
    return hi, lo

def prep(d):
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    ema=c.ewm(span=ib.EMA_LEN,adjust=False).mean()
    af=ib._atr(h,l,c,ib.ATR_FAST); asl=ib._atr(h,l,c,ib.ATR_SLOW)
    inside=(h<h.shift(1))&(l>l.shift(1))
    ib_ratio=(h-l)/(h.shift(1)-l.shift(1)).replace(0,np.nan)
    hi,lo=swings_all(h,l,ib.SWING_K)
    return dict(o=o,h=h,l=l,c=c,ema=ema,af=af,asl=asl,inside=inside,ibr=ib_ratio,
                hi=hi,lo=lo,n=len(d))

def estrutura_ok(P, pos, k):
    # estrutura de alta (nova): HighestHigh(recentes) > HighestHigh(anteriores)
    LB=ib.ESTRUT_LB
    if pos < 2*LB: return False
    h=P["h"]
    return bool(h.iloc[pos-LB:pos].max() > h.iloc[pos-2*LB:pos-LB].max())

def stop_pivo(P, pos, k):
    ll=[i for i in P["lo"] if i+k<=pos]
    return float(P["l"].iloc[ll[-1]]) if ll else None

def avaliar(P, pos):
    if pos < max(ib.EMA_LEN,ib.ATR_SLOW,ib.CONS_MAX)+2*ib.SWING_K+2: return None
    if not bool(P["inside"].iloc[pos]): return None
    h,l,c,ema,af,asl,ibr=P["h"],P["l"],P["c"],P["ema"],P["af"],P["asl"],P["ibr"]
    atr20=float(asl.iloc[pos])
    achou=False
    for L in range(ib.CONS_MIN,ib.CONS_MAX+1):
        ini=pos-L
        if ini<0: break
        jh=h.iloc[ini:pos]; jl=l.iloc[ini:pos]; je=ema.iloc[ini:pos]
        if len(jh)<L: break
        c1=(atr20>0) and ((jh.max()-jl.min())/atr20 < ib.CONS_AMPL_ATR)
        c2=bool((jl.values>=(je.values*ib.CONS_PEN_EMA)).all())
        if c1 and c2: achou=True; break
    if not achou: return None
    if not estrutura_ok(P,pos,ib.SWING_K): return None
    if not (c.iloc[pos]>ema.iloc[pos]): return None
    if not (ema.iloc[pos]>ema.iloc[pos-ib.EMA_SLOPE_LB]): return None
    if not ((c.iloc[pos]-ema.iloc[pos])/ema.iloc[pos] < ib.ESTICADO_MAX): return None
    if not (l.iloc[pos]<=ema.iloc[pos]*(1+ib.IB_PERTO_EMA)): return None
    if not ((af.iloc[pos]/asl.iloc[pos]) < ib.ATR_CONTR_MAX): return None
    if not (ibr.iloc[pos] < ib.IB_COMPRESS): return None
    return float(h.iloc[pos])   # ib_high

def roda(preps, alvo_R=2.0):
    todos=[]
    for P in preps:
        h,l,c=P["h"],P["l"],P["c"]; n=P["n"]
        D=max(ib.EMA_LEN,ib.ATR_SLOW,ib.CONS_MAX)+2*ib.SWING_K+2
        while D<n-1:
            ibh=avaliar(P,D)
            if ibh is not None:
                nx=D+1
                if nx<n and float(c.iloc[nx])>ibh:
                    entry=float(c.iloc[nx]); sp=stop_pivo(P,nx,ib.SWING_K)
                    stop=sp if sp is not None else float(l.iloc[D])
                    risk=entry-stop
                    if risk>0:
                        alvo=entry+alvo_R*risk; res=None
                        for j in range(nx+1,min(nx+61,n)):
                            if float(l.iloc[j])<=stop: res=-1.0; break
                            if float(h.iloc[j])>=alvo: res=alvo_R; break
                        if res is None: res=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        todos.append(res)
                    D=nx+1; continue
            D+=1
    return todos

def stats(rs):
    if not rs: return (0,0,0,0)
    N=len(rs); return (N,100*sum(1 for x in rs if x>0)/N,sum(rs)/N,sum(rs))

def main():
    pd_=sys.argv[1] if len(sys.argv)>1 else "prices"
    preps=[]
    for a in sorted(glob.glob(os.path.join(pd_,"*.csv"))):
        try:
            d=bt.carrega(a)
            if len(d)>=150: preps.append(prep(d))
        except: pass
    print(f"Otimizador Insidebar | {len(preps)} ativos\n")
    N,wr,exp,acc=stats(roda(preps,2.0))
    print(f"BASELINE: {N} trades | win {wr:.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R")
    print(f"  compress<{ib.IB_COMPRESS} contr<{ib.ATR_CONTR_MAX} ampl<{ib.CONS_AMPL_ATR} estic<{ib.ESTICADO_MAX}\n")
    def varre(nome,attr,vals):
        print(f"--- {nome} ---"); orig=getattr(ib,attr)
        for v in vals:
            setattr(ib,attr,v)
            # recalcula swings so se mudou SWING_K (nao e o caso aqui)
            N,wr,exp,acc=stats(roda(preps,2.0))
            print(f"  {nome}={v:<5} {N:>3}t win{wr:4.0f}% exp{exp:+.3f}R acum{acc:+.0f}R"+(" <<" if abs(v-orig)<1e-9 else ""))
        setattr(ib,attr,orig); print()
    varre("compress","IB_COMPRESS",[0.60,0.70,0.80])
    varre("contracao","ATR_CONTR_MAX",[0.85,0.90,0.95])
    varre("amplitude","CONS_AMPL_ATR",[2.0,2.5,3.0])
    varre("nao_estic","ESTICADO_MAX",[0.05,0.08,0.10])
    print("--- ALVO ---")
    for aR in [1.5,2.0,2.5,3.0]:
        N,wr,exp,acc=stats(roda(preps,aR))
        print(f"  alvo={aR}R {N:>3}t win{wr:4.0f}% exp{exp:+.3f}R acum{acc:+.0f}R")

if __name__=="__main__": main()
