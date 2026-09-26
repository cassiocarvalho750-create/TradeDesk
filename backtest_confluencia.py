#!/usr/bin/env python3
"""
Backtest da CONFLUENCIA (forward test). Le o historico_confluencia.csv — a foto
diaria da aba Confluencia, gravada AO VIVO dia a dia (sem vies de olhar o
futuro) — baixa o preco de cada ativo a partir da data do sinal e simula o
trade com alvo fixo 3R (stop na minima registrada).

Responde as perguntas que importam:
  - a CONFLUENCIA funciona? (resultado geral)
  - qual PRIORIDADE rende mais? (1 DIDI+rompeu / 2 DIDI+consolid / 3 so DIDI / 4 so rompeu)
  - a POSICAO NA FILA prediz melhores trades? (topo da lista vs resto;
    topo de cada subgrupo vs resto)
  - a FAIXA de momentum e o selo ELITE ajudam?

USO:
  python backtest_confluencia.py
  python backtest_confluencia.py --hold 60 --alvo 3

Precisa de yfinance (pip install yfinance). Rode so quando ja tiver ACUMULADO
sinais suficientes (idealmente 3+ meses / 100+ sinais).
"""
import sys, os, csv, argparse
from collections import defaultdict

ARQ = "historico_confluencia.csv"


def baixa(tk, desde):
    import yfinance as yf
    d = yf.Ticker(tk).history(start=desde, interval="1d", auto_adjust=True)
    if d is None or d.empty:
        return None
    d.columns = [c.capitalize() for c in d.columns]
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d


def simula_3r(d, data_sinal, entry, stop, alvo_r=3.0, max_hold=60):
    """A partir do dia SEGUINTE ao sinal: alvo fixo em alvo_r*R, stop fixo.
    Retorna R do trade (+alvo_r vitoria, -1 stop, ou marcacao a mercado)."""
    import pandas as pd
    risk = entry - stop
    if risk <= 0:
        return None
    try:
        idx = d.index.searchsorted(pd.Timestamp(data_sinal))
    except Exception:
        return None
    alvo = entry + alvo_r * risk
    for j in range(idx + 1, min(idx + 1 + max_hold, len(d))):
        lo = float(d["Low"].iloc[j]); hi = float(d["High"].iloc[j])
        if lo <= stop:
            return -1.0
        if hi >= alvo:
            return alvo_r
    # nao bateu nem stop nem alvo: marca a mercado no fim da janela
    c = float(d["Close"].iloc[min(idx + max_hold, len(d) - 1)])
    return (c - entry) / risk


def st(rs):
    if not rs:
        return (0, 0.0, 0.0, 0.0)
    n = len(rs)
    return (n, 100 * sum(1 for x in rs if x > 0) / n, sum(rs) / n, sum(rs))


def linha_stat(rotulo, rs):
    n, w, e, a = st(rs)
    return f"    {rotulo:<26} {n:>4} trades | win {w:4.0f}% | exp {e:+.3f}R | acum {a:+.0f}R"


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _sim(v):
    return str(v).strip().lower() in ("true", "1", "sim")


def _prio_da_linha(s):
    """Prioridade recalculada pelas colunas de sinais, e nao pelo numero gravado:
    ate 26/09/2026 o registro gravava 3 = so rompeu e 4 = so DIDI (invertido).
    Assim as linhas antigas e as novas usam a mesma numeracao."""
    didi, romp, cons = _sim(s.get("tem_didi")), _sim(s.get("q_rompeu")), _sim(s.get("q_consolidando"))
    if didi and romp: return "1"
    if didi and cons: return "2"
    if didi:          return "3"
    if romp:          return "4"
    return s.get("prioridade", "?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=int, default=60, help="max dias no trade (default 60)")
    ap.add_argument("--alvo", type=float, default=3.0, help="alvo em R (default 3.0)")
    ap.add_argument("--arquivo", default=ARQ)
    a = ap.parse_args()

    if not os.path.exists(a.arquivo):
        print(f"Arquivo {a.arquivo} nao encontrado. Deixe os scanners rodarem por um tempo primeiro.")
        return
    linhas = list(csv.DictReader(open(a.arquivo, encoding="utf-8")))
    if not linhas:
        print(f"{a.arquivo} esta vazio (so cabecalho). Ainda nao ha sinais gravados.")
        return
    print(f"Forward test — CONFLUENCIA | {len(linhas)} sinais registrados | alvo {a.alvo:.0f}R hold {a.hold}d\n")

    # so linhas com entrada e stop numericos (prio 4 sem Qulla nao tem 'entrada';
    # usa entrada do Qulla quando existe, senao pula — sem entrada nao ha trade).
    por_tk = defaultdict(list)
    for r in linhas:
        por_tk[r["ticker"]].append(r)

    todos = []
    por_prio = defaultdict(list)
    por_faixa = defaultdict(list)
    por_elite = defaultdict(list)
    por_pos_geral = defaultdict(list)   # topo3 da lista vs resto
    por_pos_sub = defaultdict(list)     # 1o do subgrupo vs resto
    sem_entrada = 0
    ignorados_preco = 0

    tkmarket = lambda r: (r["ticker"] + ".SA") if r.get("market") == "B3" else r["ticker"]

    for tk, sinais in por_tk.items():
        desde = min(s["data"] for s in sinais)
        try:
            d = baixa(tkmarket(sinais[0]), desde)
        except Exception:
            d = None
        if d is None:
            ignorados_preco += len(sinais)
            continue
        for s in sinais:
            entry = _num(s.get("entrada")); stop = _num(s.get("stop"))
            if entry is None or stop is None:
                sem_entrada += 1
                continue
            R = simula_3r(d, s["data"], entry, stop, alvo_r=a.alvo, max_hold=a.hold)
            if R is None:
                continue
            todos.append(R)
            prio = _prio_da_linha(s)
            por_prio[prio].append(R)
            por_faixa[s.get("faixa_mom", "?")].append(R)
            por_elite["ELITE" if s.get("elite") in ("True", "true", True) else "nao-elite"].append(R)
            og = _num(s.get("ordem_geral")) or 999
            por_pos_geral["topo3 (fila geral)" if og <= 3 else "resto (fila geral)"].append(R)
            osub = _num(s.get("ordem_subgrupo")) or 999
            por_pos_sub["1o do subgrupo" if osub == 1 else "resto do subgrupo"].append(R)

    N, wr, exp, acc = st(todos)
    print(f"GERAL: {N} trades | win {wr:.0f}% | exp {exp:+.3f}R | acum {acc:+.0f}R")
    if sem_entrada:
        print(f"  ({sem_entrada} sinais so-DIDI sem preco de entrada do Qulla — nao dao trade)")
    if ignorados_preco:
        print(f"  ({ignorados_preco} ignorados: sem historico de preco)")
    print()

    ROT_PRIO = {"1": "1 DIDI+rompeu", "2": "2 DIDI+consolid", "3": "3 so DIDI", "4": "4 so rompeu"}
    print("Por PRIORIDADE (a confluencia mais forte rende mais?):")
    for p in sorted(por_prio):
        print(linha_stat(ROT_PRIO.get(p, p), por_prio[p]))

    print("\nPor POSICAO na fila (a ordem prediz melhores trades?):")
    for k in ["topo3 (fila geral)", "resto (fila geral)"]:
        if por_pos_geral.get(k):
            print(linha_stat(k, por_pos_geral[k]))
    for k in ["1o do subgrupo", "resto do subgrupo"]:
        if por_pos_sub.get(k):
            print(linha_stat(k, por_pos_sub[k]))

    print("\nPor FAIXA de momentum:")
    for k in ["forte", "medio", "fraco", "sem_dado"]:
        if por_faixa.get(k):
            print(linha_stat(k, por_faixa[k]))

    print("\nPor selo ELITE (criterios rigorosos do criador):")
    for k in ["ELITE", "nao-elite"]:
        if por_elite.get(k):
            print(linha_stat(k, por_elite[k]))

    print("\n  Leitura: so confie numa vantagem que seja GRANDE e com amostra GRANDE (30+ trades).")
    print("  Win rate parecido entre grupos = provavelmente ruido. Espere 3-6 meses de dados.")


if __name__ == "__main__":
    main()
