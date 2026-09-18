#!/usr/bin/env python3
"""
============================================================================
SCANNER DE ENTRADA — DIDI + ADX + BB (grafico diario)
============================================================================
Varre B3 + EUA e lista os ativos que disparam os 3 criterios de entrada
no ULTIMO candle disponivel.

- Se rodado apos o fechamento: o ultimo candle e o pregao fechado (CONFIRMADO).
- Se rodado durante o pregao: o ultimo candle ainda esta em formacao; o sinal
  e marcado como PROVISORIO (pode mudar ate o fechamento).

Criterios (iguais ao bt_engine):
  A) DIDI: MA3 cruzou a MA8 de baixo p/ cima (no candle ou no anterior)
  B) ADX(8,8): 1a inclinacao + DI+ > DI- + ADX >= 105% do DI-
  C) Bollinger(8,2): primeira expansao das bandas

USO:
  python scanner.py              # universo completo (B3 + EUA)
  python scanner.py --quick      # ~40 ativos (teste rapido)
  python scanner.py --market b3  # so B3
  python scanner.py --market us  # so EUA
  python scanner.py --days 3     # sinais nos ultimos 3 candles

Gera: scanner_resultado.html  e imprime no terminal.
============================================================================
"""
import argparse, datetime, time, csv
import numpy as np, pandas as pd
import bt_engine as bt
import humor_sp500 as hs  # [humor_sp500] painel injetado
import run_backtest_v2 as rb

def fetch_intraday_ok(ticker):
    """Busca dados diarios incluindo o candle de hoje (em formacao se for pregao)."""
    import yfinance as yf
    try:
        # period 1y, interval 1d -> inclui o candle do dia corrente quando ha pregao
        d = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
        if d is None or d.empty: return pd.DataFrame()
        d.columns = [c.capitalize() for c in d.columns]
        if d.index.tz is not None: d.index = d.index.tz_localize(None)
        return d
    except Exception:
        return pd.DataFrame()

def market_of(tk): return "B3" if tk.endswith(".SA") else "EUA"

def tv_symbol(tk):
    """Monta o simbolo do TradingView. B3 -> BMFBOVESPA:TICKER; EUA -> so o ticker
    (o TradingView resolve a bolsa sozinho quando recebe so o simbolo na URL de busca)."""
    if tk.endswith(".SA"):
        return "BMFBOVESPA:" + tk.replace(".SA","")
    return tk

def tv_url(tk):
    return "https://www.tradingview.com/chart/?symbol=" + tv_symbol(tk)

def fmt_mktcap(v):
    """Formata market cap em B (bilhoes) ou M (milhoes)."""
    if v is None or (isinstance(v,float) and (np.isnan(v) or v<=0)): return "—"
    if v >= 1e9:  return f"{v/1e9:.1f}B"
    if v >= 1e6:  return f"{v/1e6:.0f}M"
    return f"{v:.0f}"

def enrich_fundamentals(hits):
    """Busca P/E e Market Cap SOMENTE dos ativos que deram sinal (poucos),
    para nao pesar o scan inteiro. Falhas viram '—' sem quebrar o scan."""
    for h in hits:
        try:
            info = yf.Ticker(h["ticker"]).info
            pe = info.get("trailingPE") or info.get("forwardPE")
            mc = info.get("marketCap")
            h["pe"] = round(float(pe),1) if pe not in (None,0) else None
            h["mktcap"] = float(mc) if mc not in (None,0) else None
        except Exception:
            h["pe"] = None; h["mktcap"] = None
        time.sleep(0.05)
    return hits


def scan(tickers, days_back=1):
    """Retorna lista de sinais nos ultimos `days_back` candles."""
    hits=[]
    today = pd.Timestamp(datetime.date.today())
    for i,tk in enumerate(tickers,1):
        if i%50==1: print(f"  varrendo {i}/{len(tickers)}...")
        d = fetch_intraday_ok(tk)
        if len(d) < 60: continue
        try:
            s = bt.compute_signals_windowed(d, didi_window=5, adx_window=3)
        except Exception:
            continue
        # olha os ultimos days_back candles
        tail = s.iloc[-days_back:]
        for idx, row in tail.iterrows():
            if bool(row["signal_win"]):
                is_forming = (idx.normalize() == today)
                entry = row["Close"]; low = row["Low"]; r = entry - low
                r_pct = (r/entry*100) if entry>0 else 0
                pos = s.index.get_loc(idx)
                vol20 = s["Volume"].iloc[max(0,pos-19):pos+1].mean()
                px20  = s["Close"].iloc[max(0,pos-19):pos+1].mean()
                fin_vol = (vol20 * px20) / 1e6 if not np.isnan(vol20) else 0.0
                # volume financeiro DO DIA (preco de fechamento x volume do dia), em milhoes
                vol_dia_qtd = float(s["Volume"].iloc[pos])
                vol_dia_fin = (vol_dia_qtd * float(entry)) / 1e6 if not np.isnan(vol_dia_qtd) else 0.0
                didi_ago = adx_ago = None
                for k in range(0,6):
                    if pos-k>=0 and bool(s["didi_cross"].iloc[pos-k]): didi_ago=k; break
                for k in range(0,4):
                    if pos-k>=0 and bool(s["adx_event"].iloc[pos-k]): adx_ago=k; break
                hits.append({
                    "ticker": tk, "market": market_of(tk),
                    "date": idx.date(), "forming": is_forming,
                    "close": round(float(entry),2), "stop": round(float(low),2),
                    "r_pct": round(float(r_pct),2),
                    "adx": round(float(row.get("adx",np.nan)),1),
                    "didi_ago": didi_ago, "adx_ago": adx_ago,
                    "vol_fin_mi": round(float(fin_vol),1),
                    "vol_dia_mi": round(float(vol_dia_fin),1),
                    "pe": None, "mktcap": None,   # preenchidos depois, so p/ os que deram sinal
                })
        time.sleep(0.03)
    return hits

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--quick",action="store_true")
    ap.add_argument("--market",choices=["b3","us","all"],default="all")
    ap.add_argument("--days",type=int,default=1,help="quantos candles olhar p/ tras")
    ap.add_argument("--out",default="scanner_resultado.html")
    a=ap.parse_args()

    uni = rb.get_universe(quick=a.quick)
    if a.market=="b3": uni=[t for t in uni if t.endswith(".SA")]
    elif a.market=="us": uni=[t for t in uni if not t.endswith(".SA")]
    print(f"Scanner DIDI+ADX+BB | {len(uni)} ativos | ultimos {a.days} candle(s)\n")

    hits = scan(uni, a.days)
    hits.sort(key=lambda h:(not h["forming"], h["market"], h["ticker"]))

    print("\n"+"="*60)
    if not hits:
        print("  Nenhum ativo disparou os 3 criterios no periodo.")
    else:
        print(f"  {len(hits)} sinal(is) encontrado(s):\n")
        print(f"  {'ATIVO':<12}{'MERC':<5}{'DATA':<12}{'STATUS':<12}{'PRECO':>8}{'STOP':>8}{'R%':>6}{'VOL(Mi)':>9}{'DIDI':>6}{'ADX':>6}")
        for h in hits:
            st = "EM FORMACAO" if h["forming"] else "fechado"
            da = f"-{h['didi_ago']}d" if h['didi_ago'] is not None else "?"
            aa = f"-{h['adx_ago']}d" if h['adx_ago'] is not None else "?"
            print(f"  {h['ticker']:<12}{h['market']:<5}{str(h['date']):<12}{st:<12}"
                  f"{h['close']:>8}{h['stop']:>8}{h['r_pct']:>6}{h['vol_fin_mi']:>9}{da:>6}{aa:>6}")
    print(f"\n  Relatorio: {a.out}")
    print("="*60)

    # CSV para o TradeDesk Pro
    csv_path = a.out.replace(".html", ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f, delimiter=";")
        wr.writerow(["Ticker","Mercado","Data","Status","Preco","Stop",
                     "R_pct","Vol_Financeiro_Mi","DIDI_dias","ADX_dias"])
        for h in hits:
            wr.writerow([h["ticker"], h["market"], h["date"],
                         "em_formacao" if h["forming"] else "fechado",
                         f"{h['close']:.2f}".replace(".",","),
                         f"{h['stop']:.2f}".replace(".",","),
                         f"{h['r_pct']:.2f}".replace(".",","),
                         f"{h['vol_fin_mi']:.1f}".replace(".",","),
                         h["didi_ago"] if h["didi_ago"] is not None else "",
                         h["adx_ago"] if h["adx_ago"] is not None else ""])
    print(f"  CSV: {csv_path}")

    # HTML
    rows=""
    for h in hits:
        forming = h["forming"]
        badge = ("<span style='background:#f9a825;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px'>em formação</span>"
                 if forming else
                 "<span style='background:#2E7D4F;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px'>fechado</span>")
        da = f"há {h['didi_ago']}d" if h['didi_ago'] is not None else "—"
        aa = f"há {h['adx_ago']}d" if h['adx_ago'] is not None else "—"
        rows+=(f"<tr><td style='font-weight:600'>{h['ticker'].replace('.SA','')}</td>"
               f"<td>{h['market']}</td><td>{h['date']}</td><td>{badge}</td>"
               f"<td style='text-align:right'>{h['close']}</td>"
               f"<td style='text-align:right'>{h['stop']}</td>"
               f"<td style='text-align:right'>{h['r_pct']}%</td>"
               f"<td style='text-align:right'>{h['vol_fin_mi']}</td>"
               f"<td style='text-align:right'>{da}</td>"
               f"<td style='text-align:right'>{aa}</td></tr>")
    today=datetime.date.today().strftime("%Y-%m-%d")
    n=len(hits)
    html=f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scanner DIDI+ADX+BB</title>
    <style>body{{font-family:'Segoe UI',Arial;max-width:820px;margin:auto;padding:28px;color:#222}}
    h2{{color:#1A4731;border-bottom:3px solid #2E7D4F;padding-bottom:10px}}
    table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}
    th{{background:#1A4731;color:#fff;padding:9px;text-align:right}}th:first-child,th:nth-child(2),th:nth-child(3),th:nth-child(4){{text-align:left}}
    td{{padding:8px 9px;border-bottom:1px solid #eee}} tbody tr:hover{{background:#f5f9f6}}</style></head><body>
    <h2>Scanner de entrada — DIDI + ADX + BB</h2>
    <p style="font-size:13px;color:#666">{n} sinal(is) · gerado em {today} · grafico diario.
    <b>Em formação</b> = candle de hoje ainda mexendo (pode mudar até o fechamento). <b>Fechado</b> = pregão já encerrado.</p>
    <table><thead><tr><th>Ativo</th><th>Mercado</th><th>Data</th><th>Status</th>
    <th>Preço</th><th>Stop (mín.)</th><th>R%</th><th>Vol R$Mi</th><th>DIDI</th><th>ADX</th></tr></thead><tbody>{rows}</tbody></table>
    <p style="font-size:12px;color:#888;margin-top:16px">Stop = mínima do candle de sinal. R% = distância do preço ao stop, em % (quanto menor, mais colado o stop).
    Os sinais "em formação" devem ser reconfirmados no fechamento do pregão.</p>
    <p style="font-size:11px;color:#aaa">Sinais técnicos para análise própria. Não é recomendação de investimento.</p></body></html>"""
    html = html.replace("<body>", "<body>"+hs.painel_html(), 1)  # [humor_sp500] painel injetado
    open(a.out,"w",encoding="utf-8").write(html)

if __name__=="__main__":
    main()
