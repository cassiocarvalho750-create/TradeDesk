#!/usr/bin/env python3
"""
Analise de RISCO por trade: mostra lucro e drawdown (maior queda do pico) para
diferentes % de risco, sobre uma cesta de dados. Ajuda a escolher o risco/trade.

USO:
  python analise_risco.py <pasta> <alvoR> <capital>
  ex.: python analise_risco.py prices_teste 3 10000
"""
import glob, sys
import backtest_insidebar as bt

def main():
    pasta   = sys.argv[1] if len(sys.argv)>1 else "prices"
    alvo_R  = float(sys.argv[2]) if len(sys.argv)>2 else 3.0
    capital = float(sys.argv[3]) if len(sys.argv)>3 else 10000.0

    # coletar trades em ordem cronologica
    trades=[]
    for a in sorted(glob.glob(f"{pasta}/*.csv")):
        tk=a.split("/")[-1].split("\\")[-1].replace(".csv","").upper()
        try:
            d=bt.carrega(a)
            if len(d)<150: continue
            for x in bt.backtest_ativo(d, tk, alvo_R=alvo_R):
                trades.append((x["entrada_data"], x["R"]))
        except: pass
    trades.sort(key=lambda x:x[0])
    Rs=[r for _,r in trades]
    N=len(Rs); acumR=sum(Rs)
    wr=100*sum(1 for r in Rs if r>0)/N if N else 0

    def dd_max(Rs, vR):
        cap=0; pico=0; dd=0
        for r in Rs:
            cap+=r*vR; pico=max(pico,cap); dd=min(dd,cap-pico)
        return dd
    def pior_seq(Rs):
        s=0;m=0
        for r in Rs:
            if r<0: s+=1;m=max(m,s)
            else: s=0
        return m

    print(f"\nCesta '{pasta}' | alvo {alvo_R}R | capital R$ {capital:,.0f}")
    print(f"{N} trades | win {wr:.0f}% | acumulado {acumR:+.0f}R")
    print(f"maior sequencia de perdas seguidas: {pior_seq(Rs)} trades\n")
    print(f"  {'Risco':<8}{'1R':>8}{'Lucro':>13}{'%ganho':>9}{'Drawdown':>12}{'%capital':>10}")
    for risco in [0.005, 0.0075, 0.01]:
        vR=capital*risco; lucro=acumR*vR; dd=dd_max(Rs,vR)
        print(f"  {risco*100:>5.2f}%{vR:>8.0f}{lucro:>12,.0f}{lucro/capital*100:>8.0f}%{dd:>12,.0f}{dd/capital*100:>9.0f}%")
    print()

if __name__=="__main__":
    main()
