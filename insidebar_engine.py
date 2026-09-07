#!/usr/bin/env python3
"""
TradeDesk Insidebar — motor de sinais.

Estrategia (compra, grafico diario): entrada num inside bar dentro de uma
tendencia de alta (com EMA8 e MACD confirmando forca).

Regra de sinal (o candle mais recente e o inside bar, "aguardando rompimento"):
  1. TENDENCIA: MME70 (EMA de 70) inclinada p/ CIMA e preco fechando ACIMA dela.
  2. FORCA: EMA8 inclinada p/ cima (vs 3 candles atras) E MACD (144/244/12)
     acima da linha de sinal (comprado).
  3. GATILHO: o ultimo candle e um INSIDE BAR classico — maxima < maxima da
     mae E minima > minima da mae (candle contido no range do anterior).
  4. COMPRESSAO: range do inside bar <= 60% do range da mae.
  Nivel de entrada sugerido: a MAXIMA do inside bar; stop na MINIMA do inside bar.

Reaproveita utilitarios do bt_engine. NAO mexe na logica da Agulhada.
"""
import numpy as np
import pandas as pd
import bt_engine as bt

EMA_LEN      = 70      # media movel exponencial de tendencia (longa)
EMA_SLOPE_LB = 5       # candles para medir a inclinacao da MME70
EMA_SLOPE_MIN= 0.0     # inclinacao minima (>0 = subindo). Mantemos >0 estrito.
EMA8_LEN     = 8       # media movel exponencial curta (gatilho de forca)
EMA8_SLOPE_LB= 3       # inclinacao da EMA8 medida contra 3 candles atras
MACD_FAST    = 144     # MACD customizado: media curta 144
MACD_SLOW    = 244     # media longa 244 (~1 ano de pregao no diario)
MACD_SIGNAL  = 12      # linha de sinal 12
COMPRESS_MAX = 0.60    # range do inside bar <= 60% do range da mae (compressao real)

def compute_insidebar(df):
    """Recebe DataFrame OHLCV e devolve com colunas de diagnostico e
    a coluna booleana signal_ib (sinal de inside bar de compra no ultimo candle)."""
    d = df.copy()
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]

    # --- 1) Tendencia: MME70 subindo e preco acima ---
    ema = c.ewm(span=EMA_LEN, adjust=False).mean()
    ema_slope = ema - ema.shift(EMA_SLOPE_LB)          # variacao absoluta em N candles
    ema_up = ema_slope > EMA_SLOPE_MIN                 # inclinada p/ cima
    preco_acima = c >= ema                             # fecha acima da media

    # --- 2) FORCA: EMA8 inclinada p/ cima E MACD acima da linha de sinal ---
    # EMA8 curta subindo (contra 3 candles atras) = momentum de curto prazo.
    ema8 = c.ewm(span=EMA8_LEN, adjust=False).mean()
    ema8_slope = ema8 - ema8.shift(EMA8_SLOPE_LB)
    ema8_up = ema8_slope > 0
    # MACD classico (12,26,9): linha MACD acima da linha de sinal = comprado.
    macd_fast = c.ewm(span=MACD_FAST, adjust=False).mean()
    macd_slow = c.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = macd_fast - macd_slow
    macd_sig  = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    macd_ok = macd_line > macd_sig
    forca_ok = ema8_up & macd_ok

    # --- 4) Inside bar (gatilho no ultimo candle) ---
    # candle atual contido no range do candle anterior (mae)
    inside = (h < h.shift(1)) & (l > l.shift(1))

    # --- 5) COMPRESSAO: o inside bar tem que ser bem menor que a mae ---
    # range do inside bar <= COMPRESS_MAX do range da mae. Filtra inside bars
    # "fracos" (quase do tamanho da mae), onde ha pouca compressao real e pouca
    # vantagem, conforme a literatura de price action.
    rng_ib  = (h - l)
    rng_mae = (h.shift(1) - l.shift(1))
    compress_ratio = rng_ib / rng_mae.replace(0, np.nan)
    compress_ok = compress_ratio <= COMPRESS_MAX

    # --- 3) Pullback: 2-3 candles de maximas recuando ANTES do inside bar ---
    # inside bar fecha acima da MME70 (ja coberto por preco_acima no candle atual)
    # combina tudo no candle ATUAL (o inside bar). Sem pullback: o inside bar
    # pode aparecer em qualquer ponto da tendencia de alta.
    signal_ib = (inside & compress_ok & ema_up & preco_acima
                 & forca_ok).fillna(False)

    d["ema70"] = ema
    d["ema70_slope"] = ema_slope
    d["ema8"] = ema8
    d["ema8_slope"] = ema8_slope
    d["macd"] = macd_line
    d["macd_sig"] = macd_sig
    d["inside"] = inside.fillna(False)
    d["compress_ratio"] = compress_ratio
    d["entry_level"] = h            # maxima do candle (no inside bar = nivel de rompimento)
    d["stop_level"] = l             # minima do candle (no inside bar = stop, risco menor)
    d["mae_high"] = h.shift(1)
    d["mae_low"]  = l.shift(1)
    d["signal_ib"] = signal_ib
    return d
