#!/usr/bin/env python3
"""
TradeDesk Insidebar — scanner.
Varre US + B3 no diario procurando o setup de inside bar (ver insidebar_engine).
Gera painel_insidebar.json para a pagina TradeDeskInsidebar.html.

USO: python scanner_insidebar.py
"""
import argparse, datetime, json, time
import numpy as np
import pandas as pd
import scanner as sc                 # reusa fetch_batch, fetch_intraday_ok, _liquidez_ok, tv_url
import insidebar_engine as ib
import run_backtest_v2 as rb
import us_universe as uni

def _mkt(tk): return "B3" if tk.endswith(".SA") else "EUA"

def evaluate(tk, d, today):
    """Avalia UM ticker e retorna hit se o ultimo candle for sinal de inside bar."""
    if d is None or len(d) < 90:
        return None
    for col in ("Open","High","Low","Close","Volume"):
        if col not in d.columns: return None
    try:
        r = ib.compute_insidebar(d)
    except Exception:
        return None
    last = r.iloc[-1]
    if not bool(last["signal_ib"]):
        return None
    entry = float(last["entry_level"])   # maxima do inside bar
    stop  = float(last["stop_level"])    # minima do inside bar
    r_abs = entry - stop
    r_pct = (r_abs/entry*100) if entry>0 else 0
    vol_qtd = float(last["Volume"]) if not np.isnan(last["Volume"]) else 0.0
    var_dia = ((float(last["Close"])/float(last["Open"])-1)*100) if float(last["Open"])>0 else 0.0
    return {
        "ticker": tk, "market": _mkt(tk),
        "close": round(float(last["Close"]),2),
        "entry": round(entry,2), "stop": round(stop,2),
        "r_pct": round(float(r_pct),2),
        "ema70": round(float(last["ema70"]),2),
        "ema70_up": bool(last["ema70_slope"]>0),
        "adx": round(float(last["adx"]),1),
        "dim": round(float(last["dim"]),1),
        "compress": round(float(last["compress_ratio"]),2),
        "pull_len": int(last["pull_len"]) if not np.isnan(last["pull_len"]) else None,
        "mae_high": round(float(last["mae_high"]),2),
        "mae_low": round(float(last["mae_low"]),2),
        "var_dia_pct": round(var_dia,2),
        "vol_qtd": vol_qtd,
        "date": str(d.index[-1].date()),
    }

def build_panel(hits, n_bars=40, out_path="painel_insidebar.json"):
    tz_br = datetime.timezone(datetime.timedelta(hours=-3))
    captura = datetime.datetime.now(datetime.timezone.utc).astimezone(tz_br).strftime("%d/%m/%Y %H:%M")
    ativos=[]
    for h in hits:
        tk=h["ticker"]
        d=sc.fetch_intraday_ok(tk, timeframe="1d")
        if len(d)<30: continue
        c=d["Close"]; hi=d["High"]; lo=d["Low"]; op=d["Open"]
        ema=c.ewm(span=ib.EMA_LEN, adjust=False).mean()
        def tail(s):
            return [None if (v is None or (isinstance(v,float) and np.isnan(v))) else round(float(v),4)
                    for v in s.tail(n_bars).tolist()]
        dates=[str(x.date()) for x in c.tail(n_bars).index]
        ativos.append({
            "ticker": tk.replace(".SA",""), "market": h["market"],
            "close": h["close"], "entry": h["entry"], "stop": h["stop"],
            "r_pct": h["r_pct"], "ema70": h["ema70"], "ema70_up": h["ema70_up"],
            "adx": h["adx"], "dim": h["dim"], "compress": h["compress"],
            "pull_len": h["pull_len"], "mae_high": h["mae_high"], "mae_low": h["mae_low"],
            "var_dia_pct": h["var_dia_pct"], "vol_qtd": h["vol_qtd"],
            "date": h["date"], "tv": sc.tv_url(tk),
            "dates": dates,
            "o": tail(op), "h": tail(hi), "l": tail(lo), "price": tail(c),
            "ema": tail(ema),
        })
    payload={"gerado":str(datetime.date.today()),"captura":captura,"timeframe":"1d",
             "n":len(ativos),"ativos":ativos}
    open(out_path,"w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
    print(f"  Painel JSON: {out_path} ({len(ativos)} ativo(s))")
    return out_path

def scan(tickers, batch=True, chunk=100):
    hits=[]; today=pd.Timestamp(datetime.date.today())
    try: US_MIN=float(getattr(rb,"US_MIN_VOL_FIN_MI",5.0))
    except: US_MIN=5.0
    try: B3_MIN=float(getattr(rb,"B3_MIN_VOL_FIN_MI",5.0))
    except: B3_MIN=5.0
    if batch:
        data=sc.fetch_batch(tickers, timeframe="1d", chunk=chunk)
        print(f"  baixados {len(data)}/{len(tickers)}")
        for tk in tickers:
            d=data.get(tk)
            if d is None: continue
            if not sc._liquidez_ok(tk, d, US_MIN, B3_MIN): continue
            r=evaluate(tk, d, today)
            if r: hits.append(r)
    else:
        for i,tk in enumerate(tickers,1):
            if i%50==1: print(f"  varrendo {i}/{len(tickers)}...")
            d=sc.fetch_intraday_ok(tk, timeframe="1d")
            if len(d)<90: time.sleep(0.02); continue
            if not sc._liquidez_ok(tk, d, US_MIN, B3_MIN): time.sleep(0.01); continue
            r=evaluate(tk, d, today)
            if r: hits.append(r)
            time.sleep(0.03)
    return hits

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mercado",default="ambos",choices=["ambos","us","b3"])
    ap.add_argument("--no-batch",dest="batch",action="store_false")
    ap.add_argument("--chunk",type=int,default=100)
    a=ap.parse_args()

    us = uni.US_INDICES
    b3 = uni.B3_TODAS
    if a.mercado=="us":   universo=us
    elif a.mercado=="b3": universo=b3
    else:                 universo=list(us)+list(b3)
    # B3 sempre individual (mais confiavel no candle do dia)
    print(f"Scanner Insidebar | {len(universo)} ativos | diario\n")
    hits=[]
    if a.mercado in ("us","ambos"):
        print("  [US]")
        hits += scan(list(us), batch=a.batch, chunk=a.chunk)
    if a.mercado in ("b3","ambos"):
        print("  [B3] (individual)")
        hits += scan(list(b3), batch=False, chunk=a.chunk)

    build_panel(hits, out_path="painel_insidebar.json")

    print("\n"+"="*60)
    if not hits: print("  Nenhum inside bar hoje.")
    else:
        hits.sort(key=lambda h:-(h.get("r_pct") or 0))
        print(f"  {len(hits)} sinal(is):\n")
        for h in hits:
            print(f"  {h['ticker']:<10}{h['market']:<5} entrada {h['entry']:>9} "
                  f"stop {h['stop']:>9} R%{h['r_pct']:>5} compress {h['compress']}")
    print("="*60)

if __name__=="__main__":
    main()
