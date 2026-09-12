#!/usr/bin/env python3
"""
Exporta os R de cada trade de VARIAS estrategias para um unico CSV
(trades_montecarlo.csv), para alimentar o HTML de analise Monte Carlo.
Cada linha: estrategia, R.

Estrategias exportadas:
  - IB_1R, IB_2R, IB_3R          : Insidebar, alvo integral 1R/2R/3R
  - IB_parc2R                    : Insidebar, parcial 2R+BE (metade) + 3R
  - DIDI_pivo_TRIX              : Agulhada, stop pivo + parcial 2R + saida TRIX
  - DIDI_pivo_ADX              : Agulhada, stop pivo + saida kick ADX

USO: python exportar_trades.py <pasta>   (ex.: prices_teste)
"""
import glob, sys, os
import numpy as np, pandas as pd
import insidebar_engine as ib
import bt_engine as bt
import backtest_insidebar as bti

# ---------- Insidebar ----------
def ib_trades(d, alvo_R=None, parcial=False):
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    base=ib._series_base(d); n=len(d); out=[]
    D=max(ib.EMA_LEN,ib.ATR_SLOW,ib.CONS_MAX)+2*ib.SWING_K+2
    while D<n-1:
        r=ib.avaliar_em(d,D,base=base)
        if r.get("ok"):
            nx=D+1
            if nx<n and float(c.iloc[nx])>r["ib_high"]:
                entry=float(c.iloc[nx])
                _,ll=ib._swings(h.iloc[:nx+1],l.iloc[:nx+1],ib.SWING_K)
                stop=float(l.iloc[ll[-1]]) if ll else float(r["ib_low"]); risk=entry-stop
                if risk>0:
                    if parcial:
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
                        out.append(0.5*p1+0.5*p2)
                    else:
                        alvo=entry+alvo_R*risk; res=None
                        for j in range(nx+1,min(nx+61,n)):
                            if float(l.iloc[j])<=stop:res=-1.0;break
                            if float(h.iloc[j])>=alvo:res=alvo_R;break
                        if res is None:res=(float(c.iloc[min(nx+60,n-1)])-entry)/risk
                        out.append(res)
                D=nx+1;continue
        D+=1
    return out

# ---------- Agulhada (pivo + TRIX / ADX) ----------
def didi_trades(d, saida):
    import backtest_didi as bd
    return bd.backtest(d, "X", "pivo", saida)

def main():
    pasta=sys.argv[1] if len(sys.argv)>1 else "prices_teste"
    arqs=sorted(glob.glob(f"{pasta}/*.csv"))
    linhas=[]
    def add(nome, rs):
        for r in rs: linhas.append((nome, round(float(r),4)))
    print(f"Exportando trades de '{pasta}' ({len(arqs)} ativos)...")
    for a in arqs:
        try:
            d=bti.carrega(a)
            if len(d)<150: continue
            add("IB_1R", ib_trades(d, alvo_R=1.0))
            add("IB_2R", ib_trades(d, alvo_R=2.0))
            add("IB_3R", ib_trades(d, alvo_R=3.0))
            add("IB_parc2R", ib_trades(d, parcial=True))
            add("DIDI_pivo_TRIX", didi_trades(d, "trix"))
            add("DIDI_pivo_ADX",  didi_trades(d, "adx"))
        except Exception as e:
            print(f"  {os.path.basename(a)}: erro {str(e)[:40]}")
    df=pd.DataFrame(linhas, columns=["estrategia","R"])
    df.to_csv("trades_montecarlo.csv", index=False)
    print(f"\nSalvo: trades_montecarlo.csv ({len(df)} trades)")
    # resumo rapido
    for est in df["estrategia"].unique():
        r=df[df["estrategia"]==est]["R"]
        print(f"  {est:<16} {len(r):>5} trades | exp {r.mean():+.3f}R | win {100*(r>0).mean():.0f}%")

if __name__=="__main__":
    main()
