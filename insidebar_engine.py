#!/usr/bin/env python3
"""
TradeDesk Insidebar — motor de sinais.

Estrategia (compra, grafico diario): entrada num inside bar dentro de uma
tendencia de alta (com EMA8 e MACD confirmando forca).

Regra de sinal (o candle mais recente e o inside bar, "aguardando rompimento"):
  1. ALINHAMENTO: MME9 > MME21 > MMS50 e as tres inclinadas p/ cima
     (tendencia de alta saudavel em curto, medio e medio-longo prazo).
  2. PERTO DA MME9: o fechamento esta encostado/logo acima da MME9 (ate 3%)
     — entra no momentum, nao esticado.
  3. NAO ESTICADO: o preco esta no maximo 8% acima da MME21 (evita topo).
  4. GATILHO: inside bar classico — maxima < maxima da mae E minima > minima.
  5. COMPRESSAO: range do inside bar <= 60% do range da mae.
  Nivel de entrada: a MAXIMA do inside bar; stop na MINIMA do inside bar.

Reaproveita utilitarios do bt_engine. NAO mexe na logica da Agulhada.
"""
import numpy as np
import pandas as pd
import bt_engine as bt

EMA9_LEN     = 9       # MME rapida (rastreador de momentum)
EMA21_LEN    = 21      # MME intermediaria
SMA50_LEN    = 50      # MMS de tendencia (simples, por escolha)
SLOPE_LB     = 3       # candles para medir a inclinacao das medias
PERTO_MME9   = 0.03    # inside bar ate 3% acima da MME9 (encostado, nao descolado)
ESTICADO_MAX = 0.08    # preco no maximo 8% acima da MME21 (evita ativo esticado)
COMPRESS_MAX = 0.60    # range do inside bar <= 60% do range da mae (compressao real)

def compute_insidebar(df):
    """Recebe DataFrame OHLCV e devolve com colunas de diagnostico e
    a coluna booleana signal_ib (sinal de inside bar de compra no ultimo candle)."""
    d = df.copy()
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]

    # --- 1) ALINHAMENTO DE MEDIAS: MME9 > MME21 > MMS50, todas subindo ---
    ema9  = c.ewm(span=EMA9_LEN,  adjust=False).mean()
    ema21 = c.ewm(span=EMA21_LEN, adjust=False).mean()
    sma50 = c.rolling(SMA50_LEN).mean()                 # simples, por escolha
    ordenadas = (ema9 > ema21) & (ema21 > sma50)        # empilhadas na ordem de alta
    m9_up  = ema9  > ema9.shift(SLOPE_LB)
    m21_up = ema21 > ema21.shift(SLOPE_LB)
    m50_up = sma50 > sma50.shift(SLOPE_LB)
    todas_subindo = m9_up & m21_up & m50_up
    alinhamento_ok = ordenadas & todas_subindo

    # --- 2) PERTO DA MME9: inside bar encostado/logo acima (nao descolado) ---
    # fechamento entre a MME9 e ate PERTO_MME9 acima dela (ex.: 0 a 3% acima).
    dist_mme9 = (c - ema9) / ema9.replace(0, np.nan)
    perto_mme9_ok = (dist_mme9 >= 0) & (dist_mme9 <= PERTO_MME9)

    # --- 3) NAO ESTICADO: preco nao muito acima da MME21 ---
    dist_mme21 = (c - ema21) / ema21.replace(0, np.nan)
    nao_esticado_ok = dist_mme21 <= ESTICADO_MAX

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

    # combina tudo no candle ATUAL (o inside bar):
    # alinhamento 9>21>50 subindo + inside encostado na MME9 + nao esticado +
    # inside bar classico + compressao real.
    signal_ib = (inside & compress_ok & alinhamento_ok
                 & perto_mme9_ok & nao_esticado_ok).fillna(False)

    d["ema9"] = ema9
    d["ema21"] = ema21
    d["sma50"] = sma50
    d["alinhamento_ok"] = alinhamento_ok.fillna(False)
    d["dist_mme9"] = dist_mme9
    d["dist_mme21"] = dist_mme21
    d["inside"] = inside.fillna(False)
    d["compress_ratio"] = compress_ratio
    d["entry_level"] = h            # maxima do candle (no inside bar = nivel de rompimento)
    d["stop_level"] = l             # minima do candle (no inside bar = stop, risco menor)
    d["mae_high"] = h.shift(1)
    d["mae_low"]  = l.shift(1)
    d["signal_ib"] = signal_ib
    return d
