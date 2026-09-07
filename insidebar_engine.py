#!/usr/bin/env python3
"""
TradeDesk Insidebar — motor de sinais.

Estrategia (compra, grafico diario): entrada num inside bar dentro de uma
tendencia de alta, apos um pequeno pullback.

Regra de sinal (o candle mais recente e o inside bar, "aguardando rompimento"):
  1. TENDENCIA: MME70 (EMA de 70) inclinada p/ CIMA e preco fechando ACIMA dela.
  2. FORCA: ADX > DI- (forca de tendencia com direcao compradora).
  3. PULLBACK: 2 a 3 candles de recuo (maximas descendo) imediatamente antes
     do inside bar; pode furar a MME70 de leve, mas o inside bar fecha acima.
  4. GATILHO: o ultimo candle e um INSIDE BAR classico — maxima < maxima da
     mae E minima > minima da mae (candle contido no range do anterior).
  Nivel de entrada sugerido: a MAXIMA do inside bar (rompimento).

Reaproveita calc_adx do bt_engine. NAO mexe na logica da Agulhada.
"""
import numpy as np
import pandas as pd
import bt_engine as bt

EMA_LEN      = 70      # media movel exponencial de tendencia
EMA_SLOPE_LB = 5       # candles para medir a inclinacao da MME70
EMA_SLOPE_MIN= 0.0     # inclinacao minima (>0 = subindo). Mantemos >0 estrito.
ADX_PERIOD   = 8       # mesmo periodo do resto do projeto
PULLBACK_MIN = 2       # minimo de candles recuando antes do inside bar
PULLBACK_MAX = 3       # maximo de candles recuando antes do inside bar
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

    # --- 2) Forca: ADX > DI- ---
    adx, dip, dim = bt.calc_adx(h, l, c, period=ADX_PERIOD)
    forca_ok = adx > dim                               # ADX acima da pressao vendedora

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
    # olhamos as maximas dos candles que antecedem o inside bar (a mae e antes).
    # "recuo" = maxima menor que a do candle anterior. Contamos quantos candles
    # seguidos, terminando na MAE (shift 1), tiveram maxima descendente.
    desc = (h < h.shift(1))                            # maxima recuando neste candle
    # nº de candles descendentes consecutivos terminando na MAE (posicao shift(1))
    # run[k]=1 se a mae desceu; soma a mae e os anteriores enquanto descerem.
    run = pd.Series(0, index=d.index, dtype=float)
    # constroi o comprimento da sequencia de "desc" terminando em cada candle
    streak = pd.Series(0, index=d.index, dtype=float)
    cnt = 0
    for i in range(len(d)):
        cnt = cnt + 1 if bool(desc.iloc[i]) else 0
        streak.iloc[i] = cnt
    # o pullback e avaliado na MAE (candle anterior ao inside bar) => shift(1)
    pull_len = streak.shift(1)
    pullback_ok = (pull_len >= PULLBACK_MIN) & (pull_len <= PULLBACK_MAX)

    # inside bar fecha acima da MME70 (ja coberto por preco_acima no candle atual)
    # combina tudo no candle ATUAL (o inside bar):
    signal_ib = (inside & compress_ok & ema_up & preco_acima
                 & forca_ok & pullback_ok).fillna(False)

    d["ema70"] = ema
    d["ema70_slope"] = ema_slope
    d["adx"], d["dip"], d["dim"] = adx, dip, dim
    d["inside"] = inside.fillna(False)
    d["compress_ratio"] = compress_ratio
    d["pull_len"] = pull_len
    d["entry_level"] = h            # maxima do candle (no inside bar = nivel de rompimento)
    d["stop_level"] = l             # minima do candle (no inside bar = stop, risco menor)
    d["mae_high"] = h.shift(1)
    d["mae_low"]  = l.shift(1)
    d["signal_ib"] = signal_ib
    return d
