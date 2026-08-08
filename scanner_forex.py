#!/usr/bin/env python3
"""
SCANNER FOREX & COMMODITIES — DIDI+ADX+BB no diario.
Roda sobre os 20 pares de moedas (majores + minores) e os 20 ETFs de
commodity (metais, energia, agricolas, cestas). Gera painel_forex.json.

Liquidez: pares de Forex NAO passam pelo filtro (mercado descentralizado,
volume do Yahoo nao e confiavel); ETFs de commodity passam normalmente
(tem volume real em bolsa).

USO: python scanner_forex.py   |   python scanner_forex.py --timeframe 2h
"""
import argparse, datetime, json
import scanner as sc
import forex_universe as fx

SETUP="Agulhada"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days",type=int,default=None,help="candles a olhar (padrao: por timeframe)")
    ap.add_argument("--out",default="scanner_forex")
    ap.add_argument("--no-batch",dest="batch",action="store_false",help="download individual (lento)")
    ap.add_argument("--chunk",type=int,default=50,help="tamanho do lote no download")
    ap.add_argument("--timeframe",default="1d",choices=["1d","1wk","4h","2h","1h","15m","5m"],
                    help="timeframe do grafico (1d padrao)")
    a=ap.parse_args()
    tf=a.timeframe
    days = a.days if a.days is not None else sc.default_days_back(tf)
    sufxo = "" if tf=="1d" else f"_{tf}"
    pares = fx.get_pares()
    commod = fx.get_commodities()
    print(f"Scanner Forex & Commodities (DIDI+ADX+BB) | {len(pares)} pares + "
          f"{len(commod)} commodities | tf {tf} | ultimos {days} candle(s)\n")

    batch=getattr(a,"batch",True)
    print("  [Forex]")
    hits_fx = sc.scan(pares, days, batch=batch, chunk=a.chunk,
                      timeframe=tf, skip_liquidez=True)
    hits_fx_v = sc.scan(pares, days, batch=batch, chunk=a.chunk,
                        timeframe=tf, skip_liquidez=True, lado="venda")
    print("  [Commodities]")
    hits_cm = sc.scan(commod, days, batch=batch, chunk=a.chunk,
                      timeframe=tf, skip_liquidez=False)
    hits_cm_v = sc.scan(commod, days, batch=batch, chunk=a.chunk,
                        timeframe=tf, skip_liquidez=False, lado="venda")

    def enrich(hits):
        for h in hits:
            h["par"]=fx.nome_de(h["ticker"])
            h["classe"]="Forex" if fx.is_forex(h["ticker"]) else "Commodity"
        return hits

    hits_compra = enrich(hits_fx + hits_cm)
    hits_venda  = enrich(hits_fx_v + hits_cm_v)
    # dois paineis: compra (painel_forex.json) e venda (painel_forex_venda.json)
    sc.build_panel_data(hits_compra, out_path=f"painel_forex{sufxo}.json", timeframe=tf)
    sc.build_panel_data(hits_venda,  out_path=f"painel_forex_venda{sufxo}.json", timeframe=tf)
    hits = hits_compra  # p/ o resumo no terminal

    print("\n"+"="*60)
    if not hits: print("  Nenhum ativo disparou.")
    else:
        hits.sort(key=lambda h:(-(h.get("quality") or 0)))
        print(f"  {len(hits)} sinal(is):\n")
        for h in hits:
            st="EM FORMACAO" if h["forming"] else "fechado"
            cl=h.get("classe","")
            print(f"  {h['ticker']:<10}{fx.nome_de(h['ticker'])[:28]:<30}{cl:<10}{st:<12} "
                  f"q{h.get('quality','—'):>5}")
    print("="*60)

if __name__=="__main__":
    main()
