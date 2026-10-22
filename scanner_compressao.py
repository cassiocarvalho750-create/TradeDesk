#!/usr/bin/env python3
"""
============================================================================
SCANNER COMPRESSAO DIDI — lista diaria de ativos com as medias do DIDI
comprimidas, prestes a cruzar ou cruzando, A FAVOR da tendencia macro
============================================================================
LISTA DE OBSERVACAO (watchlist). NAO e regra de entrada testada em backtest.

Linhas do DIDI (a media de 8 e o eixo zero):
  curta = (MM3 / MM8 - 1) * 100      longa = (MM20 / MM8 - 1) * 100
  Agulhada de COMPRA: curta cruza o zero para CIMA e longa cruza para BAIXO.
  Agulhada de VENDA : curta cruza o zero para BAIXO e longa cruza para CIMA.

Compressao: abertura = maior - menor entre (curta, longa, 0), ou seja, a
distancia entre as tres medias em % do preco. Comparada com o proprio
historico do ativo (ultimos 120 pregoes): "comprimido" = abertura no menor
quintil (percentil <= 20%). Para quem ja cruzou, vale a menor abertura dos
ultimos 5 pregoes (a compressao veio antes do cruzamento).

Status (lado compra; venda e o espelho):
  AGULHADA       curta > 0 e longa < 0, as duas cruzaram nos ultimos 5 pregoes
                 e a mais recente hoje ou ontem
  CRUZANDO       uma das linhas cruzou o zero hoje ou ontem no sentido certo e
                 a outra vem em direcao a ele
  PRESTES        comprimido hoje, curta abaixo do zero e subindo (vs 2 pregoes),
                 longa ainda acima do zero: falta a agulhada acontecer

Filtro de tendencia macro (EMA 200 e EMA 70, inclinacao vs 10 pregoes atras,
minimo de 0,10% nesses 10 pregoes para nao pegar media praticamente reta):
  Bloco COMPRA: fechamento > EMA200, EMA200 subindo e EMA70 subindo
  Bloco VENDA : fechamento < EMA200, EMA200 caindo  e EMA70 caindo

USO:
  python scanner_compressao.py              # universo completo (B3 + EUA)
  python scanner_compressao.py --quick
  python scanner_compressao.py --market us
Gera painel_compressao.json.
============================================================================
"""
import argparse, datetime, json
import numpy as np, pandas as pd

HIST_COMP = 120        # pregoes para o percentil da abertura
PCT_COMP = 0.20        # comprimido = abertura entre os 20% menores dos ultimos 120 pregoes
JAN_AGU = 5            # janela das duas cruzadas da agulhada
JAN_REC = 2            # cruzamento "recente": hoje ou ontem
INCL_LB = 10           # inclinacao das EMAs: hoje vs 10 pregoes atras
INCL_MIN = 0.10        # inclinacao minima (%) em 10 pregoes para contar como inclinada (corta EMA quase reta)
SPARK = 40             # pregoes no mini-grafico


def ema(s, n): return s.ewm(span=n, adjust=False).mean()


def linhas_didi(c):
    m3 = c.rolling(3).mean(); m8 = c.rolling(8).mean(); m20 = c.rolling(20).mean()
    curta = (m3 / m8 - 1.0) * 100.0
    longa = (m20 / m8 - 1.0) * 100.0
    ab = pd.concat([curta, longa, curta * 0], axis=1)
    abertura = ab.max(axis=1) - ab.min(axis=1)
    return curta, longa, abertura


def _ultimo_cruz(x, i, para_cima, jan):
    """Ha quantos pregoes (0 = hoje) a serie x cruzou o zero no sentido pedido, dentro de jan. None se nao cruzou."""
    for k in range(jan):
        j = i - k
        if j < 1: break
        if para_cima and x[j] > 0 and x[j-1] <= 0: return k
        if not para_cima and x[j] < 0 and x[j-1] >= 0: return k
    return None


def prepara(d):
    c = d["Close"]
    curta_s, longa_s, ab_s = linhas_didi(c)
    return {"cu": curta_s.values, "lo": longa_s.values, "ab": ab_s.values,
            "e200": ema(c, 200).values, "e70": ema(c, 70).values, "cl": c.values}


def avalia(d, i=None, pre=None):
    """Avalia o ativo no candle i (padrao: ultimo). Devolve dict ou None.
    pre: resultado de prepara(d), para reaproveitar em varios candles (backtest)."""
    n = len(d)
    if i is None: i = n - 1
    if i < 220: return None
    p = pre or prepara(d)
    cu, lo, ab, e200, e70, cl = p["cu"], p["lo"], p["ab"], p["e200"], p["e70"], p["cl"]
    if np.isnan(cu[i]) or np.isnan(lo[i]): return None

    # percentil da abertura de hoje e o menor dos ultimos 5 dentro da janela de 120
    jan = ab[i-HIST_COMP+1:i+1]
    pct = lambda v: float((jan <= v).mean())
    pct_hoje = pct(ab[i])
    pct_min5 = min(pct(ab[i-k]) for k in range(JAN_AGU))
    comp_hoje = pct_hoje <= PCT_COMP
    comp_rec = pct_min5 <= PCT_COMP

    inc200 = (e200[i] / e200[i-INCL_LB] - 1) * 100; inc70 = (e70[i] / e70[i-INCL_LB] - 1) * 100
    sobe200 = inc200 >= INCL_MIN; sobe70 = inc70 >= INCL_MIN
    desce200 = inc200 <= -INCL_MIN; desce70 = inc70 <= -INCL_MIN

    lado = None
    if cl[i] > e200[i] and sobe200 and sobe70: lado = "compra"
    elif cl[i] < e200[i] and desce200 and desce70: lado = "venda"
    if lado is None: return None

    s = 1 if lado == "compra" else -1          # espelha a venda: trabalha com s*curta, s*longa
    a = s * cu; b = s * lo                     # compra: a cruza p/ cima, b p/ baixo
    k_a = _ultimo_cruz(a, i, True, JAN_AGU)
    k_b = _ultimo_cruz(b, i, False, JAN_AGU)
    a_sobe = a[i] > a[i-2]; b_desce = b[i] < b[i-2]

    status = None; dias = None; qual = None
    if a[i] > 0 and b[i] < 0 and k_a is not None and k_b is not None and min(k_a, k_b) < JAN_REC and comp_rec:
        status = "AGULHADA"; dias = min(k_a, k_b)
    elif comp_rec and k_a is not None and k_a < JAN_REC and a[i] > 0 and b[i] >= 0 and b_desce:
        status = "CRUZANDO"; dias = k_a; qual = "curta"         # curta ja cruzou; longa descendo para o zero
    elif comp_rec and k_b is not None and k_b < JAN_REC and b[i] < 0 and a[i] <= 0 and a_sobe:
        status = "CRUZANDO"; dias = k_b; qual = "longa"         # longa ja cruzou; curta subindo para o zero
    elif comp_hoje and a[i] <= 0 and a_sobe and b[i] >= 0:
        status = "PRESTES"; dias = None
    if status is None: return None

    m3 = (cl[i] / cl[i-63] - 1) * 100 if i >= 63 else np.nan
    ini = max(0, i - SPARK + 1)
    r2 = lambda v: None if (v is None or not np.isfinite(v)) else round(float(v), 3)
    return {
        "lado": lado, "status": status, "dias": dias, "qual": qual,
        "data": d.index[i].strftime("%Y-%m-%d"),
        "close": round(float(cl[i]), 2),
        "curta": r2(cu[i]), "longa": r2(lo[i]), "abertura": r2(ab[i]),
        "abertura_pct": round(pct_hoje * 100), "abertura_min5_pct": round(pct_min5 * 100),
        "ema70": round(float(e70[i]), 2), "ema200": round(float(e200[i]), 2),
        "dist_ema200": round((cl[i] / e200[i] - 1) * 100, 1),
        "incl_ema200": round((e200[i] / e200[i-INCL_LB] - 1) * 100, 2),
        "incl_ema70": round((e70[i] / e70[i-INCL_LB] - 1) * 100, 2),
        "mom3": None if np.isnan(m3) else round(float(m3)),
        "spark_curta": [r2(v) for v in cu[ini:i+1]],
        "spark_longa": [r2(v) for v in lo[ini:i+1]],
    }


ORDEM_ST = {"AGULHADA": 0, "CRUZANDO": 1, "PRESTES": 2}


def chave(x):
    # status; depois a mais comprimida primeiro; depois a mais longe da EMA200 a favor
    return (ORDEM_ST[x["status"]], x["abertura_min5_pct"] if x["status"] != "PRESTES" else x["abertura_pct"],
            -abs(x["dist_ema200"]))


def main():
    import scanner as sc
    import run_backtest_v2 as rb
    try:
        from registro_sinais import _mercado_fechado
    except Exception:
        _mercado_fechado = lambda m: False

    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--market", choices=["b3", "us", "all"], default="all")
    ap.add_argument("--chunk", type=int, default=100)
    a = ap.parse_args()

    # 2 anos de historico: EMA200 bem assentada e 120 pregoes para o percentil
    sc.TF_CONFIG["1d"] = ("1d", "2y", None)

    uni = rb.get_universe(quick=a.quick)
    if a.market == "b3": uni = [t for t in uni if t.endswith(".SA")]
    elif a.market == "us": uni = [t for t in uni if not t.endswith(".SA")]
    print(f"Scanner COMPRESSAO DIDI | {len(uni)} ativos\n")

    US_MIN = float(getattr(rb, "US_MIN_VOL_FIN_MI", 5.0)); B3_MIN = float(getattr(rb, "B3_MIN_VOL_FIN_MI", 5.0))
    dados = sc.fetch_batch(uni, timeframe="1d", chunk=a.chunk)
    hoje = pd.Timestamp(datetime.date.today())
    hits = []; funil = {"total": 0, "liquidos": 0, "compra": 0, "venda": 0}
    for tk, d in dados.items():
        d = d.dropna(subset=["Close"])
        if d is None or len(d) < 230: continue
        funil["total"] += 1
        try:
            if not sc._liquidez_ok(tk, d, US_MIN, B3_MIN): continue
            funil["liquidos"] += 1
            r = avalia(d)
            if not r: continue
            market = "B3" if tk.endswith(".SA") else "EUA"
            r.update(ticker=tk, market=market, tv=sc.tv_url(tk),
                     forming=bool(d.index[-1].normalize() == hoje and not _mercado_fechado(market)))
            funil[r["lado"]] += 1
            hits.append(r)
        except Exception as e:
            print(f"  [erro] {tk}: {e}")

    hits.sort(key=chave)
    print(f"\n  [funil] {funil}\n")
    for lado in ("compra", "venda"):
        print(f"  ---- {lado.upper()} ----")
        for x in [h for h in hits if h["lado"] == lado]:
            dd = "" if x["dias"] is None else f" ha {x['dias']}d"
            print(f"  {x['ticker'].replace('.SA',''):<10}{x['status']+dd:<16}abertura p{x['abertura_pct']:<4}"
                  f"curta {x['curta']:+.2f}  longa {x['longa']:+.2f}  EMA200 {x['dist_ema200']:+.1f}%")

    payload = {"gerado": datetime.date.today().isoformat(),
               "gerado_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "params": {"hist_comp": HIST_COMP, "pct_comp": PCT_COMP, "jan_agulhada": JAN_AGU,
                          "jan_recente": JAN_REC, "incl_lb": INCL_LB, "incl_min": INCL_MIN},
               "funil": funil, "n": len(hits), "ativos": hits}
    open("painel_compressao.json", "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
    print("  JSON: painel_compressao.json")


if __name__ == "__main__":
    main()
