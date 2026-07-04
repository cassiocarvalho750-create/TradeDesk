#!/usr/bin/env python3
"""
Motor de backtest — replica os criterios do stock_scanner.py e aplica
saida escalonada por R (1/3 em 1R, 1/3 em 2R, 1/3 em 3R), stop na minima
do candle de sinal. Entrada no FECHAMENTO do candle de sinal.

Alavancas opcionais (calibracao):
  breakeven  -> apos T1, sobe o stop para o preco de entrada (zero-a-zero)
  adx_min    -> exige ADX >= piso no candle de sinal (forca de tendencia)
  close_pos  -> exige fechamento no terco superior do candle (forca do candle)
"""

import numpy as np
import pandas as pd

# ── Parametros padrao ────────────────────────────────────────────────────────
DIDI_TOLERANCE  = 20.0
DIDI_CROSS_BARS = 2      # aceita sinal so no candle do cruzamento ou no seguinte (hoje ou ontem)
R_MIN_PCT       = 0.5
R_MAX_PCT       = None
LOOKBACK_DAYS   = 365
ADX_DIM_RATIO   = 1.05   # ADX deve estar >= 105% do DI- (5% acima da pressao vendedora)
WEEKLY_EMA      = 70     # EMA da media semanal para o filtro de tendencia


# ── Indicadores ──────────────────────────────────────────────────────────────
def sma(s, n): return s.rolling(n).mean()

def bollinger_width(close, period=8, std_dev=2.0):
    m = sma(close, period)
    s = close.rolling(period).std()
    return (m + std_dev * s) - (m - std_dev * s)

def calc_adx(high, low, close, period=8):
    pc  = close.shift(1)
    tr  = pd.concat([(high - low), (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    up  = high - high.shift(1)
    dn  = low.shift(1) - low
    dmp = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=close.index)
    dmm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=close.index)
    a   = 1.0 / period
    atr = tr.ewm(alpha=a, adjust=False).mean()
    dip = 100 * dmp.ewm(alpha=a, adjust=False).mean() / atr.replace(0, np.nan)
    dim = 100 * dmm.ewm(alpha=a, adjust=False).mean() / atr.replace(0, np.nan)
    dx  = 100 * (dip - dim).abs() / (dip + dim).replace(0, np.nan)
    return dx.ewm(alpha=a, adjust=False).mean(), dip, dim


# ── Sinais (core do scanner) ─────────────────────────────────────────────────
def compute_signals(df):
    c, h, l = df["Close"], df["High"], df["Low"]
    ma3, ma8 = sma(c, 3), sma(c, 8)
    didi3 = (ma3 / ma8 - 1.0) * 100.0

    # A: DIDI — CRUZAMENTO CONSUMADO da MA3 sobre a MA8 (de baixo p/ cima).
    # Hoje a MA3 esta acima da MA8 e no candle anterior estava abaixo,
    # OU isso ocorreu em alguma das ultimas DIDI_CROSS_BARS barras.
    didi_ok = pd.Series(False, index=df.index)
    for i in range(0, DIDI_CROSS_BARS):
        crossed = (didi3.shift(i) > 0) & (didi3.shift(i + 1) <= 0)
        didi_ok = didi_ok | crossed

    # B: ADX/DMI(8,8) — primeira inclinacao p/ cima, DI+ > DI-, e ADX >= 105% do DI-
    adx, dip, dim = calc_adx(h, l, c)
    adx_first_turn = (adx > adx.shift(1)) & (adx.shift(1) <= adx.shift(2))  # 1a inclinacao
    di_bull        = dip > dim                                              # DI+ acima do DI-
    adx_above_dim  = adx >= (ADX_DIM_RATIO * dim)                           # ADX >= 105% do DI-
    adx_ok = adx_first_turn & di_bull & adx_above_dim

    # C: Bollinger(8,2) — primeira abertura das bandas (expansao)
    w = bollinger_width(c)
    bb_ok = (w > w.shift(1)) & (w.shift(1) <= w.shift(2))

    df = df.copy()
    df["didi3"] = didi3
    df["adx"], df["dip"], df["dim"] = adx, dip, dim
    df["bb_w"] = w
    df["signal"] = (didi_ok & adx_ok & bb_ok).fillna(False)
    # Posicao do fechamento dentro do candle (0=na minima, 1=na maxima)
    rng = (h - l).replace(0, np.nan)
    df["close_pos"] = ((c - l) / rng).fillna(0.5)

    # ── Filtro semanal (regime do ativo no grafico semanal) ───────────────────
    # Preco acima da EMA70 semanal E essa EMA inclinada p/ cima.
    # Usa SEMPRE a ultima semana FECHADA (sem viola futuro): o valor semanal
    # so passa a valer no diario a partir da 1a barra da semana SEGUINTE.
    wk = c.resample("W").last().dropna()              # fechamento semanal
    wk_ema70 = wk.ewm(span=WEEKLY_EMA, adjust=False).mean()
    wk_above = wk > wk_ema70                            # preco > EMA70 (semana fechada)
    wk_rising = wk_ema70 > wk_ema70.shift(1)            # EMA70 subindo
    wk_ok = (wk_above & wk_rising)
    # Desloca 1 semana: o resultado de uma semana so e conhecido na semana seguinte
    wk_ok_shifted = wk_ok.shift(1)
    # Reindexa para o diario por preenchimento p/ frente (cada dia herda a ult. semana fechada)
    weekly_filter = wk_ok_shifted.reindex(df.index, method="ffill").fillna(False)
    df["weekly_ok"] = weekly_filter.astype(bool)
    return df


# ── Simulacao de um ativo ────────────────────────────────────────────────────
def backtest_symbol(df, ticker,
                    r_min_pct=R_MIN_PCT, r_max_pct=R_MAX_PCT,
                    lookback_days=LOOKBACK_DAYS,
                    r_targets=(1.0, 2.0, 3.0),
                    breakeven=False, adx_min=None, close_pos_min=None,
                    weekly_filter=False, pivot_filter=False, pivot_n=3,
                    date_start=None, date_end=None,
                    precomputed=False, min_bars=120):
    """
    Entra no close do candle de sinal. Stop = minima do candle de sinal.
    Sai 1/3 em cada alvo R.

    breakeven      -> apos T1, stop sobe para o preco de entrada
    adx_min        -> filtro: ADX do candle de sinal >= valor
    close_pos_min  -> filtro: fechamento >= esta fracao do range do candle (0..1)
    weekly_filter  -> so entra se preco > EMA70 semanal E EMA70 semanal subindo
                      (usa a ultima semana FECHADA, sem viola futuro)
    date_start     -> so permite ENTRADAS a partir desta data (inclusive)
    date_end       -> so permite ENTRADAS ate esta data (inclusive)
                      (se date_start/date_end forem usados, lookback_days e ignorado)
    """
    if not precomputed:
        df = compute_signals(df)
    if pivot_filter:
        df = add_pivot_uptrend(df, n=pivot_n)
    if len(df) < min_bars:
        return []

    use_range = date_start is not None or date_end is not None
    last_date = df.index[-1]
    cutoff = last_date - pd.Timedelta(days=lookback_days)
    ds = pd.Timestamp(date_start) if date_start else None
    de = pd.Timestamp(date_end) if date_end else None

    trades = []
    in_pos = False
    entry_price = stop = r = entry_date = None
    remaining = 0.0
    realized_r = 0.0
    targets_hit = []
    be_active = False
    t1, t2, t3 = r_targets

    closes = df["Close"].values
    highs  = df["High"].values
    lows   = df["Low"].values
    sigs   = df["signal"].values
    dates  = df.index
    adxv   = df["adx"].values if "adx" in df else np.full(len(df), np.nan)
    cposv  = df["close_pos"].values if "close_pos" in df else np.full(len(df), 0.5)
    wkokv  = df["weekly_ok"].values if "weekly_ok" in df else np.full(len(df), True)

    for i in range(len(df)):
        date = dates[i]

        if in_pos:
            tp1 = entry_price + t1 * r
            tp2 = entry_price + t2 * r
            tp3 = entry_price + t3 * r
            cur_stop = entry_price if be_active else stop

            # 1) Stop (conservador: checa antes dos alvos)
            if lows[i] <= cur_stop:
                exit_r = (cur_stop - entry_price) / r
                realized_r += remaining * exit_r
                reason = "BREAKEVEN" if (be_active and abs(exit_r) < 1e-9) else "STOP"
                trades.append(_close(ticker, entry_date, entry_price, date,
                                     cur_stop, r, realized_r, targets_hit, reason))
                in_pos = False
                continue

            # 2) Alvos
            if remaining > 1e-9 and "T1" not in targets_hit and highs[i] >= tp1:
                realized_r += (1/3) * t1; remaining -= 1/3; targets_hit.append("T1")
                if breakeven:
                    be_active = True
            if remaining > 1e-9 and "T2" not in targets_hit and highs[i] >= tp2:
                realized_r += (1/3) * t2; remaining -= 1/3; targets_hit.append("T2")
            if remaining > 1e-9 and "T3" not in targets_hit and highs[i] >= tp3:
                realized_r += (1/3) * t3; remaining -= 1/3; targets_hit.append("T3")

            if remaining <= 1e-9:
                trades.append(_close(ticker, entry_date, entry_price, date,
                                     tp3, r, realized_r, targets_hit, "ALVO_3R"))
                in_pos = False
                continue

        else:
            if use_range:
                in_window = (ds is None or date >= ds) and (de is None or date <= de)
            else:
                in_window = date >= cutoff
            if sigs[i] and in_window:
                ep = closes[i]; sl = lows[i]; rr = ep - sl
                if rr <= 0:
                    continue
                r_pct = rr / ep * 100.0
                if r_min_pct is not None and r_pct < r_min_pct:
                    continue
                if r_max_pct is not None and r_pct > r_max_pct:
                    continue
                # filtros de forca de entrada
                if adx_min is not None and not (adxv[i] >= adx_min):
                    continue
                if close_pos_min is not None and not (cposv[i] >= close_pos_min):
                    continue
                # filtro de tendencia semanal (preco > EMA70 sem. e EMA70 subindo)
                if weekly_filter and not bool(wkokv[i]):
                    continue
                if pivot_filter and not bool(pvokv[i]):
                    continue
                in_pos = True
                entry_price, stop, r, entry_date = ep, sl, rr, date
                remaining = 1.0; realized_r = 0.0; targets_hit = []; be_active = False

    if in_pos:
        last_close = closes[-1]
        realized_r += remaining * ((last_close - entry_price) / r)
        trades.append(_close(ticker, entry_date, entry_price, dates[-1],
                             last_close, r, realized_r, targets_hit, "ABERTO"))

    return trades


def _close(ticker, ed, ep, xd, xp, r, total_r, hits, reason):
    return {
        "ticker": ticker,
        "entry_date": ed, "entry": round(ep, 4),
        "exit_date": xd, "exit_ref": round(xp, 4),
        "stop": round(ep - r, 4), "R_size": round(r, 4),
        "R_pct": round(r / ep * 100, 3),
        "result_R": round(total_r, 4),
        "targets": "+".join(hits) if hits else "-",
        "reason": reason,
        "bars_held": None,
    }


# ── Indicador auxiliar: media movel para trailing ────────────────────────────
def add_trail_ma(df, ma_period, ma_type="EMA"):
    """Adiciona coluna trail_ma (media movel do Close) ao df ja com sinais."""
    c = df["Close"]
    if ma_type.upper() == "SMA":
        df["trail_ma"] = c.rolling(ma_period).mean()
    else:
        df["trail_ma"] = c.ewm(span=ma_period, adjust=False).mean()
    return df


# ── Backtest com saida 'deixar correr' (parcial + trailing por media) ─────────
def backtest_trailing(df, ticker,
                      r_min_pct=R_MIN_PCT, r_max_pct=R_MAX_PCT,
                      partial_frac=1/3, partial_r=1.0,
                      ma_period=21, ma_type="EMA",
                      breakeven_after_partial=True,
                      weekly_filter=False, pivot_filter=False, pivot_n=3,
                      date_start=None, date_end=None,
                      precomputed=False, min_bars=120):
    """
    Entrada: 3 criterios (DIDI+ADX+BB), no fechamento do candle de sinal.
    Stop inicial: minima do candle de sinal. R = entrada - stop.

    Saida 'deixar correr':
      - Realiza `partial_frac` da posicao ao atingir +`partial_r`R (alivio cedo).
      - O restante corre ate o Close FECHAR abaixo da media movel (ma_period).
        Quando isso ocorre, sai todo o restante no fechamento desse candle.
      - Se o stop inicial bater antes da parcial, sai tudo no stop.
      - Se breakeven_after_partial=True, apos a parcial o stop do restante sobe
        para o preco de entrada (nunca devolve o trade ao prejuizo).

    Retorna lista de trades (mesmo formato), com result_R em multiplos de risco.
    """
    if not precomputed:
        df = compute_signals(df)
    df = add_trail_ma(df, ma_period, ma_type)
    if pivot_filter:
        df = add_pivot_uptrend(df, n=pivot_n)
    if len(df) < min_bars:
        return []

    use_range = date_start is not None or date_end is not None
    last_date = df.index[-1]
    cutoff = last_date - pd.Timedelta(days=LOOKBACK_DAYS)
    ds = pd.Timestamp(date_start) if date_start else None
    de = pd.Timestamp(date_end) if date_end else None

    closes = df["Close"].values
    highs  = df["High"].values
    lows   = df["Low"].values
    sigs   = df["signal"].values
    dates  = df.index
    mav    = df["trail_ma"].values
    wkokv  = df["weekly_ok"].values if "weekly_ok" in df else np.full(len(df), True)
    pvokv  = df["pivot_ok"].values if "pivot_ok" in df else np.full(len(df), True)

    trades = []
    in_pos = False
    entry_price = stop = r = entry_date = None
    remaining = 0.0
    realized_r = 0.0
    partial_done = False

    for i in range(len(df)):
        date = dates[i]
        if in_pos:
            cur_stop = entry_price if (partial_done and breakeven_after_partial) else stop

            # 1) Stop (minima fura o stop corrente) -> sai todo o restante
            if lows[i] <= cur_stop:
                realized_r += remaining * ((cur_stop - entry_price) / r)
                reason = "BREAKEVEN" if (partial_done and breakeven_after_partial
                                          and abs(cur_stop-entry_price) < 1e-9) else "STOP"
                trades.append(_close(ticker, entry_date, entry_price, date,
                                     cur_stop, r, realized_r, ["T1"] if partial_done else [], reason))
                in_pos = False
                continue

            # 2) Parcial em +partial_r R (uma vez)
            if not partial_done:
                tp = entry_price + partial_r * r
                if highs[i] >= tp:
                    realized_r += partial_frac * partial_r
                    remaining -= partial_frac
                    partial_done = True

            # 3) Trailing: se o restante existe e o Close fecha abaixo da media -> sai
            if partial_done and remaining > 1e-9 and not np.isnan(mav[i]):
                if closes[i] < mav[i]:
                    realized_r += remaining * ((closes[i] - entry_price) / r)
                    trades.append(_close(ticker, entry_date, entry_price, date,
                                         closes[i], r, realized_r, ["T1","TRAIL"], "TRAIL_MA"))
                    in_pos = False
                    continue
        else:
            if use_range:
                in_window = (ds is None or date >= ds) and (de is None or date <= de)
            else:
                in_window = date >= cutoff
            if sigs[i] and in_window:
                ep = closes[i]; sl = lows[i]; rr = ep - sl
                if rr <= 0:
                    continue
                r_pct = rr / ep * 100.0
                if r_min_pct is not None and r_pct < r_min_pct:
                    continue
                if r_max_pct is not None and r_pct > r_max_pct:
                    continue
                if weekly_filter and not bool(wkokv[i]):
                    continue
                if pivot_filter and not bool(pvokv[i]):
                    continue
                in_pos = True
                entry_price, stop, r, entry_date = ep, sl, rr, date
                remaining = 1.0; realized_r = 0.0; partial_done = False

    if in_pos:
        lc = closes[-1]
        realized_r += remaining * ((lc - entry_price) / r)
        tags = ["T1","ABERTO"] if partial_done else ["ABERTO"]
        trades.append(_close(ticker, entry_date, entry_price, dates[-1],
                             lc, r, realized_r, tags, "ABERTO"))
    return trades


# ── Filtro estrutural: pivo de alta (topos/fundos ascendentes) ────────────────
def add_pivot_uptrend(df, n=3):
    """
    Marca, para cada barra, se existe ESTRUTURA DE ALTA confirmada e se o
    ultimo topo pivo ja foi rompido/esta sendo rompido (sem lookahead).

    Pivo de topo  : high[i] > high de n barras antes E n barras depois.
    Pivo de fundo : low[i]  < low de n barras antes E n barras depois.
    Um pivo so e CONFIRMADO n barras depois dele (quando ja vimos as n a direita).

    Estrutura de alta no instante t:
      - ha >=2 fundos confirmados ate t e os 2 ultimos sao ascendentes
      - ha >=2 topos confirmados ate t e os 2 ultimos sao ascendentes
    'Pivo rompido/rompendo' no instante t:
      - close[t] >= ultimo topo pivo confirmado (preco superou a resistencia)
    Resultado em df['pivot_ok'] (bool).
    """
    h = df["High"].values; l = df["Low"].values; c = df["Close"].values
    N = len(df)
    is_top = np.zeros(N, dtype=bool)
    is_bot = np.zeros(N, dtype=bool)
    for i in range(n, N - n):
        seg_h = h[i-n:i+n+1]; seg_l = l[i-n:i+n+1]
        if h[i] == seg_h.max() and (seg_h.argmax() == n):
            is_top[i] = True
        if l[i] == seg_l.min() and (seg_l.argmin() == n):
            is_bot[i] = True

    pivot_ok = np.zeros(N, dtype=bool)
    # Vamos varrer no tempo, mantendo listas de pivos JA CONFIRMADOS.
    # Um pivo em barra j fica confirmado a partir de j+n.
    tops = []   # (idx, price) de topos confirmados
    bots = []   # (idx, price) de fundos confirmados
    for t in range(N):
        # confirma pivos cuja "barra direita" termina em t (ou seja, pivo em t-n)
        j = t - n
        if j >= 0:
            if is_top[j]:
                tops.append((j, h[j]))
            if is_bot[j]:
                bots.append((j, l[j]))
        # estrutura de alta: 2 ultimos fundos e 2 ultimos topos ascendentes
        struct_up = False
        if len(bots) >= 2 and len(tops) >= 2:
            if bots[-1][1] > bots[-2][1] and tops[-1][1] > tops[-2][1]:
                struct_up = True
        # rompido/rompendo: close atual >= ultimo topo confirmado
        broke = False
        if tops:
            broke = c[t] >= tops[-1][1]
        pivot_ok[t] = struct_up and broke

    df = df.copy()
    df["pivot_ok"] = pivot_ok
    return df


# ── Indicadores para a saida classica do Didi ────────────────────────────────
def stochastic(df, k=8, d=3, smooth=3):
    """Estocastico %K/%D. Retorna (%K_suavizado, %D)."""
    low_k  = df["Low"].rolling(k).min()
    high_k = df["High"].rolling(k).max()
    rng = (high_k - low_k).replace(0, np.nan)
    raw_k = 100 * (df["Close"] - low_k) / rng
    k_s = raw_k.rolling(smooth).mean()      # %K suavizado
    d_s = k_s.rolling(d).mean()             # %D
    return k_s, d_s

def trix(close, length=9, signal=4):
    """TRIX (tripla EMA do log-retorno) e sua linha de sinal.
    Parametros da imagem: TRIX MA (9,4,2) -> length=9, signal=4."""
    e1 = close.ewm(span=length, adjust=False).mean()
    e2 = e1.ewm(span=length, adjust=False).mean()
    e3 = e2.ewm(span=length, adjust=False).mean()
    tr = e3.pct_change() * 100.0
    sig = tr.ewm(span=signal, adjust=False).mean()
    return tr, sig

def compute_didi_exit_signals(df):
    """
    Adiciona 'didi_exit' (bool): True quando os 4 criterios estao no ESTADO
    de baixa AO MESMO TEMPO (nao a virada exata, mas todos apontando p/ baixo):
      1) BB fechando: banda superior caindo (sup_t < sup_{t-1})
      2) ADX caindo: adx_t < adx_{t-1}
      3) TRIX rapida abaixo da linha de sinal (estado de venda)
      4) Estocastico %K abaixo de %D (estado de venda)
    Parametros: BB(8,2), DMI(8,8), Stoch(8,3,3), TRIX(9,4,2).
    """
    c, h, l = df["Close"], df["High"], df["Low"]

    # 1) BB(8,2) banda superior caindo
    basis = c.rolling(8).mean()
    dev   = 2.0 * c.rolling(8).std()
    upper = basis + dev
    bb_down = upper < upper.shift(1)

    # 2) ADX(8,8) caindo
    adx, dip, dim = calc_adx(h, l, c, period=8)
    adx_down = adx < adx.shift(1)

    # 3) TRIX(9,4): rapida abaixo da sinal
    tr, sig = trix(c, length=9, signal=4)
    trix_down = tr < sig

    # 4) Estocastico(8,3,3): %K abaixo de %D
    k_s, d_s = stochastic(df, k=8, d=3, smooth=3)
    stoch_down = k_s < d_s

    df = df.copy()
    df["bb_down"]    = bb_down.fillna(False)
    df["adx_down"]   = adx_down.fillna(False)
    df["trix_down"]  = trix_down.fillna(False)
    df["stoch_down"] = stoch_down.fillna(False)
    df["didi_exit"]  = (df["bb_down"] & df["adx_down"] &
                        df["trix_down"] & df["stoch_down"])
    return df


# ── Backtest com SAIDA CLASSICA DO DIDI (estado dos 4 criterios) ──────────────
def backtest_didi_exit(df, ticker,
                       r_min_pct=R_MIN_PCT, r_max_pct=R_MAX_PCT,
                       partial_frac=1/3, partial_r=1.0, use_partial=True,
                       breakeven_after_partial=True,
                       weekly_filter=False, pivot_filter=False, pivot_n=3,
                       date_start=None, date_end=None,
                       precomputed=False, min_bars=120):
    """
    Entrada: 3 criterios (DIDI+ADX+BB) no fechamento do candle de sinal.
    Stop inicial: minima do candle de sinal. R = entrada - stop.
    Saida:
      - (opcional) realiza partial_frac em +partial_r R, com break-even depois.
      - SAI TODO O RESTANTE quando o ESTADO dos 4 criterios de saida do Didi
        fica verdadeiro (BB caindo, ADX caindo, TRIX<sinal, Stoch<sinal).
      - Se o stop inicial bater antes, sai tudo no stop.
    """
    if not precomputed:
        df = compute_signals(df)
        df = compute_didi_exit_signals(df)
    elif "didi_exit" not in df:
        df = compute_didi_exit_signals(df)
    if pivot_filter:
        df = add_pivot_uptrend(df, n=pivot_n)
    if len(df) < min_bars:
        return []

    use_range = date_start is not None or date_end is not None
    last_date = df.index[-1]
    cutoff = last_date - pd.Timedelta(days=LOOKBACK_DAYS)
    ds = pd.Timestamp(date_start) if date_start else None
    de = pd.Timestamp(date_end) if date_end else None

    closes = df["Close"].values; highs = df["High"].values; lows = df["Low"].values
    sigs   = df["signal"].values; dates = df.index
    exitv  = df["didi_exit"].values
    wkokv  = df["weekly_ok"].values if "weekly_ok" in df else np.full(len(df), True)
    pvokv  = df["pivot_ok"].values if "pivot_ok" in df else np.full(len(df), True)

    trades=[]; in_pos=False
    entry_price=stop=r=entry_date=None; remaining=0.0; realized_r=0.0; partial_done=False

    for i in range(len(df)):
        date=dates[i]
        if in_pos:
            cur_stop = entry_price if (partial_done and breakeven_after_partial) else stop
            # 1) stop
            if lows[i] <= cur_stop:
                realized_r += remaining*((cur_stop-entry_price)/r)
                reason="BREAKEVEN" if (partial_done and breakeven_after_partial and abs(cur_stop-entry_price)<1e-9) else "STOP"
                trades.append(_close(ticker,entry_date,entry_price,date,cur_stop,r,realized_r,
                                     ["T1"] if partial_done else [], reason))
                in_pos=False; continue
            # 2) parcial
            if use_partial and not partial_done:
                tp=entry_price+partial_r*r
                if highs[i]>=tp:
                    realized_r += partial_frac*partial_r
                    remaining -= partial_frac
                    partial_done=True
            # 3) saida pelo estado dos 4
            if remaining>1e-9 and bool(exitv[i]):
                realized_r += remaining*((closes[i]-entry_price)/r)
                tags=(["T1"] if partial_done else [])+["DIDI_EXIT"]
                trades.append(_close(ticker,entry_date,entry_price,date,closes[i],r,realized_r,tags,"DIDI_EXIT"))
                in_pos=False; continue
        else:
            if use_range:
                in_window=(ds is None or date>=ds) and (de is None or date<=de)
            else:
                in_window=date>=cutoff
            if sigs[i] and in_window:
                ep=closes[i]; sl=lows[i]; rr=ep-sl
                if rr<=0: continue
                rp=rr/ep*100.0
                if r_min_pct is not None and rp<r_min_pct: continue
                if r_max_pct is not None and rp>r_max_pct: continue
                if weekly_filter and not bool(wkokv[i]): continue
                if pivot_filter and not bool(pvokv[i]): continue
                in_pos=True; entry_price,stop,r,entry_date=ep,sl,rr,date
                remaining=1.0; realized_r=0.0; partial_done=False

    if in_pos:
        lc=closes[-1]; realized_r += remaining*((lc-entry_price)/r)
        trades.append(_close(ticker,entry_date,entry_price,dates[-1],lc,r,realized_r,
                             (["T1"] if partial_done else [])+["ABERTO"],"ABERTO"))
    return trades


# ── Sinal com JANELAS e gatilho na BB (para o scanner) ───────────────────────
def compute_signals_windowed(df, didi_window=5, adx_window=3):
    """
    Versao do sinal onde os 3 criterios NAO precisam coincidir no mesmo candle.
    Gatilho = BB abrindo (primeira expansao) NO candle atual. Nesse candle:
      - DIDI: cruzamento da MA3 sobre a MA8 ocorreu HOJE ou em ate `didi_window`
              candles anteriores.
      - ADX : sinal do ADX (1a inclinacao + DI+>DI- + ADX>=105% DI-) ocorreu
              HOJE ou em ate `adx_window` candles anteriores.
    Adiciona coluna 'signal_win' (bool) e colunas auxiliares de diagnostico.
    """
    c, h, l = df["Close"], df["High"], df["Low"]
    ma3, ma8 = sma(c, 3), sma(c, 8)
    didi3 = (ma3 / ma8 - 1.0) * 100.0

    # evento DIDI: cruzamento consumado neste candle
    didi_cross = (didi3 > 0) & (didi3.shift(1) <= 0)

    # evento ADX: 1a inclinacao + DI+>DI- + ADX>=105% DI-
    adx, dip, dim = calc_adx(h, l, c, period=8)
    adx_first = (adx > adx.shift(1)) & (adx.shift(1) <= adx.shift(2))
    di_bull   = dip > dim
    adx_above = adx >= (ADX_DIM_RATIO * dim)
    adx_event = adx_first & di_bull & adx_above

    # gatilho BB: primeira expansao neste candle
    w = bollinger_width(c)
    bb_trigger = (w > w.shift(1)) & (w.shift(1) <= w.shift(2))

    # candle do gatilho da BB deve ser POSITIVO (verde): fechamento > abertura
    o = df["Open"]
    candle_verde = c > o

    # janelas: DIDI ocorreu em [hoje .. hoje-didi_window]; idem ADX
    didi_recent = pd.Series(False, index=df.index)
    for k in range(0, didi_window + 1):
        didi_recent = didi_recent | didi_cross.shift(k).fillna(False)
    adx_recent = pd.Series(False, index=df.index)
    for k in range(0, adx_window + 1):
        adx_recent = adx_recent | adx_event.shift(k).fillna(False)

    df = df.copy()
    df["didi3"] = didi3
    df["adx"], df["dip"], df["dim"] = adx, dip, dim
    df["didi_cross"] = didi_cross.fillna(False)
    df["adx_event"]  = adx_event.fillna(False)
    df["bb_trigger"] = bb_trigger.fillna(False)
    df["candle_verde"] = candle_verde.fillna(False)
    df["didi_recent"] = didi_recent
    df["adx_recent"]  = adx_recent
    # sinal: BB dispara HOJE (em candle verde) e DIDI/ADX ja ocorreram nas janelas
    df["signal_win"] = (bb_trigger.fillna(False) & candle_verde.fillna(False)
                        & didi_recent & adx_recent)
    return df
