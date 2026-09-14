#!/usr/bin/env python3
"""
Registro de sinais (forward testing). A cada dia que o scanner roda (candle
fechado), acrescenta uma linha por sinal num CSV historico. No futuro, com
meses de dados, roda-se o backtest sobre esses sinais REAIS (gerados ao vivo,
sem vies de olhar o futuro) para medir a efetividade real do scanner e quais
situacoes sao mais favoraveis.

Dois arquivos, um por sistema:
  historico_sinais_didi.csv
  historico_sinais_insidebar.csv

Protecao anti-duplicata: nao grava o mesmo (data,ticker) duas vezes — se o
scanner rodar 2x no mesmo dia, o sinal fica registrado so uma vez.
"""
import os, csv, datetime

DIR = os.path.dirname(os.path.abspath(__file__))

# ---- Campos guardados (tudo que o backtest futuro precisa) ----
CAMPOS_DIDI = [
    "data","ticker","market","sistema",
    "entrada","stop","alvo_2r","r_pct",
    # categoria do sinal (para analisar quais situacoes valem mais):
    "tipo",            # 3JUNTOS / ABERTURA / ADXHOJE
    "mme70",           # ACIMA_SUB / ACIMA_LAT / ABAIXO
    "confluencia","bb_primeira","didi_ago","adx_ago",
    "acima_ema70","ema70_incl","quality",
    "vol_qtd","var_dia_pct",
]
CAMPOS_IB = [
    "data","ticker","market","sistema",
    "grupo",           # RADAR (inside bar hoje) / ENTRAR (rompimento hoje)
    "entrada","stop","parcial2r","alvo_final","r_pct",
    "compress","cons_len","contr_vol","dist_ema",
    "vol_qtd","var_dia_pct",
]

def _tipo_didi(h):
    """Classifica o sinal do DIDI conforme os blocos do painel."""
    conf = bool(h.get("confluencia")); prim = bool(h.get("bb_primeira"))
    adx0 = (h.get("adx_ago")==0)
    if conf and prim: return "3JUNTOS"
    if prim:          return "ABERTURA"
    if adx0:          return "ADXHOJE"
    return "OUTRO"

def _mme70_didi(h):
    acima = bool(h.get("acima_ema70"))
    incl = (h.get("ema70_incl") or "").lower()
    if acima and incl.startswith("sob"): return "ACIMA_SUB"
    if acima: return "ACIMA_LAT"
    return "ABAIXO"

def _carrega_chaves(path):
    """Retorna set de (data,ticker) ja gravados, p/ evitar duplicata."""
    chaves=set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                chaves.add((row.get("data",""), row.get("ticker","")))
    return chaves

def _append(path, campos, linhas):
    existe = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if not existe: w.writeheader()
        for ln in linhas: w.writerow(ln)

def registrar_didi(hits, data=None):
    """hits: lista de dicts (os sinais 'bons' do painel da Agulhada)."""
    data = data or str(datetime.date.today())
    path = os.path.join(DIR, "historico_sinais_didi.csv")
    ja = _carrega_chaves(path)
    linhas=[]
    for h in hits:
        tk = h.get("ticker","")
        if (data, tk) in ja: continue     # ja registrado hoje
        linhas.append({
            "data":data, "ticker":tk, "market":h.get("market",""), "sistema":"DIDI",
            "entrada":h.get("close"), "stop":h.get("stop"), "alvo_2r":h.get("alvo_2r"),
            "r_pct":h.get("r_pct"),
            "tipo":_tipo_didi(h), "mme70":_mme70_didi(h),
            "confluencia":bool(h.get("confluencia")), "bb_primeira":bool(h.get("bb_primeira")),
            "didi_ago":h.get("didi_ago"), "adx_ago":h.get("adx_ago"),
            "acima_ema70":bool(h.get("acima_ema70")), "ema70_incl":h.get("ema70_incl"),
            "quality":h.get("quality"),
            "vol_qtd":h.get("vol_qtd"), "var_dia_pct":h.get("var_dia_pct"),
        })
        ja.add((data,tk))
    if linhas: _append(path, CAMPOS_DIDI, linhas)
    print(f"  [registro DIDI] +{len(linhas)} sinais em historico_sinais_didi.csv")
    return len(linhas)

def registrar_insidebar(grupos, data=None):
    """grupos: dict {'hoje':[...], 'romp':[...]} do scanner Insidebar."""
    data = data or str(datetime.date.today())
    path = os.path.join(DIR, "historico_sinais_insidebar.csv")
    ja = _carrega_chaves(path)
    linhas=[]
    def add(h, grupo):
        tk=h.get("ticker","")
        # chave inclui grupo p/ permitir o mesmo ticker no radar e no entrar
        if (data, tk+"|"+grupo) in ja: return
        linhas.append({
            "data":data, "ticker":tk, "market":h.get("market",""), "sistema":"INSIDEBAR",
            "grupo":grupo,
            "entrada":h.get("entry"), "stop":h.get("stop"),
            "parcial2r":h.get("parcial2r"), "alvo_final":h.get("alvo_final"),
            "r_pct":h.get("r_pct"),
            "compress":h.get("compress"), "cons_len":h.get("cons_len"),
            "contr_vol":h.get("contr_vol"), "dist_ema":h.get("dist_ema"),
            "vol_qtd":h.get("vol_qtd"), "var_dia_pct":h.get("var_dia_pct"),
        })
        ja.add((data, tk+"|"+grupo))
    for h in grupos.get("romp",[]): add(h,"ENTRAR")
    for h in grupos.get("hoje",[]): add(h,"RADAR")
    if linhas: _append(path, CAMPOS_IB, linhas)
    print(f"  [registro Insidebar] +{len(linhas)} sinais em historico_sinais_insidebar.csv")
    return len(linhas)
