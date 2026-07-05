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
import run_backtest_v2 as rb

# --- timeframes ---
# yfinance nao tem '2h' nativo: baixamos '1h' e reamostramos para 2h.
# Mapa: timeframe -> (interval_yf, period_yf, regra_resample_ou_None)
TF_CONFIG = {
    "1d":  ("1d",  "1y",   None),
    "1h":  ("1h",  "730d", None),
    "2h":  ("1h",  "730d", "2h"),   # baixa 1h e reamostra p/ 2h
    "15m": ("15m", "60d",  None),
    "5m":  ("5m",  "60d",  None),
}

# quantos candles recentes olhar por timeframe (o gatilho e mais raro no intraday,
# entao ampliamos a janela para nao perder sinais do pregao corrente).
TF_DAYS_BACK = {"1d": 1, "2h": 2, "1h": 3, "15m": 4, "5m": 6}

def default_days_back(timeframe):
    return TF_DAYS_BACK.get(timeframe, 1)

def _resample_ohlcv(d, regra):
    """Reamostra OHLCV para um timeframe maior (ex.: 1h -> 2h)."""
    if d is None or d.empty:
        return d
    agg = {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
    cols = [c for c in agg if c in d.columns]
    r = d[cols].resample(regra, label="left", closed="left").agg({c:agg[c] for c in cols})
    return r.dropna(how="all")

def fetch_intraday_ok(ticker, timeframe="1d"):
    """Busca dados no timeframe pedido, incluindo o candle corrente (em formacao).
    Para 2h, baixa 1h e reamostra."""
    import yfinance as yf
    interval, period, regra = TF_CONFIG.get(timeframe, TF_CONFIG["1d"])
    try:
        d = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        if d is None or d.empty: return pd.DataFrame()
        d.columns = [c.capitalize() for c in d.columns]
        if d.index.tz is not None: d.index = d.index.tz_localize(None)
        if regra: d = _resample_ohlcv(d, regra)
        return d
    except Exception:
        return pd.DataFrame()

def fetch_batch(tickers, timeframe="1d", chunk=100, pause=1.0, retries=2):
    """Baixa varios tickers de uma vez com yf.download (group_by='ticker').
    Retorna dict {ticker: DataFrame} com colunas capitalizadas, indice sem tz.
    Para 2h, baixa 1h e reamostra cada ticker."""
    import yfinance as yf
    interval, period, regra = TF_CONFIG.get(timeframe, TF_CONFIG["1d"])
    out = {}
    n = len(tickers)
    for start in range(0, n, chunk):
        part = tickers[start:start+chunk]
        print(f"  baixando {start+1}-{min(start+chunk,n)}/{n}...")
        df = None
        for attempt in range(retries+1):
            try:
                df = yf.download(part, period=period, interval=interval,
                                 auto_adjust=True, group_by="ticker",
                                 threads=True, progress=False)
                if df is not None and not df.empty:
                    break
            except Exception:
                df = None
            time.sleep(pause*(attempt+1))
        if df is None or df.empty:
            continue
        # Caso 1 ticker: colunas simples (sem MultiIndex)
        if not isinstance(df.columns, pd.MultiIndex):
            d = df.copy()
            d.columns = [str(c).capitalize() for c in d.columns]
            if getattr(d.index,"tz",None) is not None: d.index = d.index.tz_localize(None)
            d = d.dropna(how="all")
            if regra and not d.empty: d = _resample_ohlcv(d, regra)
            if not d.empty: out[part[0]] = d
        else:
            for tk in part:
                if tk not in df.columns.get_level_values(0):
                    continue
                d = df[tk].copy()
                d.columns = [str(c).capitalize() for c in d.columns]
                if getattr(d.index,"tz",None) is not None: d.index = d.index.tz_localize(None)
                d = d.dropna(how="all")
                if regra and not d.empty: d = _resample_ohlcv(d, regra)
                if not d.empty: out[tk] = d
        time.sleep(pause)
    return out

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
    import yfinance as yf
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


def _liquidez_ok(tk, d, min_us_mi, min_b3_mi):
    """True se o ticker passa no piso de liquidez do seu mercado.
    US: piso em milhoes de USD. B3: piso em milhoes de BRL."""
    try:
        v20 = d["Volume"].tail(20).mean()
        p20 = d["Close"].tail(20).mean()
        vfin_mi = (v20 * p20) / 1e6
        if not np.isfinite(vfin_mi):
            return False
        piso = min_b3_mi if tk.endswith(".SA") else min_us_mi
        return bool(vfin_mi >= piso)
    except Exception:
        return False

def _evaluate(tk, d, days_back, today, timeframe="1d"):
    """Avalia UM ticker (DataFrame ja baixado) e retorna lista de hits.
    Logica identica para download em lote e individual."""
    res=[]
    if d is None or len(d) < 60:
        return res
    # garante colunas necessarias
    for col in ("Open","High","Low","Close","Volume"):
        if col not in d.columns:
            return res
    try:
        s = bt.compute_signals_windowed(d, didi_window=5, adx_window=3)
    except Exception:
        return res
    intraday = (timeframe != "1d")
    last_idx = s.index[-1]
    tail = s.iloc[-days_back:]
    for idx, row in tail.iterrows():
        if bool(row["signal_win"]):
            # no intraday, "em formacao" = ultimo candle (ainda nao fechou).
            # no diario, "em formacao" = candle de hoje.
            is_forming = (idx == last_idx) if intraday else (idx.normalize() == today)
            entry = row["Close"]; low = row["Low"]; r = entry - low
            r_pct = (r/entry*100) if entry>0 else 0
            pos = s.index.get_loc(idx)
            vol20 = s["Volume"].iloc[max(0,pos-19):pos+1].mean()
            px20  = s["Close"].iloc[max(0,pos-19):pos+1].mean()
            fin_vol = (vol20 * px20) / 1e6 if not np.isnan(vol20) else 0.0
            vol_dia_qtd = float(s["Volume"].iloc[pos])
            vol_dia_fin = (vol_dia_qtd * float(entry)) / 1e6 if not np.isnan(vol_dia_qtd) else 0.0
            didi_ago = adx_ago = None
            for k in range(0,6):
                if pos-k>=0 and bool(s["didi_cross"].iloc[pos-k]): didi_ago=k; break
            for k in range(0,4):
                if pos-k>=0 and bool(s["adx_event"].iloc[pos-k]): adx_ago=k; break

            # ---- QUALIDADE: compressao do Didi + sincronia dos gatilhos ----
            # Compressao: menor distancia entre a Didi curta (3/8) e longa (20/8)
            # nos candles em torno do gatilho. Quanto menor, melhor a agulhada.
            try:
                c = s["Close"]
                ma3 = c.rolling(3).mean(); ma8 = c.rolling(8).mean(); ma20 = c.rolling(20).mean()
                didi_curta = (ma3/ma8 - 1.0)*100.0
                didi_longa = (ma20/ma8 - 1.0)*100.0
                j0 = max(0, pos-4)
                dist = (didi_curta.iloc[j0:pos+1] - didi_longa.iloc[j0:pos+1]).abs()
                min_dist = float(dist.min()) if len(dist) else np.nan
            except Exception:
                min_dist = np.nan
            # nota de compressao (0-100): dist 0 -> 100 ; dist >= 2.0% -> 0
            if np.isnan(min_dist):
                q_comp = 0.0
            else:
                q_comp = max(0.0, min(100.0, (1.0 - min_dist/2.0)*100.0))
            # nota de sincronia (0-100): gatilhos no mesmo candle -> 100 ;
            # espalhados no limite das janelas (didi 5d, adx 3d) -> baixo.
            da = didi_ago if didi_ago is not None else 5
            aa = adx_ago if adx_ago is not None else 3
            q_sinc = max(0.0, 100.0 - (da/5.0*50.0) - (aa/3.0*50.0))
            # score final: 60% compressao + 40% sincronia
            quality = round(0.60*q_comp + 0.40*q_sinc, 1)

            res.append({
                "ticker": tk, "market": market_of(tk),
                "date": idx.date(), "forming": is_forming,
                "timeframe": timeframe,
                "candle_ts": str(idx),
                "close": round(float(entry),2), "stop": round(float(low),2),
                "r_pct": round(float(r_pct),2),
                "adx": round(float(row.get("adx",np.nan)),1),
                "didi_ago": didi_ago, "adx_ago": adx_ago,
                "vol_fin_mi": round(float(fin_vol),1),
                "vol_dia_mi": round(float(vol_dia_fin),1),
                "didi_dist": round(min_dist,3) if not np.isnan(min_dist) else None,
                "quality": quality,
                "pe": None, "mktcap": None,
            })
    return res


def scan(tickers, days_back=1, batch=True, chunk=100, timeframe="1d"):
    """Retorna lista de sinais nos ultimos `days_back` candles do timeframe dado.

    timeframe: '1d' (diario, padrao), '2h', '1h', '15m', '5m'.
    batch=True  -> download em LOTE via yf.download (rapido; recomendado p/ universo grande).
    batch=False -> download individual via fetch_intraday_ok (lento; fallback).
    O filtro de liquidez e aplicado a AMBOS os mercados, reusando o historico
    baixado (sem requisicao extra): US >= rb.US_MIN_VOL_FIN_MI (USD),
    B3 >= rb.B3_MIN_VOL_FIN_MI (BRL).
    """
    hits=[]
    today = pd.Timestamp(datetime.date.today())
    try:
        US_MIN = float(getattr(rb, "US_MIN_VOL_FIN_MI", 5.0))
    except Exception:
        US_MIN = 5.0
    try:
        B3_MIN = float(getattr(rb, "B3_MIN_VOL_FIN_MI", 5.0))
    except Exception:
        B3_MIN = 5.0

    if batch:
        data = fetch_batch(tickers, timeframe=timeframe, chunk=chunk)
        print(f"  baixados {len(data)}/{len(tickers)} (demais falharam/sem dados e foram pulados)")
        for tk in tickers:
            d = data.get(tk)
            if d is None:
                continue
            if not _liquidez_ok(tk, d, US_MIN, B3_MIN):
                continue
            hits.extend(_evaluate(tk, d, days_back, today, timeframe=timeframe))
    else:
        for i,tk in enumerate(tickers,1):
            if i%50==1: print(f"  varrendo {i}/{len(tickers)}...")
            d = fetch_intraday_ok(tk, timeframe=timeframe)
            if len(d) < 60:
                time.sleep(0.02); continue
            if not _liquidez_ok(tk, d, US_MIN, B3_MIN):
                time.sleep(0.01); continue
            hits.extend(_evaluate(tk, d, days_back, today, timeframe=timeframe))
            time.sleep(0.03)
    return hits


def build_panel_data(hits, n_bars=40, out_path="painel_didi.json", timeframe="1d"):
    """Para cada ativo com sinal, recalcula as series dos 3 indicadores
    (DIDI, ADX, BB) nos ultimos n_bars candles e grava um JSON que o painel
    HTML consome. Reusa fetch (individual) so para os POUCOS ativos com sinal.
    As formulas sao as mesmas do bt_engine (DIDI 3/8/20, ADX 8, BB 8,2)."""
    import json
    # horario de captura em Brasilia (UTC-3). O Actions roda em UTC, entao
    # convertemos explicitamente para nao sair 3h adiantado.
    tz_br = datetime.timezone(datetime.timedelta(hours=-3))
    captura = datetime.datetime.now(datetime.timezone.utc).astimezone(tz_br)
    captura_str = captura.strftime("%d/%m/%Y %H:%M")
    ativos = []
    intraday = (timeframe != "1d")
    for h in hits:
        tk = h["ticker"]
        d = fetch_intraday_ok(tk, timeframe=timeframe)
        if len(d) < 30:
            continue
        c = d["Close"]; hi = d["High"]; lo = d["Low"]
        ma3, ma8, ma20 = bt.sma(c,3), bt.sma(c,8), bt.sma(c,20)
        # Didi Index: curta (MA3/MA8) e longa (MA20/MA8), centradas em 0, em %
        didi_curta = (ma3/ma8 - 1.0)*100.0
        didi_longa = (ma20/ma8 - 1.0)*100.0
        adx, dip, dim = bt.calc_adx(hi, lo, c, period=8)
        # Bollinger 8,2
        m = bt.sma(c,8); sd = c.rolling(8).std()
        bb_sup = m + 2.0*sd; bb_inf = m - 2.0*sd
        def tail(s):
            return [None if (v is None or (isinstance(v,float) and np.isnan(v))) else round(float(v),4)
                    for v in s.tail(n_bars).tolist()]
        # rotulo do eixo: no intraday mostra data+hora; no diario so a data
        if intraday:
            dates = [x.strftime("%d/%m %H:%M") for x in c.tail(n_bars).index]
            ult_candle = c.index[-1].strftime("%d/%m %H:%M") if len(c) else None
        else:
            dates = [str(x.date()) for x in c.tail(n_bars).index]
            ult_candle = str(c.index[-1].date()) if len(c) else None
        ativos.append({
            "ticker": tk.replace(".SA",""), "market": h["market"],
            "close": h["close"], "stop": h["stop"], "r_pct": h["r_pct"],
            "forming": h["forming"], "date": str(h["date"]),
            "ult_candle": ult_candle, "timeframe": timeframe,
            "didi_ago": h["didi_ago"], "adx_ago": h["adx_ago"],
            "vol_fin_mi": h["vol_fin_mi"], "tv": tv_url(tk),
            "quality": h.get("quality"), "didi_dist": h.get("didi_dist"),
            "dates": dates,
            "price": tail(c),
            "didi_curta": tail(didi_curta), "didi_longa": tail(didi_longa),
            "adx": tail(adx), "dip": tail(dip), "dim": tail(dim),
            "bb_sup": tail(bb_sup), "bb_mid": tail(m), "bb_inf": tail(bb_inf),
        })
        time.sleep(0.05)
    # ordena por qualidade (melhores primeiro); em formacao/fechado nao afeta a ordem
    ativos.sort(key=lambda a: (a.get("quality") if a.get("quality") is not None else -1), reverse=True)
    payload = {"gerado": str(datetime.date.today()), "captura": captura_str,
               "timeframe": timeframe, "n": len(ativos), "ativos": ativos}
    open(out_path,"w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
    print(f"  Painel JSON: {out_path} ({len(ativos)} ativo(s))")
    return out_path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--quick",action="store_true")
    ap.add_argument("--market",choices=["b3","us","all"],default="all")
    ap.add_argument("--days",type=int,default=1,help="quantos candles olhar p/ tras")
    ap.add_argument("--out",default="scanner_resultado.html")
    ap.add_argument("--no-batch",dest="batch",action="store_false",help="download individual (lento)")
    ap.add_argument("--chunk",type=int,default=100,help="tamanho do lote no download")
    a=ap.parse_args()

    uni = rb.get_universe(quick=a.quick)
    if a.market=="b3": uni=[t for t in uni if t.endswith(".SA")]
    elif a.market=="us": uni=[t for t in uni if not t.endswith(".SA")]
    print(f"Scanner DIDI+ADX+BB | {len(uni)} ativos | ultimos {a.days} candle(s)\n")

    hits = scan(uni, a.days, batch=getattr(a,"batch",True), chunk=a.chunk)
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
    open(a.out,"w",encoding="utf-8").write(html)

if __name__=="__main__":
    main()
