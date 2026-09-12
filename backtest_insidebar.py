#!/usr/bin/env python3
"""
Backtest do TradeDesk Insidebar sobre dados historicos reais.
Regras (iguais ao scanner):
  - setup completo no dia D (inside bar) via avaliar_em();
  - entrada no dia D+1 SE Close[D+1] > High[IB] (rompimento por fechamento);
    entrada = Close[D+1]; stop = ultimo pivo 3x3 ate D+1.
  - Estrategia de saida DEFINITIVA: 50% em 2R (e move o stop p/ breakeven) +
    50% restante ate 3R. R do trade = media ponderada das duas metades.
  - (antes: acompanha se Low<=stop / High>=alvo, o 1o que
    ocorrer. Se o candle toca AMBOS no mesmo dia, assume o pior (stop) —
    conservador.
Saida: estatisticas por ativo e agregadas (trades, win rate, expectancia em R).
"""
import os, glob, sys
import numpy as np, pandas as pd
import insidebar_engine as ib

def carrega(path):
    d=pd.read_csv(path, parse_dates=["date"]).set_index("date")
    d=d.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})
    return d[["Open","High","Low","Close","Volume"]].dropna()

def backtest_ativo(d, tk, max_hold=60, alvo_R=3.0):
    """Retorna lista de trades. max_hold: dias maximos segurando (safety)."""
    o,h,l,c = d["Open"],d["High"],d["Low"],d["Close"]
    base=ib._series_base(d)
    n=len(d); trades=[]
    minbar=max(ib.EMA_LEN, ib.ATR_SLOW, ib.CONS_MAX)+2*ib.SWING_K+2
    D=minbar
    while D < n-1:
        r=ib.avaliar_em(d, D, base=base)
        if r.get("ok"):
            ib_high=r["ib_high"]
            # dia seguinte: rompimento por fechamento?
            nx=D+1
            if nx < n and float(c.iloc[nx]) > ib_high:
                entry=float(c.iloc[nx])
                # stop: ultimo pivo 3x3 ate nx
                _, ll = ib._swings(h.iloc[:nx+1], l.iloc[:nx+1], ib.SWING_K)
                stop = float(l.iloc[ll[-1]]) if ll else float(r["ib_low"])
                risk = entry-stop
                if risk<=0:
                    D=nx+1; continue
                # ESTRATEGIA DEFINITIVA: 50% em 2R (move stop p/ breakeven) +
                # 50% restante ate alvo_R (3R). R do trade = media das 2 metades.
                alvo1 = entry + 2*risk          # parcial: 50% em 2R
                alvo2 = entry + alvo_R*risk     # restante: ate 3R (alvo_R)
                p1=None; p2=None; st=stop; saida=None
                for j in range(nx+1, min(nx+1+max_hold, n)):
                    lo=float(l.iloc[j]); hi=float(h.iloc[j])
                    if p1 is None:
                        if lo<=st: p1=-1.0; p2=-1.0; saida=d.index[j]; break  # stop antes de 2R
                        if hi>=alvo1: p1=2.0; st=entry                        # realizou 2R, stop->BE
                    if p1 is not None and p2 is None:
                        if lo<=st: p2=0.0 if st==entry else -1.0; saida=d.index[j]; break  # BE=0
                        if hi>=alvo2: p2=alvo_R; saida=d.index[j]; break
                if p1 is None:      # nada aconteceu no horizonte
                    lastc=float(c.iloc[min(nx+max_hold, n-1)])
                    fim=(lastc-entry)/risk; p1=fim; p2=fim; saida=d.index[min(nx+max_hold, n-1)]
                elif p2 is None:    # 1a metade saiu em 2R, 2a nao resolveu
                    lastc=float(c.iloc[min(nx+max_hold, n-1)])
                    p2=(lastc-entry)/risk; saida=d.index[min(nx+max_hold, n-1)]
                res = 0.5*p1 + 0.5*p2   # R ponderado das duas metades
                trades.append({"ticker":tk,"entrada_data":str(d.index[nx].date()),
                    "entry":round(entry,2),"stop":round(stop,2),
                    "parcial2r":round(alvo1,2),"alvo3r":round(alvo2,2),
                    "saida_data":str(saida.date()),"R":round(res,2)})
                D=nx+1; continue
        D+=1
    return trades

def main():
    price_dir=sys.argv[1] if len(sys.argv)>1 else "prices"
    alvo_R=float(sys.argv[2]) if len(sys.argv)>2 else 3.0
    arqs=sorted(glob.glob(os.path.join(price_dir,"*.csv")))
    todos=[]
    print(f"Backtest Insidebar | {len(arqs)} ativos | alvo {alvo_R}R\n")
    for a in arqs:
        tk=os.path.basename(a).replace(".csv","").upper()
        try:
            d=carrega(a)
            if len(d)<150: continue
            t=backtest_ativo(d, tk, alvo_R=alvo_R)
            todos+=t
            if t:
                wr=100*sum(1 for x in t if x["R"]>0)/len(t)
                exp=sum(x["R"] for x in t)/len(t)
                print(f"  {tk:<8} {len(t):>3} trades | win {wr:4.0f}% | expect {exp:+.2f}R")
        except Exception as e:
            print(f"  {tk}: erro {str(e)[:40]}")
    # agregado
    print("\n"+"="*56)
    if todos:
        N=len(todos); wins=sum(1 for x in todos if x["R"]>0)
        wr=100*wins/N; somaR=sum(x["R"] for x in todos); exp=somaR/N
        print(f"  TOTAL: {N} trades")
        print(f"  Win rate: {wr:.1f}% ({wins} ganhos / {N-wins} perdas)")
        print(f"  Expectancia: {exp:+.3f}R por trade")
        print(f"  Resultado acumulado: {somaR:+.1f}R")
        # salva CSV dos trades
        pd.DataFrame(todos).to_csv("trades_insidebar.csv", index=False)
        print(f"  (detalhe salvo em trades_insidebar.csv)")
    else:
        print("  Nenhum trade gerado.")
    print("="*56)
    return todos

if __name__=="__main__":
    main()
