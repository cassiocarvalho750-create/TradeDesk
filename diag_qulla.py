#!/usr/bin/env python3
"""
Diagnostica UM ativo no funil do setup Qullamaggie: mostra em que etapa ele
passa ou para. Usa a MESMA logica do scanner_qulla.

Uso: python diag_qulla.py NTNX
     python diag_qulla.py PETR4.SA
"""
import sys
import numpy as np, pandas as pd

MOM_1M, MOM_3M, MOM_6M = 20.0, 60.0, 100.0   # afrouxado 30/90/150 -> 20/60/100 (validado: +0.738R, pega lideres moderados)
CONSOL_MIN, CONSOL_MAX = 5, 15
ATR_CONTRACAO = 1.10
DIST_EMA_MAX = 0.10

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(h, l, c, n):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def main():
    tk = sys.argv[1] if len(sys.argv) > 1 else "NTNX"
    import yfinance as yf
    d = yf.Ticker(tk).history(period="1y", interval="1d", auto_adjust=True)
    if d is None or d.empty:
        print(f"Nao consegui baixar {tk}"); return
    d.columns = [c.capitalize() for c in d.columns]
    if d.index.tz is not None: d.index = d.index.tz_localize(None)
    c, h, l = d["Close"], d["High"], d["Low"]
    if len(d) < 140:
        print(f"{tk}: historico curto ({len(d)} candles) — precisa de >=140"); return

    ema20 = ema(c, 20); atr5 = atr(h,l,c,5); atr20 = atr(h,l,c,20)
    mom1 = (c.iloc[-1]/c.iloc[-22]-1)*100
    mom3 = (c.iloc[-1]/c.iloc[-64]-1)*100
    mom6 = (c.iloc[-1]/c.iloc[-127]-1)*100

    print(f"\n=== DIAGNOSTICO QULLAMAGGIE: {tk} ===")
    print(f"preco hoje: {c.iloc[-1]:.2f}  ({d.index[-1].date()})\n")

    print(f"1) MOMENTUM (precisa 1M>={MOM_1M:.0f} OU 3M>={MOM_3M:.0f} OU 6M>={MOM_6M:.0f}):")
    print(f"   1M = {mom1:+.0f}%   3M = {mom3:+.0f}%   6M = {mom6:+.0f}%")
    lider = (mom1>=MOM_1M) or (mom3>=MOM_3M) or (mom6>=MOM_6M)
    print(f"   -> LIDER? {'SIM ✓' if lider else 'NAO ✗ (barrado aqui)'}\n")
    if not lider:
        print("   Motivo de nao aparecer: nao e lider de momentum hoje."); return

    print(f"2) CONSOLIDACAO (janela 5-15d, ATR5 < ATR20*{ATR_CONTRACAO}, dist EMA20 <= {DIST_EMA_MAX}):")
    i = len(d)-1
    achou = False
    for n in range(CONSOL_MAX, CONSOL_MIN-1, -1):
        if i-n < 1: continue
        jan = slice(i-n, i)
        hh = h.iloc[jan].max(); ll = l.iloc[jan].min(); e20 = ema20.iloc[jan].mean()
        cond_atr = atr5.iloc[i-1] < atr20.iloc[i-1]*ATR_CONTRACAO
        dist = abs(c.iloc[i-1]-e20)/e20 if e20>0 else 9
        cond_dist = dist <= DIST_EMA_MAX
        cond_low = ll >= e20*0.90
        ok = cond_atr and cond_dist and cond_low
        marca = "  <== PASSA" if ok else ""
        print(f"   {n:2}d: ATR5/ATR20={atr5.iloc[i-1]/atr20.iloc[i-1]:.2f}(ok?{cond_atr})  "
              f"distEMA={dist:.3f}(ok?{cond_dist})  low_acima_EMA*0.9?{cond_low}{marca}")
        if ok: achou = True; topo = hh; ndias = n; break
    if not achou:
        print("\n   -> CONSOLIDACAO nao validada em nenhuma janela (barrado aqui).")
        print("   Veja acima qual condicao falhou (ATR, distEMA ou low).")
        return

    print(f"\n   -> CONSOLIDACAO OK: {ndias} dias, topo em {topo:.2f}\n")
    print("3) ROMPIMENTO (maxima de hoje > topo da consolidacao?):")
    maxhoje = float(h.iloc[-1])
    rompeu = maxhoje > topo
    print(f"   maxima hoje = {maxhoje:.2f}  vs  topo = {topo:.2f}")
    print(f"   -> {'ROMPENDO HOJE ✓ (apareceria como ROMPENDO)' if rompeu else 'ainda nao rompeu (apareceria como CONSOLIDANDO)'}")
    print(f"\n   RESULTADO: {tk} {'APARECE no scanner' if achou else 'nao aparece'}"
          f" {'(rompendo)' if rompeu else '(consolidando)'}")

if __name__ == "__main__":
    main()
