#!/usr/bin/env python3
"""
DIAGNOSTICO de um ticker: mostra criterio por criterio por que ele passou
ou NAO passou no setup da Agulhada, com os numeros exatos que o scanner usa.

USO:
  python diagnostico.py A
  python diagnostico.py PETR4.SA --timeframe 1d
  python diagnostico.py AAPL --timeframe 2h

Serve para auditar "por que fulano nao apareceu hoje?": roda a MESMA logica
do scanner (compute_signals_windowed) e explica cada pilar.
"""
import argparse
import numpy as np, pandas as pd
import bt_engine as bt
import scanner as sc

def sim(ok):   # simbolo visual
    return "PASSOU " if ok else "FALHOU "

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker", help="ticker (ex.: A, AAPL, PETR4.SA)")
    ap.add_argument("--timeframe", default="1d",
                    choices=["1d","1wk","4h","2h","1h","15m","5m"])
    a = ap.parse_args()
    tk = a.ticker.upper()
    tf = a.timeframe
    didi_win, adx_win = sc.tf_windows(tf)

    print(f"\n{'='*66}")
    print(f"  DIAGNOSTICO: {tk}  |  timeframe {tf}  |  janelas DIDI {didi_win} / ADX {adx_win}")
    print(f"{'='*66}\n")

    d = sc.fetch_intraday_ok(tk, timeframe=tf)
    if d is None or len(d) < 60:
        print(f"  Sem dados suficientes para {tk} (baixados {0 if d is None else len(d)} candles).")
        print(f"  Verifique se o ticker existe / tem historico no timeframe {tf}.")
        return

    s = bt.compute_signals_windowed(d, didi_window=didi_win, adx_window=adx_win)
    last = s.iloc[-1]
    pos  = len(s) - 1
    dt   = s.index[-1]

    # --- dados do candle de hoje ---
    o,h,l,c = float(last["Open"]),float(last["High"]),float(last["Low"]),float(last["Close"])
    print(f"  ULTIMO CANDLE: {str(dt)[:16]}")
    print(f"    Open {o:.2f}  High {h:.2f}  Low {l:.2f}  Close {c:.2f}")
    print(f"    Variacao no candle: {(c/o-1)*100:+.2f}%  ({'VERDE' if c>o else 'VERMELHO'})\n")

    # --- 1) Gatilho da Bollinger ---
    bbt = bool(last["bb_trigger"])
    # largura da banda de Bollinger nos ultimos candles
    w = bt.bollinger_width(s["Close"])
    w0 = float(w.iloc[-1]); w1 = float(w.iloc[-2]); w2 = float(w.iloc[-3])
    print(f"  [1] GATILHO BOLLINGER (a banda esta ABRINDO hoje)")
    print(f"      largura da banda: anteontem {w2:.3f} -> ontem {w1:.3f} -> hoje {w0:.3f}")
    print(f"      {sim(bbt)} banda abrindo hoje: {w0:.3f} {'>' if bbt else '<='} {w1:.3f}")
    if not bbt:
        print(f"      -> a largura da banda NAO cresceu hoje (banda estavel ou contraindo).")
        print(f"         o gatilho exige a banda em expansao no dia da confluencia.")
    print()

    # --- 2) Candle verde ---
    verde = bool(last["candle_verde"])
    print(f"  [2] CANDLE VERDE (fechamento > abertura)")
    print(f"      {sim(verde)} {c:.2f} {'>' if verde else '<='} {o:.2f}\n")

    # --- 3) DIDI: cruzamento na janela ---
    didi_now = float(s["didi3"].iloc[-1])
    didi_recent = bool(last["didi_recent"])
    # ha quantos candles ocorreu o cruzamento?
    didi_ago = None
    for k in range(0, didi_win+1):
        if pos-k>=0 and bool(s["didi_cross"].iloc[pos-k]): didi_ago=k; break
    print(f"  [3] DIDI (cruzamento MA3>MA8 em ate {didi_win} candles)")
    print(f"      didi3 hoje = {didi_now:+.3f}  (>0 = curta acima da longa)")
    if didi_ago is not None:
        print(f"      {sim(True)} cruzamento ocorreu ha {didi_ago} candle(s) (dentro da janela {didi_win})")
    else:
        print(f"      {sim(False)} nenhum cruzamento nos ultimos {didi_win} candles")
    print()

    # --- 4) ADX: evento na janela (3 sub-condicoes) ---
    adx_now  = float(s["adx"].iloc[-1]);  adx_ant = float(s["adx"].iloc[-2])
    dip_now  = float(s["dip"].iloc[-1]);  dim_now = float(s["dim"].iloc[-1])
    adx_recent = bool(last["adx_recent"])
    adx_ago = None
    for k in range(0, adx_win+1):
        if pos-k>=0 and bool(s["adx_event"].iloc[pos-k]): adx_ago=k; break
    print(f"  [4] ADX comprado — vale de DUAS formas (o que ocorrer):")
    print(f"      ADX hoje {adx_now:.1f}  |  ontem {adx_ant:.1f}  ({'subiu' if adx_now>adx_ant else 'nao subiu'})")
    print(f"      DI+ {dip_now:.1f}  DI- {dim_now:.1f}")
    # decompor as 3 condicoes NO candle de hoje
    cond_incl  = adx_now > adx_ant
    cond_dibull= dip_now > dim_now
    cond_above = adx_now >= (bt.ADX_DIM_RATIO * dim_now)
    ok_hoje = cond_incl and cond_dibull and cond_above
    print(f"      forma (i) — as 3 condicoes valem HOJE:")
    print(f"        (a) ADX inclinando p/ cima : {sim(cond_incl)} ({adx_now:.1f} {'>' if cond_incl else '<='} {adx_ant:.1f})")
    print(f"        (b) DI+ > DI-              : {sim(cond_dibull)} ({dip_now:.1f} {'>' if cond_dibull else '<='} {dim_now:.1f})")
    print(f"        (c) ADX >= 105% do DI-     : {sim(cond_above)} ({adx_now:.1f} {'>=' if cond_above else '<'} {bt.ADX_DIM_RATIO*dim_now:.1f})")
    print(f"        => forma (i): {sim(ok_hoje)}")
    print(f"      forma (ii) — 1a virada do ADX dentro da janela ({adx_win} candles):")
    if adx_ago is not None:
        print(f"        => forma (ii): {sim(True)} (virada ha {adx_ago} candle(s))")
    else:
        print(f"        => forma (ii): {sim(False)} (virada foi ha mais de {adx_win} candles)")
    adx_comprado = ok_hoje or (adx_ago is not None)
    print(f"      {sim(adx_comprado)} ADX COMPRADO (forma i OU forma ii)")
    # exigencia adicional: ADX subindo HOJE
    adx_sobe_hoje = adx_now > adx_ant
    print(f"      {sim(adx_sobe_hoje)} ADX SUBINDO HOJE (no gatilho): {adx_now:.1f} {'>' if adx_sobe_hoje else '<='} {adx_ant:.1f}")
    print()

    # --- veredito ---
    sinal = bool(last["signal_win"])
    print(f"  {'='*62}")
    print(f"  VEREDITO: {'>>> SINAL VALIDO — apareceria no scanner <<<' if sinal else 'NAO passou — nao aparece no scanner'}")
    if not sinal:
        faltou=[]
        if not bbt:   faltou.append("gatilho da Bollinger")
        if not verde: faltou.append("candle verde")
        if didi_ago is None: faltou.append(f"cruzamento do DIDI (na janela de {didi_win})")
        if not adx_comprado: faltou.append("ADX comprado (nem 3 condicoes hoje, nem virada na janela)")
        if not (adx_now > adx_ant): faltou.append("ADX subindo hoje (esta caindo no gatilho)")
        print(f"  Reprovado em: {', '.join(faltou)}")
    print(f"  {'='*62}\n")

if __name__ == "__main__":
    main()
