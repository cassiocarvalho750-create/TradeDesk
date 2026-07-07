#!/usr/bin/env python3
"""
SCANNER ETFs SETORIAIS (EUA) — DIDI+ADX+BB no diario.
Roda sobre os 42 ETFs setoriais/tematicos e gera painel_etf.json.
Nao aplica filtro de liquidez (ETFs setoriais sao liquidos) nem busca P/E.
USO: python scanner_etf.py   |   python scanner_etf.py --timeframe 2h
"""
import argparse, datetime, json
import scanner as sc
import etf_universe as eu

SETUP="Agulhada"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days",type=int,default=None,help="candles a olhar (padrao: por timeframe)")
    ap.add_argument("--out",default="scanner_etf")
    ap.add_argument("--no-batch",dest="batch",action="store_false",help="download individual (lento)")
    ap.add_argument("--chunk",type=int,default=50,help="tamanho do lote no download")
    ap.add_argument("--timeframe",default="1d",choices=["1d","2h","1h","15m","5m"],
                    help="timeframe do grafico (1d padrao)")
    a=ap.parse_args()
    uni=eu.get_etfs()
    tf=a.timeframe
    days = a.days if a.days is not None else sc.default_days_back(tf)
    sufxo = "" if tf=="1d" else f"_{tf}"
    print(f"Scanner ETFs Setoriais (DIDI+ADX+BB) | {len(uni)} ETFs | tf {tf} | ultimos {days} candle(s)\n")
    hits=sc.scan(uni, days, batch=getattr(a,"batch",True), chunk=a.chunk, timeframe=tf)
    # injeta o nome do setor em cada hit
    for h in hits:
        h["setor"]=eu.setor_de(h["ticker"])
    # SEMPRE gera o painel (mesmo com 0 sinais), p/ nao ficar com dados antigos.
    sc.build_panel_data(hits, out_path=f"painel_etf{sufxo}.json", timeframe=tf)

    # terminal
    print("\n"+"="*60)
    if not hits: print("  Nenhum ETF disparou.")
    else:
        hits.sort(key=lambda h:(-(h.get("quality") or 0)))
        print(f"  {len(hits)} sinal(is):\n")
        for h in hits:
            st="EM FORMACAO" if h["forming"] else "fechado"
            print(f"  {h['ticker']:<6}{eu.setor_de(h['ticker'])[:28]:<30}{st:<12} "
                  f"q{h.get('quality','—'):>5} preco {h['close']:>8} stop {h['stop']:>8}")
    print("="*60)

if __name__=="__main__":
    main()
