#!/usr/bin/env python3
"""
TradeDesk Insidebar — motor de sinais (spec completa).

Estrutura: TENDENCIA -> CONSOLIDACAO/PULLBACK -> INSIDE BAR -> (rompimento).
Referencia principal: EMA20 no diario. Entrada no rompimento da MAXIMA do
inside bar; stop na MINIMA do inside bar.

REGRAS (compra / LONG):
 1. TENDENCIA: T1 Close>EMA20; T2 EMA20 subindo (vs 5 atras); T3 estrutura de
    alta por swings — ultimo topo > topo anterior (HH) E ultimo fundo > fundo
    anterior (HL). Swing = pivo com K candles de cada lado.
 2. NAO ESTICADO: (Close-EMA20)/EMA20 < 0.08.
 3. CONSOLIDACAO (janela antes do inside bar): 3-10 candles; amplitude/ATR20
    < 2.5; LowestLow > EMA20*0.98; contracao ATR5/ATR20 < 0.80.
 4. INSIDE BAR: High[t]<High[t-1] E Low[t]>Low[t-1] (mae = t-1).
 5. COMPRESSAO IB: IB_range/MotherBar_range < 0.70.
 6. POSICAO IB: |Low_IB - EMA20|/EMA20 < 0.03.

Parametros em constantes (para backtest). NAO mexe na logica da Agulhada.
"""
import numpy as np
import pandas as pd

EMA_LEN        = 20
EMA_SLOPE_LB   = 5
ESTICADO_MAX   = 0.08
SWING_K        = 3       # 3 candles de cada lado (ignora micro-oscilacao)
CONS_MIN       = 3
CONS_MAX       = 10
CONS_AMPL_ATR  = 2.5
CONS_PEN_EMA   = 0.98
ATR_CONTR_MAX  = 0.80
ATR_FAST       = 5
ATR_SLOW       = 20
IB_COMPRESS    = 0.70
IB_PERTO_EMA   = 0.03


def _atr(h, l, c, period):
    pc = c.shift(1)
    tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _swings(h, l, k):
    n = len(h); hi_idx=[]; lo_idx=[]
    hv = h.values; lv = l.values
    for i in range(k, n-k):
        jh = hv[i-k:i+k+1]; jl = lv[i-k:i+k+1]
        if hv[i] == jh.max() and jh.argmax()==k: hi_idx.append(i)
        if lv[i] == jl.min() and jl.argmin()==k: lo_idx.append(i)
    return hi_idx, lo_idx


def _estrutura_alta(h, l, pos, k):
    hh, ll = _swings(h.iloc[:pos+1], l.iloc[:pos+1], k)
    if len(hh) < 2 or len(ll) < 2: return False
    sh1, sh2 = h.iloc[hh[-1]], h.iloc[hh[-2]]
    sl1, sl2 = l.iloc[ll[-1]], l.iloc[ll[-2]]
    return bool(sh1 > sh2 and sl1 > sl2)


def compute_insidebar(df):
    d = df.copy()
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    n = len(d)

    ema = c.ewm(span=EMA_LEN, adjust=False).mean()
    atr_fast = _atr(h, l, c, ATR_FAST)
    atr_slow = _atr(h, l, c, ATR_SLOW)

    inside = (h < h.shift(1)) & (l > l.shift(1))
    rng_ib  = (h - l)
    rng_mae = (h.shift(1) - l.shift(1))
    ib_ratio = rng_ib / rng_mae.replace(0, np.nan)
    compress_ok = ib_ratio < IB_COMPRESS

    dist_ema  = (c - ema) / ema.replace(0, np.nan)
    nao_esticado = dist_ema < ESTICADO_MAX
    t1 = c > ema
    t2 = ema > ema.shift(EMA_SLOPE_LB)
    perto_ema = (l - ema).abs() / ema.replace(0, np.nan) < IB_PERTO_EMA
    contr_vol = (atr_fast / atr_slow.replace(0, np.nan)) < ATR_CONTR_MAX

    signal   = pd.Series(False, index=d.index)
    estrut   = pd.Series(False, index=d.index)
    cons_ok  = pd.Series(False, index=d.index)
    cons_len = pd.Series(np.nan, index=d.index)

    pos = n - 1
    if (pos >= max(EMA_LEN, ATR_SLOW, CONS_MAX) + 2*SWING_K + 2
        and bool(inside.iloc[pos])):
        ema_now = float(ema.iloc[pos]); atr20 = float(atr_slow.iloc[pos])
        achou=False; usado=np.nan
        for L in range(CONS_MIN, CONS_MAX+1):
            ini = pos - L
            if ini < 0: break
            jh = h.iloc[ini:pos]; jl = l.iloc[ini:pos]
            if len(jh) < L: break
            ampl = (jh.max() - jl.min())
            c1 = (atr20 > 0) and (ampl/atr20 < CONS_AMPL_ATR)
            c2 = jl.min() > ema_now * CONS_PEN_EMA
            if c1 and c2: achou=True; usado=L; break
        cons_ok.iloc[pos]=achou; cons_len.iloc[pos]=usado
        # estrutura HH+HL avaliada ATE O INICIO DA CONSOLIDACAO (nao ate hoje),
        # para a lateralizacao nao sujar a leitura dos swings. Se nao houve
        # consolidacao, cai para avaliar ate a mae (pos-1).
        ate = (pos - int(usado)) if achou and not np.isnan(usado) else (pos-1)
        est = _estrutura_alta(h, l, ate, SWING_K); estrut.iloc[pos]=est
        ok = (bool(t1.iloc[pos]) and bool(t2.iloc[pos]) and est
              and bool(nao_esticado.iloc[pos]) and achou
              and bool(contr_vol.iloc[pos]) and bool(compress_ok.iloc[pos])
              and bool(perto_ema.iloc[pos]))
        signal.iloc[pos]=ok

    d["ema20"]=ema; d["atr5"]=atr_fast; d["atr20"]=atr_slow
    d["inside"]=inside.fillna(False); d["ib_ratio"]=ib_ratio
    d["dist_ema"]=dist_ema; d["estrutura_ok"]=estrut
    d["cons_ok"]=cons_ok; d["cons_len"]=cons_len
    d["contr_vol_ratio"]=atr_fast/atr_slow.replace(0,np.nan)
    d["entry_level"]=h; d["stop_level"]=l
    d["mae_high"]=h.shift(1); d["mae_low"]=l.shift(1)
    d["signal_ib"]=signal
    return d
