#!/usr/bin/env python3
"""
============================================================================
BACKTEST — AGULHADA DO DIDI x HUMOR DO S&P 500
============================================================================
Ideia (do Cassio): "minhas compras boas vem em mares". O S&P 500 funciona
como termometro do humor do mercado. Este teste separa CADA trade da
Agulhada do Didi em dois grupos, conforme o humor do S&P 500 NA DATA DE
ENTRADA:

  BOM HUMOR  -> no S&P 500, a media 3 do Didi esta ACIMA da media 8 (didi3>0)
  MAU HUMOR  -> no S&P 500, a media 3 do Didi esta ABAIXO da media 8 (didi3<0)

Assim da pra ver, na pratica, se vale a pena se dedicar as compras quando o
S&P 500 esta de bom humor e ficar de fora quando esta de mau humor.

A estrategia de cada trade e a MESMA que ja validamos:
  entrada = fechamento do candle de sinal (mesma logica do scanner)
  stop    = pivo de baixa 3x3
  saida   = parcial 50% em 2R + breakeven no resto + resto sai na venda do TRIX

Nada muda no setup — a UNICA diferenca entre os grupos e o humor do S&P 500
no dia da entrada.

----------------------------------------------------------------------------
COMO RODAR (no seu PC, onde estao as pastas de precos):

  1) Deixe um arquivo do S&P 500 chamado  sp500.csv  na mesma pasta,
     com colunas: date,open,high,low,close,volume  (igual as suas cestas).
     - Pode exportar do TradingView (simbolo SP:SPX ou SPX) ou usar SPY.
     - Se voce NAO tiver o arquivo, o script tenta baixar ^GSPC pelo
       yfinance automaticamente (precisa de internet).

  2) Rode apontando para a cesta de precos que quer testar:

       python backtest_didi_humor.py prices_todos
       python backtest_didi_humor.py prices_todos --sp500 sp500.csv

     (se omitir a pasta, usa 'prices')

Gera no terminal a comparacao BOM HUMOR x MAU HUMOR x GERAL, e salva
backtest_humor_sp500.csv com um trade por linha (data, ativo, humor, R).
============================================================================
"""
import glob, sys, os, argparse
import numpy as np, pandas as pd
import bt_engine as bt
import backtest_didi as bd   # reaproveita carrega(), swings_low(), trix_ema()

# ------------------------------------------------------------------ S&P 500
def carrega_sp500(caminho):
    """Le o CSV do S&P 500 no mesmo formato das cestas e devolve:
      bom    -> Series booleana: MA3 do Didi acima da MA8 (didi3 > 0) = bom humor
      didi3  -> valor de (MA3/MA8-1)*100
      incl   -> inclinacao da MA3 (ma3 hoje - ma3 ontem): >0 sobe, <0 desce"""
    d = bd.carrega(caminho)
    c = d["Close"]
    ma3 = c.rolling(3).mean()
    ma8 = c.rolling(8).mean()
    didi3 = (ma3 / ma8 - 1.0) * 100.0     # >0  -> MA3 acima da MA8  -> bom humor
    incl = ma3.diff()                      # ma3 hoje - ma3 ontem
    return (didi3 > 0), didi3, incl

def baixa_sp500():
    """Fallback: baixa o ^GSPC pelo yfinance e devolve no mesmo formato."""
    import yfinance as yf
    d = yf.Ticker("^GSPC").history(period="10y", interval="1d", auto_adjust=True)
    if d is None or d.empty:
        raise RuntimeError("Nao consegui baixar o ^GSPC pelo yfinance.")
    d.columns = [x.lower() for x in d.columns]
    if d.index.tz is not None: d.index = d.index.tz_localize(None)
    c = d["close"]
    ma3 = c.rolling(3).mean(); ma8 = c.rolling(8).mean()
    didi3 = (ma3 / ma8 - 1.0) * 100.0
    incl = ma3.diff()
    return (didi3 > 0), didi3, incl

def humor_na_data(bom_humor, didi3_sp, incl_sp, data):
    """Humor do S&P 500 valido ATE a data de entrada (usa o ultimo pregao do
    S&P 500 <= data do trade — evita olhar o futuro e resolve feriados que
    caem em um mercado e nao no outro). Retorna (bom?, valor_didi3, inclinacao):
      bom?        -> True (MA3>MA8), False (MA3<MA8) ou None (sem dado)
      valor_didi3 -> o quanto a MA3 esta acima/abaixo da MA8, em % (float)
      inclinacao  -> ma3 hoje - ma3 ontem: >0 subindo, <0 descendo (float)"""
    idx = bom_humor.index
    validos = idx[idx <= data]
    if len(validos) == 0:
        return None, None, None
    ref = validos[-1]
    v = bom_humor.loc[ref]; d3 = didi3_sp.loc[ref]; inc = incl_sp.loc[ref]
    if pd.isna(v) or pd.isna(d3):
        return None, None, None
    inc = None if pd.isna(inc) else float(inc)
    return bool(v), float(d3), inc

# ------------------------------------------------------- backtest com humor
def backtest_com_humor(d, tk, bom_humor, didi3_sp, incl_sp, max_hold=120):
    """Igual ao bd.backtest com stop='pivo' e saida='trix', mas devolve, para
    cada trade, a DATA de entrada, o R e o humor do S&P 500 nessa data."""
    s = bt.compute_signals_windowed(d)
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    trix, sinal = bd.trix_ema(c)
    trix_venda = (trix < sinal) & (trix.shift(1) >= sinal.shift(1))
    n = len(d); trades = []
    i = 60
    while i < n - 1:
        if not bool(s["signal_win"].iloc[i]): i += 1; continue
        entry = float(c.iloc[i])
        sp = bd.swings_low(h, l, i, 3)
        stop = sp if sp is not None else float(l.iloc[i])
        risk = entry - stop
        if risk <= 0: i += 1; continue
        data_ent = d.index[i]
        alvo1 = entry + 2 * risk; p1 = None; p2 = None; st = stop
        saiu_em = i + 1
        for j in range(i + 1, min(i + max_hold, n)):
            saiu_em = j
            lo = float(l.iloc[j]); hi = float(h.iloc[j])
            if p1 is None:
                if lo <= st: p1 = -1.0; p2 = -1.0; break
                if hi >= alvo1: p1 = 2.0; st = entry
            if p1 is not None and p2 is None:
                if lo <= st: p2 = 0.0 if st == entry else -1.0; break
                if bool(trix_venda.iloc[j]): p2 = (float(c.iloc[j]) - entry) / risk; break
        if p1 is None:
            fim = (float(c.iloc[min(i + max_hold, n - 1)]) - entry) / risk
            p1 = fim; p2 = fim; saiu_em = min(i + max_hold, n - 1)
        elif p2 is None:
            p2 = (float(c.iloc[min(i + max_hold, n - 1)]) - entry) / risk
            saiu_em = min(i + max_hold, n - 1)
        r = 0.5 * p1 + 0.5 * p2
        humor, d3, inc = humor_na_data(bom_humor, didi3_sp, incl_sp, data_ent)
        trades.append({"ticker": tk, "data": data_ent, "R": r,
                       "humor": humor, "didi3_sp": d3, "incl_sp": inc})
        i = saiu_em + 1
    return trades

# ------------------------------------------------------------- estatisticas
def estat(rs):
    if not rs: return (0, 0.0, 0.0, 0.0, 0.0)
    N = len(rs)
    wr = 100 * sum(1 for x in rs if x > 0) / N
    exp = sum(rs) / N
    acc = sum(rs)
    # payoff = media dos ganhos / media (abs) das perdas
    g = [x for x in rs if x > 0]; p = [x for x in rs if x <= 0]
    payoff = (np.mean(g) / abs(np.mean(p))) if g and p else 0.0
    return (N, wr, exp, acc, payoff)

def linha(nome, rs):
    N, wr, exp, acc, po = estat(rs)
    return f"  {nome:<14}{N:>7}{wr:>6.0f}%{exp:>+9.3f}R{acc:>+9.1f}R{po:>8.2f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", nargs="?", default="prices",
                    help="pasta com os CSV dos ativos (ex.: prices_todos)")
    ap.add_argument("--sp500", default="sp500.csv",
                    help="CSV do S&P 500 (date,open,high,low,close,volume). "
                         "Se nao existir, baixa ^GSPC pelo yfinance.")
    ap.add_argument("--out", default="backtest_humor_sp500.csv")
    a = ap.parse_args()

    # --- humor do S&P 500 ---
    if os.path.exists(a.sp500):
        bom_humor, didi3_sp, incl_sp = carrega_sp500(a.sp500)
        origem = f"arquivo '{a.sp500}'"
    else:
        print(f"[i] '{a.sp500}' nao encontrado — tentando baixar ^GSPC pelo yfinance...")
        try:
            bom_humor, didi3_sp, incl_sp = baixa_sp500()
            origem = "yfinance (^GSPC)"
        except Exception as e:
            print(f"[X] Nao foi possivel obter o S&P 500: {e}")
            print("    Exporte o S&P 500 (SPX ou SPY) para sp500.csv e rode de novo.")
            sys.exit(1)

    ini = bom_humor.index.min().date(); fim = bom_humor.index.max().date()
    pct_bom = 100 * bom_humor.dropna().mean()
    print(f"S&P 500 (humor) | fonte: {origem}")
    print(f"  periodo do S&P 500: {ini} a {fim}")
    print(f"  dias de BOM humor (MA3>MA8): {pct_bom:.0f}%  |  MAU humor: {100-pct_bom:.0f}%\n")

    # --- carrega a cesta ---
    arqs = sorted(glob.glob(f"{a.pasta}/*.csv"))
    dfs = []
    for arq in arqs:
        tk = os.path.basename(arq).replace(".csv", "").upper()
        if tk == "SP500": continue   # nao opera o proprio indice
        try:
            d = bd.carrega(arq)
            if len(d) >= 150: dfs.append((tk, d))
        except Exception:
            pass

    todos = []
    for tk, d in dfs:
        try: todos += backtest_com_humor(d, tk, bom_humor, didi3_sp, incl_sp)
        except Exception: pass

    bom = [t["R"] for t in todos if t["humor"] is True]
    mau = [t["R"] for t in todos if t["humor"] is False]
    ger = [t["R"] for t in todos]
    semdado = sum(1 for t in todos if t["humor"] is None)

    print(f"Backtest AGULHADA DO DIDI x HUMOR DO S&P 500 | cesta '{a.pasta}' | {len(dfs)} ativos")
    print(f"Estrategia: entrada no fechamento | stop pivo 3x3 | parcial 2R + BE + saida TRIX\n")
    print(f"  {'grupo':<14}{'trades':>7}{'win':>7}{'exp':>10}{'acum':>10}{'payoff':>8}")
    print("  " + "-" * 54)
    print(linha("BOM HUMOR", bom))
    print(linha("MAU HUMOR", mau))
    print("  " + "-" * 54)
    print(linha("GERAL", ger))
    if semdado:
        print(f"\n  ({semdado} trade(s) fora do periodo do S&P 500 — sem classificacao)")

    # --- FORCA do humor: quebra bom e mau pela mediana do didi3 de cada lado ---
    # Corte pela MEDIANA de cada lado -> "forte" e "fraco" ficam com ~metade dos
    # trades cada, entao a comparacao e justa (nao e amostra grande vs pequena).
    bom_t = [t for t in todos if t["humor"] is True and t["didi3_sp"] is not None]
    mau_t = [t for t in todos if t["humor"] is False and t["didi3_sp"] is not None]
    if bom_t and mau_t:
        med_bom = float(np.median([t["didi3_sp"] for t in bom_t]))   # >0
        med_mau = float(np.median([t["didi3_sp"] for t in mau_t]))   # <0
        bom_forte = [t["R"] for t in bom_t if t["didi3_sp"] >= med_bom]  # bem acima de 0
        bom_fraco = [t["R"] for t in bom_t if t["didi3_sp"] <  med_bom]  # colado em 0
        mau_fraco = [t["R"] for t in mau_t if t["didi3_sp"] >= med_mau]  # colado em 0 (pouco negativo)
        mau_forte = [t["R"] for t in mau_t if t["didi3_sp"] <  med_mau]  # bem abaixo de 0
        print(f"\n  FORCA DO HUMOR (corte na mediana do didi3 do S&P de cada lado):")
        print(f"  bom: forte = didi3>= {med_bom:+.2f} | fraco = 0..{med_bom:+.2f}   "
              f"mau: fraco = {med_mau:+.2f}..0 | forte = didi3< {med_mau:+.2f}")
        print(f"  {'grupo':<14}{'trades':>7}{'win':>7}{'exp':>10}{'acum':>10}{'payoff':>8}")
        print("  " + "-" * 54)
        print(linha("BOM FORTE", bom_forte))
        print(linha("BOM FRACO", bom_fraco))
        print(linha("MAU FRACO", mau_fraco))
        print(linha("MAU FORTE", mau_forte))
        _, _, e_bf, _, _ = estat(bom_forte)
        _, _, e_bw, _, _ = estat(bom_fraco)
        print("\n  LEITURA (forca):")
        if e_bf > e_bw:
            print(f"  - O bom humor FORTE (S&P bem esticado p/ cima) rende {e_bf:+.3f}R/trade,")
            print(f"    contra {e_bw:+.3f}R do bom humor fraco. Acelerar quando o S&P esta")
            print(f"    claramente comprado tem base — a diferenca e de {e_bf-e_bw:+.3f}R.")
        else:
            print(f"  - Aqui o bom humor forte NAO rendeu mais que o fraco "
                  f"({e_bf:+.3f}R vs {e_bw:+.3f}R):")
            print(f"    a intensidade do humor nao ajuda a prever — nao vale acelerar por isso.")

    # --- INCLINACAO da MA3 do S&P (subindo x descendo), medida hoje vs ontem ---
    # Diferente da POSICAO (acima/abaixo da 8): aqui e a DIRECAO da MA3.
    # A MA3 pode estar acima da 8 (bom humor) mas ja virando p/ baixo — sinal
    # de mare comecando a virar.
    subindo  = [t["R"] for t in todos if t.get("incl_sp") is not None and t["incl_sp"] > 0]
    descendo = [t["R"] for t in todos if t.get("incl_sp") is not None and t["incl_sp"] < 0]
    if subindo and descendo:
        print(f"\n  INCLINACAO DA MA3 DO S&P (media 3 hoje vs ontem):")
        print(f"  {'grupo':<14}{'trades':>7}{'win':>7}{'exp':>10}{'acum':>10}{'payoff':>8}")
        print("  " + "-" * 54)
        print(linha("MA3 SUBINDO", subindo))
        print(linha("MA3 DESCENDO", descendo))
        _, _, e_up, _, _ = estat(subindo)
        _, _, e_dn, _, _ = estat(descendo)
        print("\n  LEITURA (inclinacao):")
        if e_up > e_dn:
            print(f"  - Comprar com a MA3 do S&P SUBINDO rende {e_up:+.3f}R/trade, contra")
            print(f"    {e_dn:+.3f}R com ela descendo. A direcao do S&P ajuda "
                  f"(+{e_up-e_dn:.3f}R a favor de subir).")
        else:
            print(f"  - Aqui a MA3 DESCENDO rendeu tanto quanto ou mais "
                  f"({e_dn:+.3f}R vs {e_up:+.3f}R):")
            print(f"    a direcao da MA3 nao separou nesta amostra.")

        # cruzamento POSICAO x DIRECAO: bom humor ainda subindo x bom humor ja virando
        bom_up = [t["R"] for t in todos if t["humor"] is True and t.get("incl_sp") and t["incl_sp"] > 0]
        bom_dn = [t["R"] for t in todos if t["humor"] is True and t.get("incl_sp") and t["incl_sp"] < 0]
        if bom_up and bom_dn:
            print(f"\n  CRUZAMENTO (dentro do BOM humor):")
            print(f"  {'grupo':<18}{'trades':>7}{'win':>7}{'exp':>10}{'acum':>10}")
            print("  " + "-" * 52)
            _, wu, eu, au, _ = estat(bom_up)
            _, wd, ed, ad, _ = estat(bom_dn)
            print(f"  {'bom + subindo':<18}{len(bom_up):>7}{wu:>6.0f}%{eu:>+9.3f}R{au:>+9.1f}R")
            print(f"  {'bom + descendo':<18}{len(bom_dn):>7}{wd:>6.0f}%{ed:>+9.3f}R{ad:>+9.1f}R")
            if eu > ed:
                print(f"  -> No bom humor, a MA3 AINDA subindo rende mais ({eu:+.3f}R vs {ed:+.3f}R):")
                print(f"     vale evitar quando o bom humor ja esta virando p/ baixo.")

    # --- MARE CHEIA DE VERDADE: combina FORCA + DIRECAO ---
    # bom humor FORTE (didi3 >= +0,70) E com a MA3 SUBINDO, contra o resto.
    LIM = 0.70
    def _class(t):
        d3 = t.get("didi3_sp"); inc = t.get("incl_sp")
        if d3 is None or inc is None: return None
        return (d3 >= LIM and inc > 0)   # True = mare cheia de verdade
    cheia   = [t["R"] for t in todos if _class(t) is True]
    resto   = [t["R"] for t in todos if _class(t) is False]
    if cheia and resto:
        print(f"\n  MARE CHEIA DE VERDADE (S&P bom-forte didi3>= +{LIM:.2f} E MA3 subindo):")
        print(f"  {'grupo':<18}{'trades':>7}{'win':>7}{'exp':>10}{'acum':>10}{'payoff':>8}")
        print("  " + "-" * 58)
        print(linha("MARE CHEIA     ", cheia))
        print(linha("RESTO          ", resto))
        _, _, e_c, _, _ = estat(cheia)
        _, _, e_r, _, _ = estat(resto)
        _, _, e_g, _, _ = estat(ger)
        print("\n  LEITURA (mare cheia):")
        print(f"  - Filtrando so a mare cheia (forte E subindo): {e_c:+.3f}R/trade,")
        print(f"    contra {e_r:+.3f}R do resto e {e_g:+.3f}R do geral (sem filtro).")
        if e_c > e_g:
            print(f"    E o teto do humor: +{e_c-e_g:.3f}R acima da media — e onde pisar fundo.")

    # leitura pronta
    _, wr_b, exp_b, acc_b, _ = estat(bom)
    _, wr_m, exp_m, acc_m, _ = estat(mau)
    print("\n  LEITURA:")
    if bom and mau:
        if exp_b > exp_m:
            print(f"  - No BOM humor cada trade rende {exp_b:+.3f}R, no MAU {exp_m:+.3f}R.")
            dif = exp_b - exp_m
            print(f"    Diferenca de {dif:.3f}R por trade a favor de operar com o S&P de bom humor.")
        else:
            print(f"  - Aqui o MAU humor rendeu tanto quanto ou mais ({exp_m:+.3f}R vs {exp_b:+.3f}R).")
            print(f"    Nesta amostra o filtro de humor NAO ajudou — cuidado antes de adotar.")
        if exp_m <= 0 < exp_b:
            print(f"  - Ficar de FORA no mau humor teria evitado um grupo de expectancia negativa.")
    else:
        print("  - Amostra insuficiente em um dos grupos para conclusao confiavel.")

    # CSV: um trade por linha
    df = pd.DataFrame(todos)
    if not df.empty:
        df["humor"] = df["humor"].map({True: "bom", False: "mau", None: "sem_dado"})
        df = df.sort_values("data")
        df.to_csv(a.out, index=False, sep=";", encoding="utf-8-sig",
                  date_format="%Y-%m-%d")
        print(f"\n  Detalhe trade a trade: {a.out}")

if __name__ == "__main__":
    main()
