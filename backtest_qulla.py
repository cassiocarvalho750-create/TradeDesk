#!/usr/bin/env python3
"""
============================================================================
BACKTEST — SETUP QULLAMAGGIE (Kristjan Kullamägi) — momentum breakout
============================================================================
A ideia do Qullamaggie, em 3 passos:

  1) MOMENTUM (o coracao): so olha LIDERES — ativos que ja subiram muito.
     Lider se: +30% em 1 mes  OU  +90% em 3 meses  OU  +150% em 6 meses.

  2) CONSOLIDACAO: depois da alta, a acao descansa de lado 5-15 dias, com
     a volatilidade CAINDO (ATR contraindo) e o preco COLADO na EMA10/20
     (nao esticado). E a "bandeira"/flag.

  3) BREAKOUT: entra no ROMPIMENTO da maxima da consolidacao. Stop na minima
     do dia de entrada (loss curto). Saida: parcial na forca + trailing na
     EMA (o resto sai quando fecha abaixo da EMA de trailing).

Uso: python backtest_qulla.py <pasta>   (ex.: prices_todos)
============================================================================
"""
import glob, sys, os, argparse
import numpy as np, pandas as pd
import backtest_didi as bd   # reaproveita carrega()

# ---- parametros (todos ajustaveis no topo) ----
MOM_1M, MOM_3M, MOM_6M = 25.0, 75.0, 125.0   # sweet spot: quase sem perda de qualidade (+0.785R), 70% mais sinais
CONSOL_MIN, CONSOL_MAX = 5, 15               # dias da consolidacao
ATR_CONTRACAO = 1.10       # afrouxado 1.0->1.10 (validado: +21% sinais, exp igual)
DIST_EMA_MAX = 0.10        # preco a no maximo 10% da EMA20 (nao esticado)
EMA_PROX = 20              # EMA de referencia p/ "colado" na consolidacao
ALVO_R = 3.0               # SAIDA validada: alvo fixo 3R (robusto, sem ilusao do trailing)
MAX_HOLD = 120

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def atr(h, l, c, n):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def indicadores(d):
    c, h, l = d["Close"], d["High"], d["Low"]
    d = d.copy()
    d["ema10"] = ema(c, 10); d["ema20"] = ema(c, 20)
    d["atr5"]  = atr(h, l, c, 5); d["atr20"] = atr(h, l, c, 20)
    # momentum: retorno em 21 / 63 / 126 pregoes (~1M/3M/6M)
    d["mom1"] = (c / c.shift(21) - 1.0) * 100.0
    d["mom3"] = (c / c.shift(63) - 1.0) * 100.0
    d["mom6"] = (c / c.shift(126) - 1.0) * 100.0
    return d

def eh_lider(row):
    """True se o ativo e um lider de momentum na data."""
    return ((row["mom1"] >= MOM_1M) or (row["mom3"] >= MOM_3M) or (row["mom6"] >= MOM_6M))

def consolidacao_ok(d, i):
    """Verifica se os candles ANTES de i formam uma consolidacao valida:
    volatilidade caindo E preco colado na EMA. Devolve (ok, topo_consol)."""
    # janela da consolidacao: procura a maior janela [CONSOL_MIN..CONSOL_MAX]
    # em que a amplitude fica contida e o preco fica perto da EMA.
    c, h, l = d["Close"], d["High"], d["Low"]
    melhor_topo = None
    for n in range(CONSOL_MAX, CONSOL_MIN - 1, -1):
        if i - n < 1: continue
        jan = slice(i - n, i)          # os n candles antes do candle i (rompimento)
        hh = h.iloc[jan].max(); ll = l.iloc[jan].min()
        ema20_med = d["ema20"].iloc[jan].mean()
        # volatilidade caindo
        if not (d["atr5"].iloc[i-1] < d["atr20"].iloc[i-1] * ATR_CONTRACAO): continue
        # preco colado na EMA20 (nao esticado): fecha a <=DIST_EMA_MAX da EMA20
        if ema20_med <= 0: continue
        dist = abs(c.iloc[i-1] - ema20_med) / ema20_med
        if dist > DIST_EMA_MAX: continue
        # a consolidacao nao pode ser um tombo: minima da janela acima da EMA20*0.90
        if ll < ema20_med * 0.90: continue
        melhor_topo = float(hh)
        break
    return (melhor_topo is not None), melhor_topo

def backtest(d, tk):
    d = indicadores(d)
    c, h, l = d["Close"], d["High"], d["Low"]
    n = len(d); trades = []; i = 130   # comeca depois de ter 6M de historico
    while i < n - 1:
        row = d.iloc[i]
        # 1) tem que ser LIDER de momentum
        if not eh_lider(row): i += 1; continue
        # 2) consolidacao valida logo antes
        ok, topo = consolidacao_ok(d, i)
        if not ok: i += 1; continue
        # 3) breakout: candle i rompe a maxima da consolidacao
        if not (float(h.iloc[i]) > topo): i += 1; continue
        # entrada realista: se abriu acima do topo (gap), entra na abertura;
        # senao, entra no topo (nivel do rompimento intradia).
        op_i = float(d["Open"].iloc[i])
        entry = max(topo, op_i)           # nao da pra entrar abaixo da abertura
        stop  = float(l.iloc[i])          # stop na minima do dia de rompimento
        risk  = entry - stop
        if risk <= 0: i += 1; continue
        # ---- SAIDA validada: alvo fixo 3R (o trailing era ilusao de backtest) ----
        alvo = entry + ALVO_R * risk; res = None; saiu = i + 1
        for j in range(i + 1, min(i + MAX_HOLD, n)):
            saiu = j
            lo = float(l.iloc[j]); hi = float(h.iloc[j])
            if lo <= stop: res = -1.0; break            # stop
            if hi >= alvo: res = ALVO_R; break          # alvo 3R
        if res is None:
            res = (float(c.iloc[min(i+MAX_HOLD, n-1)]) - entry) / risk
            saiu = min(i+MAX_HOLD, n-1)
        trades.append(res)
        i = saiu + 1
    return trades

def estat(rs):
    if not rs: return (0, 0.0, 0.0, 0.0, 0.0)
    N = len(rs); wr = 100*sum(1 for x in rs if x > 0)/N; exp = sum(rs)/N; acc = sum(rs)
    g = [x for x in rs if x > 0]; p = [x for x in rs if x <= 0]
    po = (np.mean(g)/abs(np.mean(p))) if g and p else 0.0
    return (N, wr, exp, acc, po)

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
        except Exception: pass
    todos = []
    for tk, d in dfs:
        try: todos += backtest(d, tk)
        except Exception: pass
    N, wr, exp, acc, po = estat(todos)
    print(f"BACKTEST QULLAMAGGIE | cesta '{a.pasta}' | {len(dfs)} ativos")
    print(f"Momentum: +{MOM_1M:.0f}%/1M ou +{MOM_3M:.0f}%/3M ou +{MOM_6M:.0f}%/6M | "
          f"consol {CONSOL_MIN}-{CONSOL_MAX}d")
    print(f"Entrada no rompimento | stop na minima do dia | alvo fixo {ALVO_R:.0f}R\n")
    print(f"  {'trades':>7}{'win':>7}{'exp':>10}{'acum':>11}{'payoff':>8}")
    print("  " + "-"*45)
    print(f"  {N:>7}{wr:>6.0f}%{exp:>+9.3f}R{acc:>+10.1f}R{po:>8.2f}")
    if N:
        print(f"\n  Leitura: {N} breakouts de lideres. "
              f"{'Expectancia POSITIVA — vale seguir testando.' if exp>0 else 'Expectancia negativa nesta cesta.'}")

if __name__ == "__main__":
    main()
