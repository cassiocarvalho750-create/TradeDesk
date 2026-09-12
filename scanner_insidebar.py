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
import scanner as sc                 # reusa _liquidez_ok, tv_url
import insidebar_engine as ib
ALVO_R = 3.0   # alvo em R (backtest favoreceu 3R)
import run_backtest_v2 as rb
import us_universe as uni

# O MACD 144/244 precisa de MUITO mais historico que 1 ano p/ estabilizar.
# O Insidebar baixa seu proprio historico de 2 anos, sem mexer no fetch da
# Agulhada (que continua 1 ano no TF_CONFIG).
IB_PERIOD = "1y"   # 50 e a maior media; 1 ano basta

def _fetch_one(tk):
    """Baixa 2 anos de 1 ativo (diario)."""
    import yfinance as yf
    try:
        d = yf.Ticker(tk).history(period=IB_PERIOD, interval="1d", auto_adjust=True)
        if d is None or d.empty: return None
        d.columns = [c.capitalize() for c in d.columns]
        if d.index.tz is not None: d.index = d.index.tz_localize(None)
        return d
    except Exception:
        return None

def _fetch_batch(tickers, chunk=100):
    """Baixa 2 anos de varios ativos via yf.download."""
    import yfinance as yf
    out={}
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i+chunk]
        try:
            raw = yf.download(part, period=IB_PERIOD, interval="1d", auto_adjust=True,
                              group_by="ticker", threads=True, progress=False)
        except Exception:
            continue
        for tk in part:
            try:
                d = raw[tk].copy() if len(part) > 1 else raw.copy()
                d.columns = [c.capitalize() for c in d.columns]
                d = d.dropna(how="all")
                if d.index.tz is not None: d.index = d.index.tz_localize(None)
                if len(d) >= 50: out[tk] = d
            except Exception:
                continue
    return out

def _mkt(tk): return "B3" if tk.endswith(".SA") else "EUA"

def evaluate(tk, d, today):
    """Avalia UM ticker. Retorna dict {'hoje': hit|None, 'romp': hit|None}:
    - 'hoje': inside bar formado hoje (aguardando rompimento);
    - 'romp': ontem foi setup completo e hoje o Close rompeu a maxima do IB
      de ontem (entrar hoje, item 12)."""
    if d is None or len(d) < 90: return None
    for col in ("Open","High","Low","Close","Volume"):
        if col not in d.columns: return None
    try:
        r = ib.compute_insidebar(d)
    except Exception:
        return None
    out={"hoje":None,"romp":None}
    last = r.iloc[-1]
    vol_qtd = float(last["Volume"]) if not np.isnan(last["Volume"]) else 0.0
    var_dia = ((float(last["Close"])/float(last["Open"])-1)*100) if float(last["Open"])>0 else 0.0

    # (A) inside bar formado HOJE
    if bool(last["signal_ib"]):
        entry=float(last["entry_level"])
        sp=last.get("stop_pivo")
        stop=float(sp) if (sp is not None and not np.isnan(sp)) else float(last["stop_level"])
        r_abs=entry-stop; r_pct=(r_abs/entry*100) if entry>0 else 0
        out["hoje"]={
            "ticker":tk,"market":_mkt(tk),"close":round(float(last["Close"]),2),
            "entry":round(entry,2),"stop":round(stop,2),"parcial1r":round(entry+1*r_abs,2),"breakeven":round(entry,2),"alvo_final":round(entry+ALVO_R*r_abs,2),
            "r_pct":round(float(r_pct),2),"ema20":round(float(last["ema20"]),2),
            "dist_ema":round(float(last["dist_ema"])*100,2),"compress":round(float(last["ib_ratio"]),2),
            "cons_len":int(last["cons_len"]) if not np.isnan(last["cons_len"]) else None,
            "contr_vol":round(float(last["contr_vol_ratio"]),2),
            "mae_high":round(float(last["mae_high"]),2),"mae_low":round(float(last["mae_low"]),2),
            "var_dia_pct":round(var_dia,2),"vol_qtd":vol_qtd,"date":str(d.index[-1].date()),
        }

    # (B) ROMPIMENTO HOJE (entrar hoje)
    if r.attrs.get("rompeu_hoje"):
        entry=float(r.attrs["romp_entry"]); stop=float(r.attrs["romp_stop"])
        r_abs=entry-stop; r_pct=(r_abs/entry*100) if entry>0 else 0
        out["romp"]={
            "ticker":tk,"market":_mkt(tk),"close":round(float(last["Close"]),2),
            "entry":round(entry,2),"stop":round(stop,2),"parcial1r":round(entry+1*r_abs,2),"breakeven":round(entry,2),"alvo_final":round(entry+ALVO_R*r_abs,2),
            "r_pct":round(float(r_pct),2),"ema20":round(float(last["ema20"]),2),
            "compress":round(float(r.iloc[-2]["ib_ratio"]),2) if len(r)>=2 else None,
            "cons_len":int(r.attrs["romp_cons"]) if not (r.attrs.get("romp_cons") is None or np.isnan(r.attrs["romp_cons"])) else None,
            "var_dia_pct":round(var_dia,2),"vol_qtd":vol_qtd,"date":str(d.index[-1].date()),
            "rompeu": float(last["Close"]) > entry,   # ja fechou acima (provisorio se pregao aberto)
        }
    return out if (out["hoje"] or out["romp"]) else None

def _com_grafico(hits, n_bars=40):
    """Anexa as series de grafico (candles + EMA20) a cada hit."""
    saida=[]
    for h in hits:
        tk = h["ticker"] if h["ticker"].endswith(".SA") or h["market"]=="EUA" else h["ticker"]
        tkf = h["ticker"] if not h["ticker"].endswith(".SA") else h["ticker"]
        # o ticker no hit ja veio limpo em alguns casos; re-baixa pelo original
        raw = h.get("_tk", h["ticker"])
        d=_fetch_one(raw if raw.endswith(".SA") or h["market"]=="EUA" else raw)
        if d is None or len(d)<30:
            saida.append(h); continue
        c=d["Close"]; hi=d["High"]; lo=d["Low"]; op=d["Open"]
        ema20=c.ewm(span=ib.EMA_LEN,adjust=False).mean()
        def tail(s):
            return [None if (v is None or (isinstance(v,float) and np.isnan(v))) else round(float(v),4)
                    for v in s.tail(n_bars).tolist()]
        h=dict(h)
        h["ticker"]=h["ticker"].replace(".SA","")
        h["tv"]=sc.tv_url(raw)
        h["dates"]=[str(x.date()) for x in c.tail(n_bars).index]
        h["o"]=tail(op); h["h"]=tail(hi); h["l"]=tail(lo); h["price"]=tail(c); h["ema20s"]=tail(ema20)
        saida.append(h)
    return saida

def build_panel(grupos, n_bars=40, out_path="painel_insidebar.json"):
    tz_br = datetime.timezone(datetime.timedelta(hours=-3))
    captura = datetime.datetime.now(datetime.timezone.utc).astimezone(tz_br).strftime("%d/%m/%Y %H:%M")
    entrar = _com_grafico(grupos["romp"], n_bars)   # quadro de cima: entrar hoje
    radar  = _com_grafico(grupos["hoje"], n_bars)   # quadro de baixo: inside bar hoje
    payload={"gerado":str(datetime.date.today()),"captura":captura,"timeframe":"1d",
             "n_entrar":len(entrar),"n_radar":len(radar),
             "entrar":entrar,"ativos":radar}
    open(out_path,"w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
    print(f"  Painel JSON: {out_path} (entrar hoje: {len(entrar)} | radar IB: {len(radar)})")
    return out_path

def scan(tickers, batch=True, chunk=100):
    hoje=[]; romp=[]; today=pd.Timestamp(datetime.date.today())
    try: US_MIN=float(getattr(rb,"US_MIN_VOL_FIN_MI",5.0))
    except: US_MIN=5.0
    try: B3_MIN=float(getattr(rb,"B3_MIN_VOL_FIN_MI",5.0))
    except: B3_MIN=5.0
    def _push(tk,r):
        if not r: return
        if r.get("hoje"): r["hoje"]["_tk"]=tk; hoje.append(r["hoje"])
        if r.get("romp"): r["romp"]["_tk"]=tk; romp.append(r["romp"])
    if batch:
        data=_fetch_batch(tickers, chunk=chunk)
        print(f"  baixados {len(data)}/{len(tickers)}")
        for tk in tickers:
            d=data.get(tk)
            if d is None: continue
            if not sc._liquidez_ok(tk, d, US_MIN, B3_MIN): continue
            _push(tk, evaluate(tk, d, today))
    else:
        for i,tk in enumerate(tickers,1):
            if i%50==1: print(f"  varrendo {i}/{len(tickers)}...")
            d=_fetch_one(tk)
            if d is None or len(d)<90: time.sleep(0.02); continue
            if not sc._liquidez_ok(tk, d, US_MIN, B3_MIN): time.sleep(0.01); continue
            _push(tk, evaluate(tk, d, today))
            time.sleep(0.03)
    return {"hoje":hoje,"romp":romp}

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
    grupos={"hoje":[],"romp":[]}
    if a.mercado in ("us","ambos"):
        print("  [US]")
        g=scan(list(us), batch=a.batch, chunk=a.chunk)
        grupos["hoje"]+=g["hoje"]; grupos["romp"]+=g["romp"]
    if a.mercado in ("b3","ambos"):
        print("  [B3] (individual)")
        g=scan(list(b3), batch=False, chunk=a.chunk)
        grupos["hoje"]+=g["hoje"]; grupos["romp"]+=g["romp"]

    # ordena cada grupo por maior compressao
    for k in grupos:
        grupos[k].sort(key=lambda h:(h.get("compress") if h.get("compress") is not None else 9))
    build_panel(grupos, out_path="painel_insidebar.json")

    print("\n"+"="*60)
    print(f"  ENTRAR HOJE (rompimento): {len(grupos['romp'])}")
    for h in grupos["romp"]:
        print(f"    {h['ticker']:<10}{h['market']:<5} ent {h['entry']:>8} stop {h['stop']:>8} parc1R {h.get('parcial1r','—')} final3R {h.get('alvo_final','—')}")
    print(f"  RADAR (inside bar hoje): {len(grupos['hoje'])}")
    for h in grupos["hoje"]:
        print(f"    {h['ticker']:<10}{h['market']:<5} entrada {h['entry']:>9} stop {h['stop']:>9} compress {h['compress']}")
    print("="*60)

if __name__=="__main__":
    main()
