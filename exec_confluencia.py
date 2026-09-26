#!/usr/bin/env python3
"""
Motor unico da CONFLUENCIA (DIDI x Qullamaggie) para os backtests historicos.
Usado por backtest_confluencia_hist.py e backtest_confluencia_momentum.py.

Dois modos de execucao:

REALISTA (padrao) — so usa informacao disponivel no momento da decisao:
  - Lado Qulla (prio 1 e 4, quando ha rompimento):
      a lista de candidatos (lider de momentum + consolidacao valida) e montada
      com os dados de ONTEM; hoje a ordem de compra fica no topo da consolidacao
      (ou na abertura, se abrir acima). Stop na MINIMA DE ONTEM. Se o preco volta
      abaixo do stop no proprio dia da entrada, conta como stop (-1R).
  - Lado DIDI (prio 2 e 3): entrada no FECHAMENTO do dia do sinal, stop no
      PIVO de baixa 3x3 (regra do scanner DIDI ao vivo).
  - A prioridade (1 x 3, 2 x 4) e decidida no fechamento, quando se sabe se o
      DIDI confirmou. Prio 1 e 4 sao executadas do mesmo jeito.

IDEALIZADO — a regra antiga, para comparacao: lider avaliado no proprio dia,
  entrada no rompimento com stop na minima do PROPRIO dia (so conhecida no
  fechamento) e, no lado DIDI, entrada no fechamento com stop na minima do dia.

Saida: alvo fixo 3R, stop fixo, no maximo 120 pregoes. Um trade por vez por ativo.
"""
import numpy as np, pandas as pd
import backtest_didi as bd
import backtest_qulla as bq
import bt_engine as bt

ALVO_R = 3.0
MAX_HOLD = 120
PURO_1M, PURO_3M, PURO_6M = 30.0, 90.0, 150.0


def _simula(h, l, c, i, entry, stop, checa_dia_entrada):
    """Retorna (R, indice_saida) ou (None, i+1) se o stop for invalido."""
    risk = entry - stop
    if risk <= 0:
        return None, i + 1
    if checa_dia_entrada and float(l.iloc[i]) <= stop:
        return -1.0, i
    alvo = entry + ALVO_R * risk
    n = len(c); saiu = i + 1
    for j in range(i + 1, min(i + MAX_HOLD, n)):
        saiu = j
        if float(l.iloc[j]) <= stop: return -1.0, saiu
        if float(h.iloc[j]) >= alvo: return ALVO_R, saiu
    fim = min(i + MAX_HOLD, n - 1)
    return (float(c.iloc[fim]) - entry) / risk, fim


def _nan(x):
    return x is None or (isinstance(x, float) and np.isnan(x))


def processa(d, idealizado=False):
    """Lista de trades de UM ativo: dicts com prioridade, mom3, elite, R, data."""
    d = bq.indicadores(d)
    s = bt.compute_signals_windowed(d)
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    sig = s["signal_win"]
    n = len(d); out = []; i = 130
    while i < n - 1:
        didi = bool(sig.iloc[i])
        ref = d.iloc[i] if idealizado else d.iloc[i - 1]     # lista de candidatos Qulla
        romp = cons = False; topo = None
        if bq.eh_lider(ref):
            ok, topo = bq.consolidacao_ok(d, i)
            if ok:
                if float(h.iloc[i]) > topo: romp = True
                else: cons = True
        if didi and romp:   prio = 1
        elif didi and cons: prio = 2
        elif didi:          prio = 3   # so DIDI
        elif romp:          prio = 4   # so Qulla rompeu
        else:
            i += 1; continue

        if romp:
            entry = max(topo, float(o.iloc[i]))
            stop = float(l.iloc[i]) if idealizado else float(l.iloc[i - 1])
            R, saiu = _simula(h, l, c, i, entry, stop, checa_dia_entrada=not idealizado)
        else:
            entry = float(c.iloc[i])
            if idealizado:
                stop = float(l.iloc[i])
            else:
                sp = bd.swings_low(h, l, i, 3)
                stop = sp if sp is not None else float(l.iloc[i])
            R, saiu = _simula(h, l, c, i, entry, stop, checa_dia_entrada=False)
        if R is None:
            i += 1; continue

        row = d.iloc[i]
        m1, m3, m6 = row["mom1"], row["mom3"], row["mom6"]
        elite = ((not _nan(m1) and m1 >= PURO_1M) or (not _nan(m3) and m3 >= PURO_3M)
                 or (not _nan(m6) and m6 >= PURO_6M))
        out.append({"prioridade": prio, "mom3": None if _nan(m3) else float(m3),
                    "elite": bool(elite), "R": R, "data": d.index[i]})
        i = saiu + 1
    return out


def carrega_cesta(pasta):
    import glob, os
    dfs = []
    for arq in sorted(glob.glob(f"{pasta}/*.csv")):
        tk = os.path.basename(arq).replace(".csv", "").upper()
        if tk == "SP500": continue
        try:
            d = bd.carrega(arq)
            if len(d) >= 200: dfs.append((tk, d))
        except Exception:
            pass
    return dfs


def rotulo_execucao(idealizado):
    if idealizado:
        return "IDEALIZADA (regra antiga, com vies: stop na minima do proprio dia)"
    return ("REALISTA (rompimento: candidatos de ontem, stop na minima de ontem, stop no mesmo dia conta; "
            "DIDI: entrada no fechamento, stop no pivo)")
