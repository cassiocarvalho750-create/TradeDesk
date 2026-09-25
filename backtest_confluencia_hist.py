#!/usr/bin/env python3
"""
BACKTEST HISTORICO da CONFLUENCIA (DIDI x Qullamaggie) sobre uma cesta de precos.

Varre o passado da cesta e reconstroi, a cada dia de cada ativo, a prioridade:
  1 = DIDI entrou + Qulla ROMPEU      2 = DIDI entrou + Qulla CONSOLIDANDO
  3 = so Qulla ROMPEU                 4 = so DIDI entrou
Simula alvo fixo 3R. Execucao REALISTA por padrao (ver exec_confluencia.py);
--idealizado reproduz a regra antiga, que usava a minima do proprio dia como stop.

AVISO: vies de passado conhecido. A validacao honesta e o forward test
(backtest_confluencia.py).

Uso: python backtest_confluencia_hist.py prices_todos
     python backtest_confluencia_hist.py prices_todos --idealizado
"""
import argparse, warnings
from collections import defaultdict
warnings.simplefilter("ignore")
import exec_confluencia as ec


def faixa_mom(m3):
    if m3 is None: return "sem_dado"
    if m3 >= 30: return "forte"
    if m3 >= 10: return "medio"
    return "fraco"


def st(rs):
    if not rs: return (0, 0.0, 0.0, 0.0)
    N = len(rs); return (N, 100 * sum(1 for x in rs if x > 0) / N, sum(rs) / N, sum(rs))


def linha(rot, rs):
    N, wr, exp, acc = st(rs)
    return f"    {rot:<20} {N:>5} trades | win {wr:4.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", nargs="?", default="prices_todos")
    ap.add_argument("--idealizado", action="store_true")
    a = ap.parse_args()
    dfs = ec.carrega_cesta(a.pasta)
    todos = []; por_prio = defaultdict(list); por_faixa = defaultdict(list); por_elite = defaultdict(list)
    for tk, d in dfs:
        try:
            for t in ec.processa(d, a.idealizado):
                todos.append(t["R"]); por_prio[t["prioridade"]].append(t["R"])
                por_faixa[faixa_mom(t["mom3"])].append(t["R"])
                por_elite["ELITE" if t["elite"] else "nao-elite"].append(t["R"])
        except Exception:
            pass
    print(f"BACKTEST HISTORICO — CONFLUENCIA | cesta '{a.pasta}' | {len(dfs)} ativos | alvo 3R")
    print(f"  Execucao {ec.rotulo_execucao(a.idealizado)}")
    print("  (vies de passado conhecido — o forward test e a validacao honesta)\n")
    N, wr, exp, acc = st(todos)
    print(f"GERAL: {N} sinais | win {wr:.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R\n")
    ROT = {1: "1 DIDI+rompeu", 2: "2 DIDI+consolid", 3: "3 so rompeu", 4: "4 so DIDI"}
    print("Por PRIORIDADE:")
    for p in sorted(por_prio): print(linha(ROT[p], por_prio[p]))
    print("\nPor FAIXA de momentum 3M:")
    for k in ["forte", "medio", "fraco", "sem_dado"]:
        if por_faixa.get(k): print(linha(k, por_faixa[k]))
    print("\nPor selo ELITE:")
    for k in ["ELITE", "nao-elite"]:
        if por_elite.get(k): print(linha(k, por_elite[k]))
    print("\n  So confie em vantagem GRANDE com amostra GRANDE (30+ trades).")


if __name__ == "__main__":
    main()
