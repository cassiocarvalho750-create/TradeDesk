#!/usr/bin/env python3
"""
Backtest do TradeDesk Insidebar sobre dados historicos reais.
Regras (iguais ao scanner):
  - setup completo no dia D (inside bar) via avaliar_em();
  - entrada no dia D+1 SE Close[D+1] > High[IB] (rompimento por fechamento);
    entrada = Close[D+1]; stop = ultimo pivo 3x3 ate D+1; alvo = 2R.
  - acompanha D+2..fim: se Low<=stop -> -1R; se High>=alvo -> +2R; o 1o que
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
                alvo = entry + alvo_R*risk
                # acompanha a partir de nx+1
                res=None; saida=None
                for j in range(nx+1, min(nx+1+max_hold, n)):
                    lo=float(l.iloc[j]); hi=float(h.iloc[j])
                    bateu_stop = lo<=stop
                    bateu_alvo = hi>=alvo
                    if bateu_stop and bateu_alvo:
                        res=-1.0; saida=d.index[j]; break   # conservador: pior caso
                    if bateu_stop:
                        res=-1.0; saida=d.index[j]; break
                    if bateu_alvo:
                        res=alvo_R; saida=d.index[j]; break
                if res is None:
                    # nao bateu nem stop nem alvo dentro de max_hold: fecha no ultimo close
                    lastc=float(c.iloc[min(nx+max_hold, n-1)])
                    res=(lastc-entry)/risk; saida=d.index[min(nx+max_hold, n-1)]
                trades.append({"ticker":tk,"entrada_data":str(d.index[nx].date()),
                    "entry":round(entry,2),"stop":round(stop,2),"alvo":round(alvo,2),
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
