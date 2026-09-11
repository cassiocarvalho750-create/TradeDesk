#!/usr/bin/env python3
"""
DIAGNOSTICO do Insidebar para UM ticker — mostra criterio por criterio se o
ativo forma inside bar hoje (radar) e/ou esta dando entrada hoje (rompimento).
Funciona com qualquer ticker (baixa os dados na hora), esteja ou nao no universo.

USO:
  python diagnostico_insidebar.py STT
  python diagnostico_insidebar.py PETR4.SA
"""
import sys
import numpy as np, pandas as pd
import insidebar_engine as ib

def baixa(tk):
    import yfinance as yf
    d = yf.Ticker(tk).history(period="1y", interval="1d", auto_adjust=True)
    if d is None or d.empty: return None
    d.columns=[c.capitalize() for c in d.columns]
    if d.index.tz is not None: d.index=d.index.tz_localize(None)
    return d[["Open","High","Low","Close","Volume"]].dropna()

def sim(b): return "PASSOU " if b else "FALHOU "

def diag_pos(d, pos, titulo):
    """Diagnostica o setup completo em `pos` (candle do inside bar)."""
    o,h,l,c=d["Open"],d["High"],d["Low"],d["Close"]
    ema=c.ewm(span=ib.EMA_LEN,adjust=False).mean()
    af=ib._atr(h,l,c,ib.ATR_FAST); asl=ib._atr(h,l,c,ib.ATR_SLOW)
    ibr=(h-l)/(h.shift(1)-l.shift(1)).replace(0,np.nan)
    print(f"\n  {titulo} (candle {d.index[pos].date()})")
    print(f"    OHLC: O {o.iloc[pos]:.2f}  H {h.iloc[pos]:.2f}  L {l.iloc[pos]:.2f}  C {c.iloc[pos]:.2f}")
    # inside bar
    insi = bool(h.iloc[pos]<h.iloc[pos-1] and l.iloc[pos]>l.iloc[pos-1])
    print(f"    {sim(insi)} INSIDE BAR (contido no candle anterior)")
    if not insi:
        print("      -> nao e inside bar; sem setup neste candle.")
        return False
    # compressao
    comp = bool(ibr.iloc[pos] < ib.IB_COMPRESS)
    print(f"    {sim(comp)} COMPRESSAO: IB={ibr.iloc[pos]:.2f} < {ib.IB_COMPRESS}")
    # tendencia
    t1=bool(c.iloc[pos]>ema.iloc[pos]); t2=bool(ema.iloc[pos]>ema.iloc[pos-ib.EMA_SLOPE_LB])
    print(f"    {sim(t1)} T1 Close>EMA20: {c.iloc[pos]:.2f} > {ema.iloc[pos]:.2f}")
    print(f"    {sim(t2)} T2 EMA20 subindo: {ema.iloc[pos]:.2f} > {ema.iloc[pos-ib.EMA_SLOPE_LB]:.2f} (5 atras)")
    # estrutura HH+HL
    est=ib._estrutura_alta(h,l,pos,ib.SWING_K)
    print(f"    {sim(est)} T3 estrutura HH+HL (ultimos pivos 3x3 ascendentes)")
    # nao esticado
    dist=(c.iloc[pos]-ema.iloc[pos])/ema.iloc[pos]
    ne=bool(dist<ib.ESTICADO_MAX)
    print(f"    {sim(ne)} NAO ESTICADO: {dist*100:.1f}% < {ib.ESTICADO_MAX*100:.0f}% acima da EMA20")
    # posicao do IB
    pe=bool(l.iloc[pos]<=ema.iloc[pos]*(1+ib.IB_PERTO_EMA))
    print(f"    {sim(pe)} POSICAO IB: Low {l.iloc[pos]:.2f} <= EMA20*{1+ib.IB_PERTO_EMA} ({ema.iloc[pos]*(1+ib.IB_PERTO_EMA):.2f})")
    # contracao
    cv=bool((af.iloc[pos]/asl.iloc[pos])<ib.ATR_CONTR_MAX)
    print(f"    {sim(cv)} CONTRACAO: ATR5/ATR20={af.iloc[pos]/asl.iloc[pos]:.2f} < {ib.ATR_CONTR_MAX}")
    # consolidacao candle a candle
    atr20=float(asl.iloc[pos]); achou=False; usL=None
    for L in range(ib.CONS_MIN,ib.CONS_MAX+1):
        ini=pos-L
        if ini<0: break
        jh=h.iloc[ini:pos]; jl=l.iloc[ini:pos]; je=ema.iloc[ini:pos]
        c1=(atr20>0) and ((jh.max()-jl.min())/atr20<ib.CONS_AMPL_ATR)
        c2=bool((jl.values>=(je.values*ib.CONS_PEN_EMA)).all())
        if c1 and c2: achou=True; usL=L; break
    print(f"    {sim(achou)} CONSOLIDACAO: {('achou '+str(usL)+' candles') if achou else 'nenhuma janela 3-10 valida'}")
    ok = insi and comp and t1 and t2 and est and ne and pe and cv and achou
    print(f"    {'='*50}")
    print(f"    SETUP COMPLETO: {'>>> SIM <<<' if ok else 'NAO'}")
    return ok

def main():
    if len(sys.argv)<2:
        print("uso: python diagnostico_insidebar.py TICKER"); return
    tk=sys.argv[1].upper()
    print("="*60); print(f"  DIAGNOSTICO INSIDEBAR: {tk}"); print("="*60)
    d=baixa(tk)
    if d is None or len(d)<90:
        print(f"  sem dados suficientes para {tk}"); return
    n=len(d)
    # RADAR: inside bar HOJE (candle mais recente)
    ok_hoje=diag_pos(d, n-1, "[RADAR] inside bar HOJE (aguardando rompimento)")
    # ENTRAR HOJE: setup ONTEM + Close hoje rompeu a maxima do IB de ontem
    print(f"\n  [ENTRAR HOJE] rompimento por fechamento")
    ok_ont=diag_pos(d, n-2, "  setup ONTEM")
    if ok_ont:
        rompeu=float(d['Close'].iloc[-1])>float(d['High'].iloc[-2])
        print(f"\n    {sim(rompeu)} Close hoje {d['Close'].iloc[-1]:.2f} > maxima do IB ontem {d['High'].iloc[-2]:.2f}")
        if rompeu:
            entry=float(d['Close'].iloc[-1])
            _,ll=ib._swings(d['High'],d['Low'],ib.SWING_K)
            stop=float(d['Low'].iloc[ll[-1]]) if ll else float(d['Low'].iloc[-2])
            r=entry-stop
            print(f"    >>> ENTRAR HOJE: entrada {entry:.2f} | stop {stop:.2f} | alvo 3R {entry+3*r:.2f}")
        else:
            print(f"    -> setup valido ontem, mas ainda nao rompeu por fechamento hoje.")
    else:
        print(f"    -> ontem nao foi setup completo; sem entrada hoje por este criterio.")
    print("\n"+"="*60)

if __name__=="__main__":
    main()
