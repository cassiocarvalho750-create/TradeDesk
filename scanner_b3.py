#!/usr/bin/env python3
"""
SCANNER B3 — DIDI+ADX+BB (janelas, gatilho na BB) — exporta p/ TradeDesk Pro BRL
Gera JSON no formato do TradeDesk_Pro_v11_BRL (campos data,s,setup,q,pc,ps,tgt).
USO: python scanner_b3.py    |    python scanner_b3.py --quick
"""
import argparse, datetime, time, json
import numpy as np, pandas as pd
import bt_engine as bt
import run_backtest_v2 as rb
import scanner as sc   # reusa fetch_intraday_ok e scan

MARKET="b3"; SETUP="Agulhada"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--quick",action="store_true")
    ap.add_argument("--days",type=int,default=None,help="candles a olhar (padrao: por timeframe)")
    ap.add_argument("--out",default="scanner_b3")
    ap.add_argument("--no-batch",dest="batch",action="store_false",help="download individual (lento)")
    ap.add_argument("--chunk",type=int,default=100,help="tamanho do lote no download")
    ap.add_argument("--timeframe",default="1d",choices=["1d","1wk","2h","1h","15m","5m"],
                    help="timeframe do grafico (1d padrao)")
    a=ap.parse_args()
    uni=[t for t in rb.get_universe(quick=a.quick) if t.endswith(".SA")]
    tf=a.timeframe
    days = a.days if a.days is not None else sc.default_days_back(tf)
    sufxo = "" if tf=="1d" else f"_{tf}"
    if a.out=="scanner_b3": a.out=f"scanner_b3{sufxo}"
    print(f"Scanner B3 (DIDI+ADX+BB, gatilho BB) | {len(uni)} ativos | tf {tf} | ultimos {days} candle(s)\n")
    hits=sc.scan(uni, days, batch=getattr(a,"batch",True), chunk=a.chunk, timeframe=tf)
    if hits:
        print(f"  buscando P/E e Market Cap de {len(hits)} ativo(s) com sinal...")
        sc.enrich_fundamentals(hits)
    # SEMPRE gera o painel (mesmo com 0 sinais), para o arquivo refletir o scan
    # mais recente e nao ficar com dados antigos de um scan anterior.
    sc.build_panel_data(hits, out_path=f"painel_b3{sufxo}.json", timeframe=tf)
    hits.sort(key=lambda h:(not h["forming"], h["ticker"]))

    # terminal
    print("\n"+"="*60)
    if not hits: print("  Nenhum ativo disparou.")
    else:
        print(f"  {len(hits)} sinal(is):\n")
        for h in hits:
            st="EM FORMACAO" if h["forming"] else "fechado"
            print(f"  {h['ticker'].replace('.SA',''):<10}{st:<12} preco {h['close']:>8} stop {h['stop']:>8} "
                  f"R% {h['r_pct']:>5} vol {h['vol_fin_mi']:>7}Mi  DIDI -{h['didi_ago']}d ADX -{h['adx_ago']}d")


    # ---- relatorio HTML ----
    today=datetime.date.today().strftime("%Y-%m-%d")
    rows=""
    for h in hits:
        badge = ("<span style='background:#f9a825;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px'>em formação</span>"
                 if h["forming"] else
                 "<span style='background:#2E7D4F;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px'>fechado</span>")
        da = f"há {h['didi_ago']}d" if h['didi_ago'] is not None else "—"
        aa = f"há {h['adx_ago']}d" if h['adx_ago'] is not None else "—"
        tk_disp = h["ticker"].replace(".SA","")
        tv = sc.tv_url(h["ticker"])
        pe_disp = h.get("pe") if h.get("pe") is not None else "—"
        mc_disp = sc.fmt_mktcap(h.get("mktcap"))
        rows+=(f"<tr><td style='font-weight:600'><a href='{tv}' target='_blank' style='color:#1A4731;text-decoration:none;border-bottom:1px dotted #1A4731'>{tk_disp} ↗</a></td><td>{h['date']}</td><td>{badge}</td>"
               f"<td style='text-align:right'>{h['close']}</td><td style='text-align:right'>{h['stop']}</td>"
               f"<td style='text-align:right'>{h['r_pct']}%</td><td style='text-align:right'>{h['vol_fin_mi']}</td>"
               f"<td style='text-align:right'>{h.get('vol_dia_mi','—')}</td>"
               f"<td style='text-align:right'>{pe_disp}</td><td style='text-align:right'>{mc_disp}</td>"
               f"<td style='text-align:right'>{da}</td><td style='text-align:right'>{aa}</td></tr>")
    n=len(hits)
    html=f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scanner B3</title>
    <style>body{{{{font-family:'Segoe UI',Arial;max-width:860px;margin:auto;padding:28px;color:#222}}}}
    h2{{{{color:#1A4731;border-bottom:3px solid #2E7D4F;padding-bottom:10px}}}}
    table{{{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}}}
    th{{{{background:#1A4731;color:#fff;padding:9px;text-align:right}}}}th:first-child,th:nth-child(2),th:nth-child(3){{{{text-align:left}}}}
    td{{{{padding:8px 9px;border-bottom:1px solid #eee}}}} tbody tr:hover{{{{background:#f5f9f6}}}}</style></head><body>
    <h2>Scanner B3 — DIDI + ADX + BB</h2>
    <p style="font-size:13px;color:#666">{n} sinal(is) · gerado em {today} · gatilho na BB (DIDI até 5d, ADX até 3d).
    <b>Em formação</b> = candle de hoje ainda mexendo. <b>Fechado</b> = pregão encerrado.</p>
    <table><thead><tr><th>Ativo</th><th>Data</th><th>Status</th><th>Preço</th><th>Stop</th><th>R%</th><th>Vol méd (Mi)</th><th>Vol dia (Mi)</th><th>P/E</th><th>Mkt Cap</th><th>DIDI</th><th>ADX</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan=12 style=text-align:center;color:#888;padding:20px>Nenhum ativo disparou os critérios.</td></tr>'}</tbody></table>
    <p style="font-size:12px;color:#888;margin-top:14px">Sinais técnicos para análise própria. Confira contexto, liquidez (volume) e R% antes de operar. Não é recomendação.</p>
    </body></html>"""
    hpath=a.out+".html"
    open(hpath,"w",encoding="utf-8").write(html)
    print(f"  HTML: {hpath}")

    # JSON p/ TradeDesk BRL: alvo = entrada + 2R (2x risco)
    trades=[]
    for h in hits:
        risco=h["close"]-h["stop"]
        alvo=round(h["close"]+2*risco,2) if risco>0 else ""
        trades.append({
            "data": today, "s": h["ticker"].replace(".SA",""), "setup": SETUP,
            "q": "", "pc": str(h["close"]),
            "pa": "", "pv": "", "dv": "",
            "ps": str(h["stop"]),
            "tgt": str(alvo),
            "clE": "", "exitR": "", "pe": "", "img1": "", "img2": "",
        })
    payload={"trades":trades}
    jpath=a.out+"_tradedesk_BRL.json"
    open(jpath,"w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
    print(f"\n  JSON p/ TradeDesk BRL: {jpath}")
    print(f"  ATENCAO: importar este JSON SUBSTITUI os trades do TradeDesk.")
    print(f"  Veja as instrucoes de importacao segura no terminal/relatorio.")
    print("="*60)

if __name__=="__main__":
    main()
