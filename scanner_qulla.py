#!/usr/bin/env python3
"""
============================================================================
SCANNER QULLAMAGGIE — lideres de momentum em consolidacao/rompimento HOJE
============================================================================
Lista os ativos que HOJE sao candidatos ao setup Qullamaggie:
  1) LIDER de momentum: +30%/1M ou +90%/3M ou +150%/6M
  2) em CONSOLIDACAO valida (5-15d, ATR contraindo, colado na EMA20)
  3) ou ja ROMPENDO a maxima da consolidacao no candle de hoje.

Entrada sugerida: rompimento da maxima da consolidacao.
Stop: minima do dia ANTERIOR ao da entrada (conhecida na hora da ordem). Alvo: 3R.

USO:
  python scanner_qulla.py            # universo completo (B3 + EUA)
  python scanner_qulla.py --quick    # teste rapido
  python scanner_qulla.py --market us
Gera scanner_qulla.html e painel_qulla.json.
============================================================================
"""
import argparse, datetime, json
import numpy as np, pandas as pd
import scanner as sc
import run_backtest_v2 as rb

# --- parametros (iguais ao backtest validado) ---
MOM_1M, MOM_3M, MOM_6M = 30.0, 90.0, 150.0   # recalibrado c/ execucao realista (set/2026): melhor por trade nas 3 cestas, ~40% menos sinais
PURO_1M, PURO_3M, PURO_6M = 30.0, 90.0, 150.0   # criterios RIGOROSOS do criador (selo de elite)
CONSOL_MIN, CONSOL_MAX = 5, 15
ATR_CONTRACAO = 1.10   # afrouxado de 1.0 -> 1.10 (validado: +21% sinais, exp igual)
DIST_EMA_MAX = 0.10
ALVO_R = 3.0

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(h, l, c, n):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def avalia(d, funil=None):
    """Avalia o ultimo candle de d. Devolve dict do sinal ou None.
    Se `funil` (dict) for passado, conta em que etapa cada ativo parou."""
    def _stop(etapa):
        if funil is not None: funil[etapa] = funil.get(etapa, 0) + 1
        return None
    if len(d) < 140: return _stop("hist_curto")
    c, h, l = d["Close"], d["High"], d["Low"]
    ema20 = ema(c, 20); ema10 = ema(c, 10)
    atr5 = atr(h, l, c, 5); atr20 = atr(h, l, c, 20)
    mom1 = (c.iloc[-1]/c.iloc[-22]-1)*100 if len(c) > 22 else np.nan
    mom3 = (c.iloc[-1]/c.iloc[-64]-1)*100 if len(c) > 64 else np.nan
    mom6 = (c.iloc[-1]/c.iloc[-127]-1)*100 if len(c) > 127 else np.nan
    lider = (mom1>=MOM_1M) or (mom3>=MOM_3M) or (mom6>=MOM_6M)
    if not lider: return _stop("nao_lider")
    # consolidacao logo antes do ultimo candle (i = ultimo)
    i = len(d)-1
    topo = None; ndias = None
    for n in range(CONSOL_MAX, CONSOL_MIN-1, -1):
        if i-n < 1: continue
        jan = slice(i-n, i)
        hh = h.iloc[jan].max(); ll = l.iloc[jan].min(); e20 = ema20.iloc[jan].mean()
        if not (atr5.iloc[i-1] < atr20.iloc[i-1]*ATR_CONTRACAO): continue
        if e20<=0 or abs(c.iloc[i-1]-e20)/e20 > DIST_EMA_MAX: continue
        if ll < e20*0.90: continue
        topo = float(hh); ndias = n; break
    if topo is None: return _stop("lider_sem_consol")
    preco = float(c.iloc[-1]); maxhoje = float(h.iloc[-1]); minhoje = float(l.iloc[-1])
    hoje = pd.Timestamp(datetime.date.today())
    forming = (d.index[-1].normalize() == hoje)   # candle de hoje ainda em formacao (pregao aberto)
    rompendo = maxhoje > topo
    # Execucao realista (validada no backtest): o stop e a minima do dia ANTERIOR ao da entrada,
    # que ja e conhecida na hora de pôr a ordem.
    #  - rompendo hoje: entrada no topo (ou na abertura, se abriu acima), stop na minima de ONTEM
    #  - consolidando: a entrada seria amanha no topo, com stop na minima de HOJE
    abertura = float(d["Open"].iloc[-1])
    if rompendo:
        entrada = max(topo, abertura)
        stop = float(l.iloc[i-1])
    else:
        entrada = topo
        stop = minhoje
    risk = entrada - stop
    if risk <= 0: return None
    alvo = round(entrada + ALVO_R*risk, 2)
    return {
        "entrada": round(entrada,2), "stop": round(stop,2), "alvo_3r": alvo,
        "preco": round(preco,2), "r_pct": round(risk/entrada*100,2) if entrada>0 else 0,
        "mom1": None if np.isnan(mom1) else round(mom1,0),
        "mom3": None if np.isnan(mom3) else round(mom3,0),
        "mom6": None if np.isnan(mom6) else round(mom6,0),
        "consol_dias": ndias, "rompendo": bool(rompendo),
        "acima_ema20": bool(preco > ema20.iloc[-1]),
        "puro": bool((mom1>=PURO_1M) or (mom3>=PURO_3M) or (mom6>=PURO_6M)),  # cumpre criterios rigorosos do criador
        "forming": bool(forming),   # candle de hoje em formacao (rompimento provisorio)
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--market", choices=["b3","us","all"], default="all")
    ap.add_argument("--out", default="scanner_qulla")
    ap.add_argument("--chunk", type=int, default=100)
    a = ap.parse_args()

    uni = rb.get_universe(quick=a.quick)
    if a.market=="b3": uni=[t for t in uni if t.endswith(".SA")]
    elif a.market=="us": uni=[t for t in uni if not t.endswith(".SA")]
    print(f"Scanner QULLAMAGGIE | {len(uni)} ativos\n")

    dados = sc.fetch_batch(uni, timeframe="1d", chunk=a.chunk)
    hits = []; funil = {"total": 0, "lideres": 0}
    for tk, d in dados.items():
        if d is None or len(d) < 140: continue
        funil["total"] += 1
        try:
            # conta lideres (p/ diagnostico)
            c = d["Close"]
            if len(c) > 127:
                m1=(c.iloc[-1]/c.iloc[-22]-1)*100; m3=(c.iloc[-1]/c.iloc[-64]-1)*100; m6=(c.iloc[-1]/c.iloc[-127]-1)*100
                if (m1>=MOM_1M) or (m3>=MOM_3M) or (m6>=MOM_6M): funil["lideres"] += 1
            r = avalia(d, funil)
            if r:
                r["ticker"] = tk
                r["market"] = "B3" if tk.endswith(".SA") else "EUA"
                r["tv"] = sc.tv_url(tk)
                hits.append(r)
        except Exception:
            pass
    # diagnostico do funil (util quando da 0)
    print(f"\n  [funil] {funil.get('total',0)} ativos com historico | "
          f"{funil.get('lideres',0)} lideres de momentum | "
          f"{funil.get('lider_sem_consol',0)} lideres sem consolidacao valida | "
          f"{len(hits)} candidatos finais\n")

    # ordena: rompendo hoje primeiro, depois maior momentum
    hits.sort(key=lambda x: (not x["rompendo"], -(x["mom3"] or x["mom1"] or 0)))

    print("="*70)
    if not hits:
        print("  Nenhum lider em consolidacao/rompimento hoje.")
    else:
        print(f"  {len(hits)} candidato(s):\n")
        print(f"  {'ATIVO':<10}{'STATUS':<12}{'PRECO':>8}{'ENTRADA':>9}{'STOP':>8}{'ALVO3R':>9}{'MOM3M':>7}{'CONS':>6}")
        for x in hits:
            st = "ROMPENDO" if x["rompendo"] else "consolid."
            m3 = f"+{x['mom3']:.0f}%" if x['mom3'] is not None else "—"
            print(f"  {x['ticker'].replace('.SA',''):<10}{st:<12}{x['preco']:>8}{x['entrada']:>9}"
                  f"{x['stop']:>8}{x['alvo_3r']:>9}{m3:>7}{x['consol_dias']:>5}d")
    print("="*70)

    # JSON
    payload = {"gerado": datetime.date.today().isoformat(), "n": len(hits), "ativos": hits}
    open(f"painel_qulla.json","w",encoding="utf-8").write(json.dumps(payload,ensure_ascii=False,indent=2))
    print(f"  JSON: painel_qulla.json")

    # registro da CONFLUENCIA (forward testing): tira a foto DIDI x Qulla e grava
    # no historico_confluencia.csv (so com pregao fechado; a prova de erro embutida).
    try:
        import registro_confluencia
        registro_confluencia.registrar(qulla_ativos=hits)
    except Exception as e:
        print(f"  [registro Confluencia] falhou: {e}")

    # HTML
    rows=""
    for x in hits:
        badge = ("<span style='background:#e6a817;color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700'>ROMPENDO</span>"
                 if x["rompendo"] else
                 "<span style='background:#30363d;color:#8b949e;padding:2px 8px;border-radius:10px;font-size:11px'>consolidando</span>")
        m1 = f"+{x['mom1']:.0f}%" if x['mom1'] is not None else "—"
        m3 = f"+{x['mom3']:.0f}%" if x['mom3'] is not None else "—"
        m6 = f"+{x['mom6']:.0f}%" if x['mom6'] is not None else "—"
        rows+=(f"<tr><td style='font-weight:600'><a href='{x['tv']}' target='_blank' style='color:#1A4731;text-decoration:none;border-bottom:1px dotted #1A4731'>{x['ticker'].replace('.SA','')} ↗</a></td>"
               f"<td>{x['market']}</td><td>{badge}</td>"
               f"<td style='text-align:right'>{x['preco']}</td>"
               f"<td style='text-align:right'>{x['entrada']}</td>"
               f"<td style='text-align:right'>{x['stop']}</td>"
               f"<td style='text-align:right;color:#1b8a3a;font-weight:600'>{x['alvo_3r']}</td>"
               f"<td style='text-align:right'>{x['r_pct']}%</td>"
               f"<td style='text-align:right'>{m1}</td><td style='text-align:right'>{m3}</td><td style='text-align:right'>{m6}</td>"
               f"<td style='text-align:right'>{x['consol_dias']}d</td></tr>")
    today=datetime.date.today().strftime("%Y-%m-%d"); n=len(hits)
    html=f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scanner Qullamaggie</title>
    <style>body{{font-family:'Segoe UI',Arial;max-width:900px;margin:auto;padding:28px;color:#222}}
    h2{{color:#1A4731;border-bottom:3px solid #e6a817;padding-bottom:10px}}
    table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}
    th{{background:#1A4731;color:#fff;padding:9px;text-align:right}}th:first-child,th:nth-child(2),th:nth-child(3){{text-align:left}}
    td{{padding:8px 9px;border-bottom:1px solid #eee}} tbody tr:hover{{background:#fdf7e6}}</style></head><body>
    <h2>Scanner Qullamaggie — momentum breakout</h2>
    <p style="font-size:13px;color:#666">{n} candidato(s) · gerado em {today}. Líderes de momentum (+30%/1M ou +90%/3M ou +150%/6M) em consolidação (5-15d) ou rompendo.
    <b>Entrada</b> = rompimento da máxima da consolidação · <b>Stop</b> = mínima do dia anterior à entrada · <b>Alvo</b> = 3R.</p>
    <table><thead><tr><th>Ativo</th><th>Mercado</th><th>Status</th><th>Preço</th><th>Entrada</th><th>Stop</th><th>Alvo 3R</th><th>R%</th><th>1M</th><th>3M</th><th>6M</th><th>Consol.</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan=12 style=text-align:center;color:#888;padding:20px>Nenhum líder em consolidação/rompimento hoje.</td></tr>'}</tbody></table>
    <p style="font-size:12px;color:#888;margin-top:14px">Setup Qullamaggie: só líderes de momentum. Win rate ~45%, mas alvo 3R paga as perdas. Backtest: +0.80R/trade nas cestas. Não é recomendação.</p>
    </body></html>"""
    open(f"{a.out}.html","w",encoding="utf-8").write(html)
    print(f"  HTML: {a.out}.html")

if __name__ == "__main__":
    main()
