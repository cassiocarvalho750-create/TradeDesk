#!/usr/bin/env python3
"""
BACKTEST HISTORICO da CONFLUENCIA (DIDI x Qullamaggie) sobre uma cesta de precos.

Diferente do backtest_confluencia.py (que le os sinais REAIS gravados dia a dia),
este VARRE o passado da cesta e reconstroi, a cada dia de cada ativo, se o DIDI
e/ou o Qulla teriam disparado — classificando na prioridade da Confluencia:

  1 = DIDI entrou + Qulla ROMPEU
  2 = DIDI entrou + Qulla CONSOLIDANDO
  3 = so Qulla ROMPEU
  4 = so DIDI entrou

Simula cada sinal com alvo fixo 3R (stop conforme o setup dominante) e quebra o
resultado por prioridade, faixa de momentum e selo elite.

AVISO: isto tem VIES DE PASSADO CONHECIDO (olha um historico ja calibrado). E
uma primeira nocao — o backtest_confluencia.py (forward test, sinais ao vivo) e
a validacao honesta. Use este so para ter uma ideia enquanto aquele amadurece.

Uso: python backtest_confluencia_hist.py <pasta>   (ex.: prices_todos)
"""
import glob, sys, os, argparse
from collections import defaultdict
import numpy as np, pandas as pd
import backtest_didi as bd          # carrega()
import backtest_qulla as bq         # indicadores(), consolidacao_ok(), eh_lider()
import bt_engine as bt              # compute_signals_windowed()

ALVO_R = 3.0
MAX_HOLD = 120
PURO_1M, PURO_3M, PURO_6M = 30.0, 90.0, 150.0   # selo elite (criterios rigorosos)

# faixas de momentum iguais as da pagina/registro
def faixa_mom(m3):
    if m3 is None or (isinstance(m3, float) and np.isnan(m3)): return "sem_dado"
    if m3 >= 30: return "forte"
    if m3 >= 10: return "medio"
    return "fraco"


def simula_3r(h, l, c, i, entry, stop, alvo_r=ALVO_R, max_hold=MAX_HOLD):
    """A partir do candle SEGUINTE ao sinal (i): alvo fixo, stop fixo.
    Retorna (R, indice_de_saida)."""
    risk = entry - stop
    if risk <= 0:
        return None, i + 1
    alvo = entry + alvo_r * risk
    n = len(c)
    saiu = i + 1
    for j in range(i + 1, min(i + max_hold, n)):
        saiu = j
        lo = float(l.iloc[j]); hi = float(h.iloc[j])
        if lo <= stop:
            return -1.0, saiu
        if hi >= alvo:
            return alvo_r, saiu
    r = (float(c.iloc[min(i + max_hold, n - 1)]) - entry) / risk
    return r, min(i + max_hold, n - 1)


def processa(d):
    """Devolve a lista de sinais de confluencia de UM ativo, ja simulados.
    Cada item: dict com prioridade, faixa, elite, R."""
    d = bq.indicadores(d)               # ema, atr, mom1/3/6
    s = bt.compute_signals_windowed(d)  # sinais DIDI
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    sig_didi = s["signal_win"]
    n = len(d)
    resultados = []
    i = 130                              # depois de ter 6M de historico
    while i < n - 1:
        row = d.iloc[i]
        didi_hoje = bool(sig_didi.iloc[i])

        # Qulla: e lider + tem consolidacao valida? rompeu hoje?
        q_rompeu = False; q_consol = False; topo = None
        if bq.eh_lider(row):
            ok, topo = bq.consolidacao_ok(d, i)
            if ok:
                if float(h.iloc[i]) > topo:
                    q_rompeu = True
                else:
                    q_consol = True

        # prioridade (mesma regra da pagina)
        if didi_hoje and q_rompeu:      prio = 1
        elif didi_hoje and q_consol:    prio = 2
        elif (not didi_hoje) and q_rompeu: prio = 3
        elif didi_hoje:                 prio = 4
        else:
            i += 1; continue

        # entrada/stop conforme o setup dominante:
        #  - se Qulla rompeu (prio 1 ou 3): entra no rompimento, stop na minima do dia
        #  - senao (prio 2 ou 4, guiado pelo DIDI): entra no fechamento, stop na minima do dia
        if q_rompeu:
            op_i = float(o.iloc[i]); entry = max(topo, op_i); stop = float(l.iloc[i])
        else:
            entry = float(c.iloc[i]); stop = float(l.iloc[i])

        R, saiu = simula_3r(h, l, c, i, entry, stop)
        if R is None:
            i += 1; continue

        m1 = row["mom1"]; m3 = row["mom3"]; m6 = row["mom6"]
        m3v = None if (m3 is None or np.isnan(m3)) else float(m3)
        elite = ((not np.isnan(m1) and m1 >= PURO_1M) or
                 (not np.isnan(m3) and m3 >= PURO_3M) or
                 (not np.isnan(m6) and m6 >= PURO_6M))
        resultados.append({
            "prioridade": prio,
            "faixa": faixa_mom(m3v),
            "elite": bool(elite),
            "R": R,
        })
        i = saiu + 1                     # sem sobreposicao de trades no mesmo ativo
    return resultados


def st(rs):
    if not rs: return (0, 0.0, 0.0, 0.0)
    N = len(rs); return (N, 100*sum(1 for x in rs if x > 0)/N, sum(rs)/N, sum(rs))


def linha(rot, rs):
    N, wr, exp, acc = st(rs)
    return f"    {rot:<20} {N:>5} trades | win {wr:4.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", nargs="?", default="prices_todos")
    a = ap.parse_args()
    arqs = sorted(glob.glob(f"{a.pasta}/*.csv"))
    dfs = []
    for arq in arqs:
        tk = os.path.basename(arq).replace(".csv", "").upper()
        if tk == "SP500": continue
        try:
            d = bd.carrega(arq)
            if len(d) >= 200: dfs.append((tk, d))
        except Exception:
            pass

    todos = []; por_prio = defaultdict(list); por_faixa = defaultdict(list); por_elite = defaultdict(list)
    for tk, d in dfs:
        try:
            for r in processa(d):
                todos.append(r["R"])
                por_prio[r["prioridade"]].append(r["R"])
                por_faixa[r["faixa"]].append(r["R"])
                por_elite["ELITE" if r["elite"] else "nao-elite"].append(r["R"])
        except Exception:
            pass

    print(f"BACKTEST HISTORICO — CONFLUENCIA | cesta '{a.pasta}' | {len(dfs)} ativos | alvo {ALVO_R:.0f}R")
    print("  (vies de passado conhecido — o forward test e a validacao honesta)\n")
    N, wr, exp, acc = st(todos)
    print(f"GERAL: {N} sinais | win {wr:.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R\n")

    ROT = {1: "1 DIDI+rompeu", 2: "2 DIDI+consolid", 3: "3 so rompeu", 4: "4 so DIDI"}
    print("Por PRIORIDADE (a confluencia forte rende mais?):")
    for p in sorted(por_prio):
        print(linha(ROT.get(p, str(p)), por_prio[p]))

    print("\nPor FAIXA de momentum:")
    for k in ["forte", "medio", "fraco", "sem_dado"]:
        if por_faixa.get(k):
            print(linha(k, por_faixa[k]))

    print("\nPor selo ELITE:")
    for k in ["ELITE", "nao-elite"]:
        if por_elite.get(k):
            print(linha(k, por_elite[k]))

    print("\n  Leitura: so confie numa vantagem GRANDE e com amostra GRANDE (30+ trades).")
    print("  Este backtest historico da uma primeira nocao; a validacao real vem do forward test.")


if __name__ == "__main__":
    main()
