#!/usr/bin/env python3
"""
============================================================================
HUMOR DO S&P 500 — painel para os scanners (DIDI e Insidebar)
============================================================================
Calcula o "humor" do S&P 500 pelo DIDI (media 3 vs media 8 do fechamento) e
devolve um painel HTML colorido com a SITUACAO DE HOJE + a tabela de
referencia validada nos backtests (3 cestas).

Leitura dos backtests (bom forte x bom fraco, robusto nas 3 cestas):
  BOM FORTE  didi3 >= +0.70   -> mare cheia: risco cheio (dedicar-se)
  BOM FRACO  0    a  +0.70    -> mare morna: risco padrao
  MAU FRACO  -0.40 a 0        -> mare morna: risco padrao/reduzido
  MAU FORTE  didi3 <  -0.40   -> mare seca: risco minimo

Nao e filtro de entra/nao-entra (nenhum grupo perde dinheiro) — e ACELERADOR:
segue pegando todo sinal da Agulhada, mas pisa mais fundo no risco quando o
S&P esta claramente comprado.

Uso nos scanners:
    import humor_sp500 as hs
    painel = hs.painel_html()      # bloco HTML pronto p/ inserir apos <body>
    ...
    html = html.replace("<body>", "<body>" + painel)   # ou concatena

Fonte dos dados: usa 'sp500.csv' (date,open,high,low,close,volume) se existir
na pasta; senao baixa ^GSPC pelo yfinance. Se nada funcionar, devolve um
painel neutro dizendo que nao conseguiu ler o S&P (nao quebra o scanner).
============================================================================
"""
import os
import numpy as np, pandas as pd

# fronteiras validadas (medianas ~ +0.70 e -0.40 nas 3 cestas)
LIM_BOM_FORTE = 0.70    # didi3 >= isso  -> bom forte
LIM_MAU_FORTE = -0.40   # didi3 <  isso  -> mau forte

# expectancia media por zona (R/trade), das 3 cestas — so p/ exibir referencia
REF = {
    "bom_forte": {"nome": "BOM HUMOR FORTE", "risco": "Risco CHEIO",
                  "exp": "≈ +0.35R/trade", "cor": "#1b8a3a", "cor2": "#e6f5ea",
                  "emoji": "▲▲", "acao": "Maré cheia — é aqui que vale se dedicar."},
    "bom_fraco": {"nome": "BOM HUMOR FRACO", "risco": "Risco padrão",
                  "exp": "≈ +0.26R/trade", "cor": "#7cb342", "cor2": "#f1f8e9",
                  "emoji": "▲", "acao": "Maré morna — opera normal, sem acelerar."},
    "mau_fraco": {"nome": "MAU HUMOR FRACO", "risco": "Risco padrão/reduzido",
                  "exp": "≈ +0.30R/trade", "cor": "#f9a825", "cor2": "#fff8e1",
                  "emoji": "▼", "acao": "Maré morna — cautela, tamanho normal ou menor."},
    "mau_forte": {"nome": "MAU HUMOR FORTE", "risco": "Risco MÍNIMO",
                  "exp": "≈ +0.24R/trade", "cor": "#e53935", "cor2": "#ffebee",
                  "emoji": "▼▼", "acao": "Maré seca — sobrevive, não empolga. Pé no freio."},
    "sem_dado": {"nome": "SEM DADO DO S&P 500", "risco": "—",
                 "exp": "—", "cor": "#9e9e9e", "cor2": "#f5f5f5",
                 "emoji": "?", "acao": "Não consegui ler o S&P 500 hoje — opere com o critério padrão."},
}

def _didi3_sp(caminho="sp500.csv"):
    """Devolve (didi3_hoje, data_hoje, fonte) do S&P 500. didi3 = (MA3/MA8-1)*100."""
    def calc(c):
        ma3 = c.rolling(3).mean(); ma8 = c.rolling(8).mean()
        d3 = (ma3 / ma8 - 1.0) * 100.0
        return d3
    # 1) arquivo local
    if os.path.exists(caminho):
        try:
            d = pd.read_csv(caminho, parse_dates=["date"]).set_index("date")
            d = d.rename(columns={"close": "Close"})
            d3 = calc(d["Close"]).dropna()
            return float(d3.iloc[-1]), d3.index[-1].date(), f"arquivo {caminho}"
        except Exception:
            pass
    # 2) yfinance
    try:
        import yfinance as yf
        d = yf.Ticker("^GSPC").history(period="6mo", interval="1d", auto_adjust=True)
        if d is not None and not d.empty:
            if d.index.tz is not None: d.index = d.index.tz_localize(None)
            d3 = calc(d["Close"]).dropna()
            return float(d3.iloc[-1]), d3.index[-1].date(), "yfinance (^GSPC)"
    except Exception:
        pass
    return None, None, None

def zona(didi3):
    if didi3 is None: return "sem_dado"
    if didi3 >= LIM_BOM_FORTE: return "bom_forte"
    if didi3 >= 0:             return "bom_fraco"
    if didi3 >= LIM_MAU_FORTE: return "mau_fraco"
    return "mau_forte"

def situacao(caminho="sp500.csv"):
    """Devolve um dict com a situacao de hoje (p/ quem quiser usar sem HTML)."""
    d3, data, fonte = _didi3_sp(caminho)
    z = zona(d3)
    return {"didi3": d3, "data": data, "fonte": fonte, "zona": z, **REF[z]}

def painel_html(caminho="sp500.csv"):
    """Bloco HTML do painel de humor do S&P 500 (situacao de hoje + tabela ref)."""
    s = situacao(caminho)
    r = REF[s["zona"]]
    d3txt = f"{s['didi3']:+.2f}" if s["didi3"] is not None else "—"
    datatxt = f" · {s['data']}" if s["data"] else ""
    fontetxt = f" · fonte: {s['fonte']}" if s["fonte"] else ""

    # linhas da tabela de referencia (destaca a zona de hoje)
    ordem = ["bom_forte", "bom_fraco", "mau_fraco", "mau_forte"]
    faixa = {
        "bom_forte": "didi3 ≥ +0,70",
        "bom_fraco": "0 a +0,70",
        "mau_fraco": "−0,40 a 0",
        "mau_forte": "didi3 < −0,40",
    }
    linhas = ""
    for k in ordem:
        rr = REF[k]
        ativo = (k == s["zona"])
        bg = rr["cor2"] if ativo else "#fff"
        marca = ("<span style='background:%s;color:#fff;border-radius:6px;padding:1px 7px;"
                 "font-size:11px;font-weight:700'>HOJE</span>" % rr["cor"]) if ativo else ""
        peso = "700" if ativo else "500"
        linhas += (
            f"<tr style='background:{bg}'>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>"
            f"<span style='display:inline-block;width:10px;height:10px;border-radius:2px;"
            f"background:{rr['cor']};margin-right:7px'></span>"
            f"<b style='color:{rr['cor']};font-weight:{peso}'>{rr['nome']}</b> {marca}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-family:monospace'>{faixa[k]}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-weight:{peso}'>{rr['risco']}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;color:#555'>{rr['exp']}</td>"
            f"</tr>"
        )

    return f"""
<div style="max-width:900px;margin:0 auto 18px auto;border:1px solid #e0e0e0;border-radius:12px;overflow:hidden;font-family:'Segoe UI',Arial">
  <div style="background:{r['cor']};color:#fff;padding:14px 18px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
    <div style="display:flex;align-items:center;gap:12px">
      <span style="font-size:26px;line-height:1">{r['emoji']}</span>
      <div>
        <div style="font-size:12px;opacity:.85;letter-spacing:.5px">HUMOR DO S&amp;P 500 HOJE{datatxt}</div>
        <div style="font-size:20px;font-weight:800">{r['nome']}</div>
      </div>
    </div>
    <div style="text-align:right">
      <div style="font-size:12px;opacity:.85">DIDI do S&amp;P (média 3 vs 8)</div>
      <div style="font-size:22px;font-weight:800;font-family:monospace">{d3txt}</div>
    </div>
  </div>
  <div style="background:{r['cor2']};padding:10px 18px;font-size:14px;color:#333;border-bottom:1px solid #eee">
    <b>{r['risco']}</b> — {r['acao']}
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead>
      <tr style="background:#fafafa;color:#666;text-align:left">
        <th style="padding:6px 10px;border-bottom:2px solid #e0e0e0">Zona</th>
        <th style="padding:6px 10px;border-bottom:2px solid #e0e0e0">Faixa didi3 S&amp;P</th>
        <th style="padding:6px 10px;border-bottom:2px solid #e0e0e0">Tamanho da posição</th>
        <th style="padding:6px 10px;border-bottom:2px solid #e0e0e0">Expectância (backtest)</th>
      </tr>
    </thead>
    <tbody>{linhas}</tbody>
  </table>
  <div style="padding:8px 18px;font-size:11px;color:#999;background:#fff">
    Termômetro de humor do mercado — validado em 3 cestas (≈11,7 mil trades da Agulhada).
    Não é filtro de entrada; é acelerador de tamanho: entre em todo sinal válido, mas pise fundo no risco só na maré cheia.{fontetxt}
  </div>
</div>
"""

def gerar_json(caminho="sp500.csv", out="painel_humor.json"):
    """Grava painel_humor.json com a situacao de hoje + a tabela de referencia,
    para as paginas do site (GitHub Pages) desenharem o painel em JavaScript."""
    import json, datetime
    s = situacao(caminho)
    ordem = ["bom_forte", "bom_fraco", "mau_fraco", "mau_forte"]
    faixa = {"bom_forte": "≥ +0,70", "bom_fraco": "0 a +0,70",
             "mau_fraco": "−0,40 a 0", "mau_forte": "< −0,40"}
    tabela = [{
        "zona": k, "nome": REF[k]["nome"], "faixa": faixa[k],
        "risco": REF[k]["risco"], "exp": REF[k]["exp"],
        "cor": REF[k]["cor"], "cor2": REF[k]["cor2"], "emoji": REF[k]["emoji"],
        "hoje": (k == s["zona"]),
    } for k in ordem]
    payload = {
        "gerado_em": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_sp": str(s["data"]) if s["data"] else None,
        "didi3": round(s["didi3"], 3) if s["didi3"] is not None else None,
        "zona": s["zona"], "nome": s["nome"], "risco": s["risco"],
        "acao": s["acao"], "exp": s["exp"], "emoji": s["emoji"],
        "cor": s["cor"], "cor2": s["cor2"], "fonte": s["fonte"],
        "tabela": tabela,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload

if __name__ == "__main__":
    import sys
    # 'python humor_sp500.py --json' grava painel_humor.json (usado pelo GitHub Actions)
    if "--json" in sys.argv:
        p = gerar_json()
        print(f"painel_humor.json gerado: {p['nome']} (didi3={p['didi3']}) fonte={p['fonte']}")
    else:
        s = situacao()
        print(f"Humor do S&P 500 hoje: {s['nome']}  (didi3={s['didi3']})  fonte={s['fonte']}")
        print(f"  {s['risco']} — {s['acao']}")
