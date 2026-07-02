#!/usr/bin/env python3
"""
============================================================================
BACKTEST — Estrategia DIDI + ADX + Bollinger  (saida escalonada 1R/2R/3R)
============================================================================
Replica os criterios do stock_scanner.py e roda um backtest historico nos
ultimos 365 dias sobre o universo S&P500 + NASDAQ100 + B3.

Entrada : fechamento do candle que dispara os 3 criterios (core)
Stop    : minima do candle de sinal (fixo)
Saidas  : 1/3 da posicao em +1R, +1/3 em +2R, +1/3 em +3R
Filtro  : R minimo (% do preco) para descartar sinais de stop colado

Saida   : relatorio HTML com metricas e graficos (backtest_report.html)

USO:
    python3 run_backtest.py                 # universo completo, 365 dias
    python3 run_backtest.py --quick         # so ~40 tickers (teste rapido)
    python3 run_backtest.py --tickers AAPL MSFT PETR4.SA
    python3 run_backtest.py --days 730 --rmin 0.8

Requer:  pip install yfinance pandas numpy
Precisa de acesso a internet (Yahoo Finance).
============================================================================
"""
import sys, os, json, time, argparse, datetime, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import bt_engine as bt

# Piso de liquidez (volume financeiro medio diario, em milhoes) para o universo US amplo.
# Aplicado em tempo de scan (scanner.py), reusando o historico ja baixado.
US_MIN_VOL_FIN_MI = 5.0

# Piso de liquidez para a B3 (volume financeiro medio diario, em milhoes de BRL).
# Como agora varremos todas as acoes da B3, este piso descarta os codigos
# inexistentes/iliquidos (a maioria dos ~1200 gerados).
B3_MIN_VOL_FIN_MI = 5.0

# ── Universo (mesmas listas do scanner) ──────────────────────────────────────
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def _read_html_url(url, **kwargs):
    import requests, io
    r = requests.get(url, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text), **kwargs)

def get_sp500():
    try:
        df = _read_html_url("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                            attrs={"id": "constituents"})[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception as e:
        print(f"  [aviso] S&P500: {e}"); return []

def get_nasdaq100():
    try:
        for t in _read_html_url("https://en.wikipedia.org/wiki/Nasdaq-100"):
            for col in ("Ticker", "Symbol"):
                if col in t.columns:
                    return t[col].dropna().str.replace(".", "-", regex=False).tolist()
        return []
    except Exception as e:
        print(f"  [aviso] NASDAQ100: {e}"); return []

B3_BASE = [
    "ABEV3","AGRO3","ALOS3","ALPA4","ALUP11","ARZZ3","ASAI3","AURE3","AZUL4",
    "B3SA3","BBAS3","BBDC3","BBDC4","BBSE3","BEEF3","BPAC11","BRAP4","BRFS3",
    "BRKM5","CCRO3","CMIG4","CMIN3","COGN3","CPFE3","CPLE6","CRFB3","CSAN3",
    "CSNA3","CVCB3","CYRE3","DXCO3","EGIE3","ELET3","ELET6","EMBR3","ENEV3",
    "ENGI11","EQTL3","EZTC3","FLRY3","GGBR4","GOAU4","HAPV3","HYPE3","IGTI11",
    "IRBR3","ITSA4","ITUB4","JBSS3","KLBN11","LREN3","LWSA3","MGLU3","MRFG3",
    "MRVE3","MULT3","NTCO3","PCAR3","PETR3","PETR4","PETZ3","PRIO3","QUAL3",
    "RADL3","RAIL3","RAIZ4","RDOR3","RENT3","RRRP3","SANB11","SBSP3","SLCE3",
    "SMTO3","SOMA3","SUZB3","TAEE11","TIMS3","TOTS3","UGPA3","USIM5","VALE3",
    "VBBR3","VIVT3","WEGE3","YDUQ3",
]
def get_b3():
    return [t + ".SA" for t in B3_BASE]

# Lista fixa das principais acoes liquidas dos EUA (S&P500 / NASDAQ100 mais negociadas).
# Usada quando a busca na Wikipedia falha (ex.: bloqueio 403 em servidores).
US_BASE = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","TSLA","AVGO","AMD",
    "NFLX","ADBE","CRM","ORCL","IBM","INTC","QCOM","TXN","AMAT","MU",
    "ADI","LRCX","KLAC","SNPS","CDNS","MRVL","NXPI","ON","MCHP","FTNT",
    "PANW","CRWD","DDOG","SNOW","ZS","NET","MDB","TEAM","WDAY","ADSK",
    "INTU","NOW","ROP","ANSS","CTSH","ACN","CSCO","HPQ","HPE","DELL",
    "WDC","STX","SWKS","TER","GLW","KEYS","GRMN","PTC","TYL","FSLR",
    "ENPH","SEDG","GEN","AKAM","JNPR","FFIV","EPAM","CDW","NTAP","ZBRA",
    "TRMB","DIS","CMCSA","T","VZ","TMUS","CHTR","WBD","EA","TTWO",
    "OMC","IPG","LYV","NWSA","FOXA","MTCH","HD","LOW","NKE","SBUX",
    "MCD","TJX","BKNG","CMG","MAR","HLT","YUM","ROST","DG","DLTR",
    "ORLY","AZO","LULU","ULTA","DPZ","DRI","EBAY","ETSY","BBY","TSCO",
    "GPC","KMX","POOL","WSM","RL","TPR","DECK","HAS","GM","F",
    "RIVN","LCID","ABNB","UBER","LYFT","EXPE","CCL","RCL","NCLH","WYNN",
    "LVS","MGM","CZR","WMT","COST","PG","KO","PEP","MDLZ","CL",
    "KMB","GIS","KHC","MO","PM","STZ","KDP","KR","SYY","ADM",
    "HSY","MKC","CHD","CLX","TSN","CAG","CPB","HRL","K","TAP",
    "BG","EL","MNST","UNH","JNJ","LLY","ABBV","MRK","PFE","TMO",
    "ABT","DHR","BMY","AMGN","GILD","ISRG","VRTX","REGN","CVS","CI",
    "HUM","ELV","MDT","SYK","BSX","ZTS","BDX","BIIB","MRNA","DXCM",
    "IDXX","IQV","RMD","A","HCA","CNC","MCK","COR","CAH","WAT",
    "MTD","WST","ALGN","ZBH","BAX","HOLX","STE","COO","PODD","TFX",
    "DVA","JPM","BAC","WFC","GS","MS","C","BLK","SCHW","AXP",
    "SPGI","V","MA","PYPL","COF","USB","PNC","TFC","BK","CME",
    "ICE","MMC","AON","AJG","MCO","MSCI","TRV","ALL","PGR","CB",
    "AIG","MET","PRU","AFL","ACGL","HIG","FITB","HBAN","RF","CFG",
    "KEY","MTB","NTRS","STT","FDS","NDAQ","CBOE","DFS","SYF","FIS",
    "GPN","BRK-B","WTW","BRO","CINF","L","RJF","TROW","IVZ","BEN",
    "AMP","CPAY","BA","CAT","GE","HON","UPS","RTX","LMT","DE",
    "UNP","MMM","GD","NOC","EMR","ETN","ITW","CSX","NSC","FDX",
    "PH","GEV","CARR","OTIS","CMI","PCAR","ROK","AME","FTV","DOV",
    "XYL","IR","EFX","VRSK","WAB","PWR","HWM","TT","JCI","LHX",
    "TDG","AXON","ODFL","URI","FAST","PAYX","ADP","CTAS","RSG","WM",
    "GWW","SNA","SWK","HUBB","IEX","NDSN","PNR","ALLE","MAS","JBHT",
    "CHRW","EXPD","TXT","BR","LDOS","GGG","XOM","CVX","COP","SLB",
    "EOG","MPC","PSX","VLO","OXY","WMB","KMI","OKE","HES","DVN",
    "FANG","HAL","BKR","TRGP","CTRA","APA","EQT","LNG","TPL","LIN",
    "APD","SHW","ECL","NEM","FCX","DOW","NUE","PPG","ALB","DD",
    "CTVA","VMC","MLM","IFF","PKG","AMCR","AVY","BALL","CF","MOS",
    "FMC","STLD","CE","EMN","IP","SEE","WLK","NEE","DUK","SO",
    "D","AEP","EXC","SRE","XEL","ED","PEG","WEC","ES","AWK",
    "DTE","PPL","AEE","CMS","CNP","ATO","NI","LNT","EVRG","FE",
    "ETR","PCG","EIX","AES","NRG","PLD","AMT","EQIX","CCI","PSA",
    "O","SPG","WELL","DLR","VICI","AVB","EQR","EXR","INVH","MAA",
    "ARE","VTR","SBAC","UDR","CPT","KIM","REG","HST","BXP","FRT",
    "DOC","SPY","QQQ","IWM","DIA","VTI","VOO","XLF","XLE","XLK",
    "XLV","XLI","XLY","XLP","XLU","XLB","XLRE","SMH","SOXX","ARKK",
    "GLD","SLV","TLT","HYG","EEM","EFA","XBI","KRE","GDX",
]
def get_us_fixed():
    return list(US_BASE)

def get_us_large():
    """Universo US: Russell 1000 (top-1000 por market cap) uniao S&P 500.
    Liquidez filtrada no scan."""
    try:
        import us_universe as uu
        return uu.get_us_indices()
    except Exception as e:
        print(f"  [aviso] us_universe indisponivel ({e}); usando lista fixa de {len(US_BASE)} acoes")
        return list(US_BASE)

def get_b3_todas():
    """Todas as acoes da B3 (ON/PN/Unit) + curada. Liquidez filtrada no scan."""
    try:
        import us_universe as uu
        return uu.get_b3_todas()
    except Exception:
        return get_b3()

def get_universe(quick=False):
    if quick:
        u = (["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AMD","CRM","NFLX",
              "AVGO","COST","ADBE","INTC","QCOM","TXN","PYPL","SBUX","CSCO","PEP"]
             + ["PETR4.SA","VALE3.SA","ITUB4.SA","BBDC4.SA","BBAS3.SA","B3SA3.SA",
                "ABEV3.SA","WEGE3.SA","SUZB3.SA","RENT3.SA","PRIO3.SA","RADL3.SA",
                "EQTL3.SA","ELET3.SA","RAIL3.SA","LREN3.SA","HAPV3.SA","TOTS3.SA",
                "MGLU3.SA","ASAI3.SA"])
        return sorted(set(u))
    # US: indices (Russell 1000 ∪ S&P 500). B3: todas as acoes. Liquidez filtrada no scan.
    us = get_us_large()
    b3 = get_b3_todas()
    print(f"  [info] US indices: {len(us)} acoes | B3 todas: {len(b3)} codigos "
          f"(filtro de liquidez >= {US_MIN_VOL_FIN_MI} Mi/dia no scan)")
    return sorted(set(us + b3))


# ── Download + execucao ──────────────────────────────────────────────────────
def fetch(ticker, period="2y"):
    import yfinance as yf
    try:
        d = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if d is None or d.empty:
            return pd.DataFrame()
        d.columns = [c.capitalize() for c in d.columns]
        if d.index.tz is not None:
            d.index = d.index.tz_localize(None)
        return d
    except Exception:
        return pd.DataFrame()

def run(tickers, days, rmin, rmax, breakeven=False, adx_min=None, close_pos_min=None, weekly=False):
    all_trades = []
    total = len(tickers)
    print(f"Rodando backtest em {total} ativos (ultimos {days} dias)...")
    for i, tk in enumerate(tickers, 1):
        if i % 25 == 1:
            print(f"  {i}/{total}  ({tk})")
        d = fetch(tk)
        if len(d) < 120:
            continue
        try:
            tr = bt.backtest_symbol(d, tk, r_min_pct=rmin, r_max_pct=rmax,
                                    lookback_days=days, breakeven=breakeven,
                                    adx_min=adx_min, close_pos_min=close_pos_min,
                                    weekly_filter=weekly)
            all_trades.extend(tr)
        except Exception as e:
            print(f"  [erro] {tk}: {e}")
        time.sleep(0.05)
    return all_trades


# ── Metricas ─────────────────────────────────────────────────────────────────
def metrics(trades):
    if not trades:
        return {}
    df = pd.DataFrame(trades)
    closed = df[df["reason"] != "ABERTO"]
    n = len(closed)
    wins = closed[closed["result_R"] > 0]
    losses = closed[closed["result_R"] <= 0]
    total_r = closed["result_R"].sum()
    win_rate = len(wins) / n * 100 if n else 0
    avg_win = wins["result_R"].mean() if len(wins) else 0
    avg_loss = losses["result_R"].mean() if len(losses) else 0
    expectancy = closed["result_R"].mean() if n else 0
    gross_win = wins["result_R"].sum()
    gross_loss = abs(losses["result_R"].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    # max drawdown na curva de R (ordenada por data de saida)
    eq = closed.sort_values("exit_date")["result_R"].cumsum()
    peak = eq.cummax()
    dd = (eq - peak).min() if len(eq) else 0
    return {
        "n_trades": n, "n_open": int((df["reason"] == "ABERTO").sum()),
        "total_R": round(total_r, 2), "expectancy_R": round(expectancy, 3),
        "win_rate": round(win_rate, 1),
        "avg_win_R": round(avg_win, 3), "avg_loss_R": round(avg_loss, 3),
        "profit_factor": round(pf, 2) if pf != float("inf") else 999,
        "max_dd_R": round(dd, 2),
        "n_wins": len(wins), "n_losses": len(losses),
    }


# ── Relatorio HTML ───────────────────────────────────────────────────────────
def svg_equity(closed):
    """Curva de equity (R acumulado) em SVG inline."""
    if closed.empty:
        return "<p>Sem trades.</p>"
    s = closed.sort_values("exit_date")["result_R"].cumsum().values
    W, H, pad = 900, 280, 40
    n = len(s)
    lo, hi = min(0, s.min()), max(0, s.max())
    rng = (hi - lo) or 1
    def X(i): return pad + (W - 2*pad) * (i / max(1, n-1))
    def Y(v): return H - pad - (H - 2*pad) * ((v - lo) / rng)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s))
    zero_y = Y(0)
    area = f"M {X(0):.1f},{zero_y:.1f} L " + \
           " L ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s)) + \
           f" L {X(n-1):.1f},{zero_y:.1f} Z"
    color = "#2E7D4F" if s[-1] >= 0 else "#c62828"
    return f"""<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;font-family:Arial">
      <line x1="{pad}" y1="{zero_y:.1f}" x2="{W-pad}" y2="{zero_y:.1f}" stroke="#bbb" stroke-dasharray="4"/>
      <path d="{area}" fill="{color}22"/>
      <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>
      <text x="{pad}" y="20" fill="#555" font-size="13">R acumulado: {s[-1]:.2f}R em {n} trades</text>
    </svg>"""

def svg_bars(labels, values, color="#1A4731", title=""):
    if not values:
        return "<p>—</p>"
    W, H, pad = 900, 240, 50
    n = len(values)
    mx = max(values) or 1
    bw = (W - 2*pad) / n * 0.7
    gap = (W - 2*pad) / n
    bars = ""
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = pad + i*gap + (gap-bw)/2
        h = (H - 2*pad) * (v / mx)
        y = H - pad - h
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>'
        bars += f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" font-size="11" text-anchor="middle" fill="#333">{v}</text>'
        bars += f'<text x="{x+bw/2:.1f}" y="{H-pad+15:.1f}" font-size="10" text-anchor="middle" fill="#666">{lab}</text>'
    return f"""<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;font-family:Arial">
      <text x="{pad}" y="22" fill="#555" font-size="13">{title}</text>{bars}</svg>"""

def build_report(trades, params):
    df = pd.DataFrame(trades) if trades else pd.DataFrame()
    m = metrics(trades)
    today = datetime.date.today().strftime("%Y-%m-%d")

    if df.empty:
        body = "<p style='color:#c62828'>Nenhum trade gerado no periodo. " \
               "Verifique conexao, tickers ou afrouxe o filtro de R.</p>"
        return _html_shell(body, today, params)

    closed = df[df["reason"] != "ABERTO"].copy()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"])

    # Cards de metricas
    def card(label, val, good=None):
        col = "#333"
        if good is True:  col = "#2E7D4F"
        if good is False: col = "#c62828"
        return f"""<div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;
            padding:14px 18px;min-width:150px;flex:1">
            <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:.5px">{label}</div>
            <div style="font-size:24px;font-weight:700;color:{col};margin-top:4px">{val}</div></div>"""

    exp = m["expectancy_R"]
    cards = "".join([
        card("Trades", m["n_trades"]),
        card("Total", f"{m['total_R']}R", m["total_R"] > 0),
        card("Expectancy", f"{exp}R", exp > 0),
        card("Win rate", f"{m['win_rate']}%", m["win_rate"] >= 40),
        card("Profit factor", m["profit_factor"], m["profit_factor"] >= 1),
        card("Max DD", f"{m['max_dd_R']}R", None),
    ])

    # Saidas por motivo
    reason_counts = closed["reason"].value_counts()
    reasons_svg = svg_bars(list(reason_counts.index), list(reason_counts.values),
                           "#2E7D4F", "Trades por tipo de saida")

    # Top/bottom ativos por R
    by_tk = closed.groupby("ticker")["result_R"].sum().sort_values(ascending=False)
    top = by_tk.head(12)
    top_svg = svg_bars([t.replace(".SA","") for t in top.index],
                       [round(v,2) for v in top.values], "#1A4731", "Top 12 ativos (R acumulado)")

    # Tabela de trades (ordenada por data)
    show = closed.sort_values("exit_date", ascending=False).head(120)
    rows = ""
    for _, r in show.iterrows():
        rc = "#2E7D4F" if r["result_R"] > 0 else "#c62828"
        rows += f"""<tr>
            <td style="font-weight:600">{r['ticker'].replace('.SA','')}</td>
            <td>{pd.to_datetime(r['entry_date']).date()}</td>
            <td style="text-align:right">{r['entry']}</td>
            <td style="text-align:right">{r['stop']}</td>
            <td style="text-align:right">{r['R_pct']}%</td>
            <td>{pd.to_datetime(r['exit_date']).date()}</td>
            <td style="text-align:center">{r['targets']}</td>
            <td style="text-align:center;font-size:11px;color:#888">{r['reason']}</td>
            <td style="text-align:right;font-weight:700;color:{rc}">{r['result_R']:+.2f}R</td>
        </tr>"""

    body = f"""
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin:20px 0">{cards}</div>

      <h3 style="color:#1A4731;margin-top:28px">Curva de equity (R acumulado)</h3>
      <div style="background:#fafafa;border:1px solid #eee;border-radius:10px;padding:12px">{svg_equity(closed)}</div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:24px">
        <div style="background:#fafafa;border:1px solid #eee;border-radius:10px;padding:12px">{reasons_svg}</div>
        <div style="background:#fafafa;border:1px solid #eee;border-radius:10px;padding:12px">{top_svg}</div>
      </div>

      <h3 style="color:#1A4731;margin-top:28px">Trades (ultimos 120 fechados)</h3>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr style="background:#1A4731;color:#fff">
          <th style="padding:8px;text-align:left">Ativo</th><th>Entrada</th>
          <th style="text-align:right">Preco</th><th style="text-align:right">Stop</th>
          <th style="text-align:right">R%</th><th>Saida</th><th>Alvos</th>
          <th>Motivo</th><th style="text-align:right">Resultado</th>
        </tr></thead><tbody>{rows}</tbody>
      </table>
    """
    return _html_shell(body, today, params, m)

def _html_shell(body, today, params, m=None):
    pstr = (f"Janela: {params['days']} dias &nbsp;|&nbsp; R minimo: {params['rmin']}% "
            f"&nbsp;|&nbsp; Alvos: 1R/2R/3R (1/3 cada) &nbsp;|&nbsp; "
            f"Config: {params.get('extra','padrao')} &nbsp;|&nbsp; "
            f"Universo: {params['universe']}")
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Backtest DIDI+ADX+BB</title>
    <style>
      body{{font-family:'Segoe UI',Arial,sans-serif;max-width:1000px;margin:auto;
            padding:28px;color:#222;background:#fff}}
      h2{{color:#1A4731;border-bottom:3px solid #2E7D4F;padding-bottom:10px}}
      th{{padding:8px;font-weight:600}}
      td{{padding:7px 8px;border-bottom:1px solid #eee}}
      tbody tr:hover{{background:#f5f9f6}}
    </style></head><body>
      <h2>Backtest — DIDI + ADX + Bollinger &nbsp;<span style="font-size:14px;color:#888">(saida 1R/2R/3R)</span></h2>
      <p style="font-size:13px;color:#666">{pstr}</p>
      {body}
      <hr style="margin-top:32px;border:none;border-top:1px solid #eee">
      <p style="font-size:11px;color:#aaa">Gerado em {today}. Resultados em R (multiplos de risco).
      Backtest historico nao garante desempenho futuro; nao constitui recomendacao de investimento.</p>
    </body></html>"""


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="~40 tickers para teste rapido")
    ap.add_argument("--tickers", nargs="+", help="lista manual de tickers")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--rmin", type=float, default=0.5, help="R minimo %% (0 desliga)")
    ap.add_argument("--rmax", type=float, default=None, help="R maximo %% (opcional)")
    ap.add_argument("--breakeven", action="store_true", default=True,
                    help="apos T1, sobe o stop para o preco de entrada (LIGADO por padrao)")
    ap.add_argument("--no-breakeven", dest="breakeven", action="store_false",
                    help="desliga o break-even")
    ap.add_argument("--adxmin", type=float, default=None,
                    help="exige ADX >= valor no candle de sinal (ex.: 20)")
    ap.add_argument("--closepos", type=float, default=None,
                    help="exige fechamento >= fracao do candle (0..1, ex.: 0.6)")
    ap.add_argument("--weekly", action="store_true",
                    help="exige preco > EMA70 semanal e EMA70 subindo")
    ap.add_argument("--out", default="backtest_report.html")
    args = ap.parse_args()

    if args.tickers:
        tickers = args.tickers; uni = "manual"
    elif args.quick:
        tickers = get_universe(quick=True); uni = "S&P+B3 reduzido (~40)"
    else:
        tickers = get_universe(quick=False); uni = "S&P500 + NASDAQ100 + B3"

    rmin = None if args.rmin == 0 else args.rmin
    trades = run(tickers, args.days, rmin, args.rmax,
                 breakeven=args.breakeven, adx_min=args.adxmin, close_pos_min=args.closepos,
                 weekly=args.weekly)

    cfg = []
    if args.breakeven: cfg.append("break-even apos T1")
    if args.adxmin is not None: cfg.append(f"ADX>={args.adxmin}")
    if args.closepos is not None: cfg.append(f"close>={args.closepos}")
    params = {"days": args.days, "rmin": args.rmin, "universe": uni,
              "extra": " | ".join(cfg) if cfg else "padrao"}
    html = build_report(trades, params)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    m = metrics(trades)
    print("\n" + "="*56)
    if m:
        print(f"  Trades: {m['n_trades']}  |  Total: {m['total_R']}R  |  "
              f"Expectancy: {m['expectancy_R']}R  |  Win: {m['win_rate']}%")
        print(f"  Profit factor: {m['profit_factor']}  |  Max DD: {m['max_dd_R']}R")
    else:
        print("  Nenhum trade gerado.")
    print(f"  Relatorio salvo em: {args.out}")
    print("="*56)


if __name__ == "__main__":
    main()
