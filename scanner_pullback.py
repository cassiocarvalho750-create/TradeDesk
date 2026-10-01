#!/usr/bin/env python3
"""
============================================================================
SCANNER PULLBACK EMA20 — primeiro toque na EMA20 com candle de forca
============================================================================
Setup estudado no backtest_pullback_mm.py / backtest_pullback_saidas.py (out/2026):
  1) MERCADO: indice acima da media simples de 200 dias
       EUA -> QQQ (validado no backtest) | B3 -> IBOV (mesma regra, NAO testada)
  2) TENDENCIA: EMA10 > EMA20 > EMA50 e EMA50 de hoje > EMA50 de 10 pregoes atras
  3) PRIMEIRO TOQUE: minima de D-1 ou D tocou a EMA20 e D fechou acima dela;
     nenhuma minima tocou a EMA20 nos 10 pregoes anteriores (D-11 .. D-2)
  4) GATILHO: D fechou acima da maxima de D-1 (candle de forca)
Execucao: compra stop em max(D)+0,01, valida SO no pregao seguinte (abriu acima ->
entra na abertura). Stop = min(minima D-1, minima D). Saida: metade em 3R (stop do
resto vai para a entrada) e o resto sai na abertura seguinte a um fechamento abaixo
da EMA20.

Status de cada linha:
  ORDEM     -> o candle do sinal ja FECHOU. A ordem vale no proximo pregao
               (ou HOJE, se o pregao de hoje ja esta aberto).
  FORMANDO  -> o candle de hoje (ainda aberto) cumpre o setup ate agora.
               So vira sinal se continuar assim no fechamento.

USO:
  python scanner_pullback.py            # universo completo (B3 + EUA)
  python scanner_pullback.py --quick    # teste rapido
  python scanner_pullback.py --market us
Gera painel_pullback.json e grava historico_pullback.csv (forward test).
============================================================================
"""
import argparse, datetime, json, os, csv
import numpy as np, pandas as pd

TOQUES_JANELA = 10       # pregoes antes do toque sem encostar na EMA20
EMA50_LOOKBACK = 10      # EMA50 subindo: hoje > 10 pregoes atras
ALVO_R = 3.0             # parcial (metade) em 3R
TICK = 0.01
INDICES = {"EUA": ("QQQ", "QQQ", True), "B3": ("^BVSP", "IBOV", False)}   # (yahoo, nome, validado?)
DIR = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(DIR, "historico_pullback.csv")


def ema(s, n): return s.ewm(span=n, adjust=False).mean()


def sinal_em(d, i, e10, e20, e50):
    """Avalia o setup com o candle i como candle de gatilho. Devolve dict ou None.
    Mesma regra do backtest (pullback_mm.py / pullback_saidas.py)."""
    if i < 60 or i >= len(d): return None
    h = d["High"].values; l = d["Low"].values; c = d["Close"].values
    if not (e10[i] > e20[i] > e50[i] and e50[i] > e50[i-EMA50_LOOKBACK]):
        return None
    lo2 = min(l[i-1], l[i])
    if not (lo2 <= e20[i] and c[i] > e20[i]): return None          # tocou e fechou acima
    if not (c[i] > h[i-1]): return None                             # candle de forca
    if np.any(l[i-1-TOQUES_JANELA:i-1] <= e20[i-1-TOQUES_JANELA:i-1]):  # 1o toque
        return None
    entrada = round(float(h[i]) + TICK, 2)
    stop = round(float(lo2), 2)
    risk = entrada - stop
    if risk <= 0: return None
    m3 = (c[i]/c[i-63]-1)*100 if i >= 63 else np.nan
    return {
        "data_sinal": d.index[i].strftime("%Y-%m-%d"),
        "entrada": entrada, "stop": stop,
        "alvo_3r": round(entrada + ALVO_R*risk, 2),
        "r_pct": round(risk/entrada*100, 2),
        "preco": round(float(c[i]), 2),
        "ema20": round(float(e20[i]), 2),
        "mom3": None if np.isnan(m3) else round(float(m3), 0),
        "mom_fraco": bool(not np.isnan(m3) and 10 <= m3 < 30),   # faixa mais fraca no backtest
    }


def indice_ok(serie_idx, data):
    """True/False se o indice fechou acima da MM200 na data (ou no ultimo dia ate ela)."""
    if serie_idx is None or len(serie_idx) < 200: return None
    mm = serie_idx.rolling(200).mean()
    s = serie_idx.loc[:pd.Timestamp(data)]
    if s.empty or np.isnan(mm.loc[s.index[-1]]): return None
    return bool(s.iloc[-1] > mm.loc[s.index[-1]])


def avalia(tk, d, market, idx_close, hoje, forming, funil=None):
    """Devolve a lista de linhas (0, 1 ou 2) do ativo: ORDEM e/ou FORMANDO."""
    def conta(k):
        if funil is not None: funil[k] = funil.get(k, 0) + 1
    if len(d) < 80: conta("hist_curto"); return []
    c = d["Close"]
    e10 = ema(c, 10).values; e20 = ema(c, 20).values; e50 = ema(c, 50).values
    n = len(d); out = []
    i_fech = n-2 if forming else n-1          # ultimo candle FECHADO
    s = sinal_em(d, i_fech, e10, e20, e50)
    if s:
        s["status"] = "ORDEM"
        if forming:
            # a ordem vale HOJE: ve o que o pregao de hoje ja fez
            o, hh, ll = float(d["Open"].iloc[-1]), float(d["High"].iloc[-1]), float(d["Low"].iloc[-1])
            s["ordem_dia"] = "hoje"
            if o > s["entrada"]: s["execucao"] = "abriu acima"
            elif hh >= s["entrada"]: s["execucao"] = "ativada"
            else: s["execucao"] = "aguardando"
            s["stop_tocado"] = bool(s["execucao"] != "aguardando" and ll <= s["stop"])
            s["preco"] = round(float(c.iloc[-1]), 2)
        else:
            s["ordem_dia"] = "próximo pregão"; s["execucao"] = "aguardando"; s["stop_tocado"] = False
        out.append(s)
    if forming:
        f = sinal_em(d, n-1, e10, e20, e50)
        if f:
            f["status"] = "FORMANDO"; f["ordem_dia"] = "amanhã, se confirmar"; f["execucao"] = "—"; f["stop_tocado"] = False
            out.append(f)
    for r in out:
        r["mercado_ok"] = indice_ok(idx_close, r["data_sinal"])
        r["indice"] = INDICES[market][1]
    if out: conta("sinais")
    return out


def registrar(linhas):
    """Forward test: grava os sinais de candle FECHADO (status ORDEM), sem duplicar (data_sinal,ticker)."""
    campos = ["data_sinal", "ticker", "market", "entrada", "stop", "alvo_3r", "r_pct",
              "mom3", "mercado_ok", "indice", "registrado_em"]
    ja = set()
    if os.path.exists(HIST):
        with open(HIST, encoding="utf-8") as f:
            for r in csv.DictReader(f): ja.add((r["data_sinal"], r["ticker"]))
    novos = [x for x in linhas if x["status"] == "ORDEM" and (x["data_sinal"], x["ticker"]) not in ja]
    novo_arq = not os.path.exists(HIST)
    with open(HIST, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if novo_arq: w.writeheader()
        agora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        for x in novos: w.writerow({**x, "registrado_em": agora})
    print(f"  [registro Pullback] +{len(novos)} sinais em historico_pullback.csv")


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

    uni = rb.get_universe(quick=a.quick)
    if a.market == "b3": uni = [t for t in uni if t.endswith(".SA")]
    elif a.market == "us": uni = [t for t in uni if not t.endswith(".SA")]
    print(f"Scanner PULLBACK EMA20 | {len(uni)} ativos\n")

    # indices para o filtro de mercado
    idx = sc.fetch_batch([v[0] for v in INDICES.values()], timeframe="1d", chunk=10)
    idx_close = {m: (idx[v[0]]["Close"].dropna() if v[0] in idx else None) for m, v in INDICES.items()}
    mercado = {}
    for m, (yh, nome, validado) in INDICES.items():
        s = idx_close[m]
        if s is not None and len(s) >= 200:
            mm = float(s.rolling(200).mean().iloc[-1]); fc = float(s.iloc[-1])
            mercado[m] = {"indice": nome, "ok": fc > mm, "close": round(fc, 2), "mm200": round(mm, 2), "validado": validado}
        else:
            mercado[m] = {"indice": nome, "ok": None, "close": None, "mm200": None, "validado": validado}
        print(f"  [mercado] {nome}: {mercado[m]}")

    US_MIN = float(getattr(rb, "US_MIN_VOL_FIN_MI", 5.0)); B3_MIN = float(getattr(rb, "B3_MIN_VOL_FIN_MI", 5.0))
    dados = sc.fetch_batch(uni, timeframe="1d", chunk=a.chunk)
    hoje = pd.Timestamp(datetime.date.today())
    hits = []; funil = {"total": 0, "liquidos": 0}
    for tk, d in dados.items():
        if d is None or len(d) < 80: continue
        funil["total"] += 1
        try:
            if not sc._liquidez_ok(tk, d, US_MIN, B3_MIN): continue
            funil["liquidos"] += 1
            market = "B3" if tk.endswith(".SA") else "EUA"
            forming = bool(d.index[-1].normalize() == hoje and not _mercado_fechado(market))
            for r in avalia(tk, d, market, idx_close[market], hoje, forming, funil):
                r.update(ticker=tk, market=market, tv=sc.tv_url(tk), forming=forming)
                hits.append(r)
        except Exception as e:
            print(f"  [erro] {tk}: {e}")

    # ordem: mercado liberado, ORDEM antes de FORMANDO, faixa de momentum fraca por ultimo, maior momentum
    hits.sort(key=lambda x: (x["mercado_ok"] is not True, x["status"] != "ORDEM", x["mom_fraco"], -(x["mom3"] or 0)))

    print(f"\n  [funil] {funil['total']} ativos | {funil['liquidos']} liquidos | {len(hits)} linhas\n")
    print("=" * 78)
    print(f"  {'ATIVO':<10}{'STATUS':<10}{'EXECUCAO':<13}{'ENTRADA':>9}{'STOP':>9}{'3R':>9}{'R%':>6}{'3M':>6}  MERC")
    for x in hits:
        m3 = f"{x['mom3']:+.0f}%" if x["mom3"] is not None else "—"
        mk = {True: "ok", False: "DESLIG.", None: "?"}[x["mercado_ok"]]
        print(f"  {x['ticker'].replace('.SA',''):<10}{x['status']:<10}{x['execucao']:<13}{x['entrada']:>9}{x['stop']:>9}"
              f"{x['alvo_3r']:>9}{x['r_pct']:>5.1f}%{m3:>6}  {mk}")
    print("=" * 78)

    payload = {"gerado": datetime.date.today().isoformat(),
               "gerado_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "mercado": mercado, "funil": funil, "n": len(hits), "ativos": hits}
    open("painel_pullback.json", "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
    print("  JSON: painel_pullback.json")
    try:
        registrar(hits)
    except Exception as e:
        print(f"  [registro Pullback] falhou: {e}")


if __name__ == "__main__":
    main()
