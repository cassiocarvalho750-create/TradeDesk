#!/usr/bin/env python3
"""
Registro da CONFLUENCIA (forward testing).

A cada dia de pregao fechado, tira uma "foto" da aba Confluencia — o cruzamento
DIDI x Qullamaggie — e grava uma linha por ativo num CSV historico. No futuro,
com meses de dados, roda-se o backtest sobre esses sinais REAIS (gerados ao
vivo, sem vies de olhar o futuro) para medir se a confluencia funciona e qual
prioridade / posicao na fila rende mais.

Replica EXATAMENTE a logica de docs/TradeDeskConfluencia.html:
  - DIDI aprovado: confluencia OR bb_primeira OR adx_ago==0
  - prioridades: 1 (DIDI+rompeu) / 2 (DIDI+consolidando) / 3 (so rompeu) / 4 (so DIDI)
  - ordem: prioridade -> faixa de momentum (forte>=30 / medio 10-30 / fraco<10 /
    sem dado) -> menor R% -> elite -> maior mom3
  - registra ordem_geral (posicao na lista toda) e ordem_subgrupo (dentro da prioridade)

Arquivo: historico_confluencia.csv
Anti-duplicata: nao grava o mesmo (data,ticker) duas vezes no mesmo dia.
A prova de erro: so grava se TODOS os mercados presentes na foto ja fecharam
hoje (BRT); se algum candle ainda esta em formacao, pula o dia inteiro (a foto
so vale com tudo fechado, senao rompimentos/precos sao provisorios).
"""
import os, csv, json, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(DIR, "historico_confluencia.csv")

FECHAMENTO_BRT = {
    "EUA": (18, 15),
    "B3":  (18, 30),
}

CAMPOS = [
    "data",
    "ordem_geral",      # posicao na lista TOTAL (1 = topo)
    "prioridade",       # 1 / 2 / 3 / 4
    "ordem_subgrupo",   # posicao DENTRO da prioridade (1 = topo do subgrupo)
    "ticker", "market",
    # dados de entrada (do Qulla quando existe, senao do DIDI):
    "entrada", "stop", "alvo", "r_pct",
    # sinais que compoem a prioridade:
    "tem_didi", "q_rompeu", "q_consolidando", "elite",
    # momentum (com fallback DIDI):
    "mom1", "mom3", "mom6", "faixa_mom",
    # contexto DIDI (quando aplicavel):
    "didi_tipo", "quality",
    # contexto Qulla (quando aplicavel):
    "consol_dias", "acima_ema20",
]


def _agora_brt(agora=None):
    if agora:
        return agora
    tz = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(datetime.timezone.utc).astimezone(tz)


def _mercado_fechado(market, agora=None):
    agora = _agora_brt(agora)
    if agora.weekday() >= 5:
        return True
    h, m = FECHAMENTO_BRT.get(market, (18, 30))
    limite = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    return agora >= limite


def _norm(tk):
    return (tk or "").replace(".SA", "").upper()


def _didi_aprovado(a):
    return bool(a.get("confluencia")) or bool(a.get("bb_primeira")) or (a.get("adx_ago") == 0)


def _didi_tipo(a):
    conf = bool(a.get("confluencia")); prim = bool(a.get("bb_primeira"))
    adx0 = (a.get("adx_ago") == 0)
    if conf and prim: return "3JUNTOS"
    if prim:          return "ABERTURA"
    if adx0:          return "ADXHOJE"
    return "OUTRO"


def _faixa_mom(m3):
    if m3 is None: return 3
    if m3 >= 30:   return 0   # forte
    if m3 >= 10:   return 1   # medio
    return 2                  # fraco

_FAIXA_ROT = {0: "forte", 1: "medio", 2: "fraco", 3: "sem_dado"}


def _carrega_chaves(path):
    chaves = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                chaves.add((row.get("data", ""), row.get("ticker", "")))
    return chaves


def _le_painel(path):
    try:
        with open(path, encoding="utf-8") as f:
            return (json.load(f) or {}).get("ativos", []) or []
    except Exception:
        return []


def montar_confluencia(didi_ativos, qulla_ativos):
    """Reproduz a lista ordenada da aba Confluencia. Retorna lista de dicts ja
    na ordem final, com prioridade e campos calculados."""
    didi = {}
    for a in didi_ativos:
        if _didi_aprovado(a):
            didi[_norm(a.get("ticker"))] = a
    qulla = {}
    for a in qulla_ativos:
        qulla[_norm(a.get("ticker"))] = a

    tickers = set(didi) | set(qulla)
    linhas = []
    for tk in tickers:
        d = didi.get(tk); q = qulla.get(tk)
        tem_didi = d is not None
        q_rompeu = bool(q and q.get("rompendo"))
        q_cons = bool(q and not q.get("rompendo"))
        if tem_didi and q_rompeu:      prio = 1
        elif tem_didi and q_cons:      prio = 2
        elif (not tem_didi) and q_rompeu: prio = 3
        elif tem_didi:                 prio = 4
        else:                          continue  # so consolidando sem DIDI: fora

        # entrada: do Qulla quando existe (rompimento), senao o close do DIDI
        # (assim a prioridade 4 tambem fica backtestavel no forward test).
        entrada = (q.get("entrada") if q else None) or (d.get("close") if d else None)
        stop = q.get("stop") if q else (d.get("stop") if d else None)
        alvo = q.get("alvo_3r") if q else None
        rpct = None
        if entrada and stop and entrada > 0:
            rpct = round((entrada - stop) / entrada * 100, 2)

        def _mom(k):
            v = q.get(k) if q else None
            if v is None and d is not None:
                v = d.get(k)
            return v
        m1, m3, m6 = _mom("mom1"), _mom("mom3"), _mom("mom6")

        linhas.append({
            "ticker": tk,
            "market": (q.get("market") if q else None) or (d.get("market") if d else "") or "",
            "prioridade": prio,
            "tem_didi": tem_didi, "q_rompeu": q_rompeu, "q_consolidando": q_cons,
            "elite": bool(q.get("puro")) if q else False,
            "entrada": entrada, "stop": stop, "alvo": alvo, "r_pct": rpct,
            "mom1": m1, "mom3": m3, "mom6": m6, "_fx": _faixa_mom(m3),
            "faixa_mom": _FAIXA_ROT[_faixa_mom(m3)],
            "didi_tipo": _didi_tipo(d) if d else "",
            "quality": d.get("quality") if d else None,
            "consol_dias": q.get("consol_dias") if q else None,
            "acima_ema20": (bool(q.get("acima_ema20")) if q else None),
            "forming": bool(q.get("forming")) if q else False,
        })

    # mesma ordenacao da pagina: prio -> faixa mom -> menor R% -> elite -> maior mom3
    # chave de momentum POR PRIORIDADE (igual a pagina):
    #  prio 1: so menor R% | prio 3: 3M<30 topo, 30-60 meio, 60+ fim | prio 2 e 4: faixa como antes
    def _chave_mom(x):
        if x["prioridade"] == 1: return 0
        if x["prioridade"] == 3:
            m = x["mom3"]
            if m is None: return 1
            if m >= 60: return 2
            if m >= 30: return 1
            return 0
        return x["_fx"]
    linhas.sort(key=lambda x: (
        x["prioridade"],
        _chave_mom(x),
        (1e9 if x["r_pct"] is None else x["r_pct"]),
        0 if x["elite"] else 1,
        -(x["mom3"] or 0),
    ))
    return linhas


def _painel(nome):
    """Le o painel preferindo a RAIZ (onde os scanners acabaram de escrever),
    caindo para docs/ (copia publicada) se nao existir na raiz."""
    raiz = os.path.join(DIR, nome)
    if os.path.exists(raiz):
        return _le_painel(raiz)
    return _le_painel(os.path.join(DIR, "docs", nome))


def registrar(didi_ativos=None, qulla_ativos=None, data=None, agora=None):
    """Tira a foto da Confluencia e grava no CSV. Se os painels nao forem
    passados, le painel_us/painel_b3/painel_qulla (raiz, ou docs/ como fallback)."""
    data = data or str(datetime.date.today())
    if didi_ativos is None:
        didi_ativos = _painel("painel_us.json") + _painel("painel_b3.json")
    if qulla_ativos is None:
        qulla_ativos = _painel("painel_qulla.json")

    linhas = montar_confluencia(didi_ativos, qulla_ativos)
    if not linhas:
        print("  [registro Confluencia] nada a registrar (lista vazia)")
        return 0

    # a prova de erro: so grava se TODOS os mercados presentes ja fecharam,
    # e se nenhum ativo esta 'em formacao' (candle provisorio).
    mercados = {ln["market"] for ln in linhas}
    if any(not _mercado_fechado(mk, agora) for mk in mercados):
        abertos = [mk for mk in mercados if not _mercado_fechado(mk, agora)]
        print(f"  [registro Confluencia] pulado: mercado(s) ainda aberto(s): {', '.join(abertos)}")
        return 0
    if any(ln["forming"] for ln in linhas):
        print("  [registro Confluencia] pulado: ha ativo em formacao (candle provisorio)")
        return 0

    ja = _carrega_chaves(CSV_PATH)
    # numera ordem geral e ordem no subgrupo
    sub = {}
    registros = []
    for i, ln in enumerate(linhas, start=1):
        p = ln["prioridade"]
        sub[p] = sub.get(p, 0) + 1
        if (data, ln["ticker"]) in ja:
            continue
        registros.append({
            "data": data,
            "ordem_geral": i,
            "prioridade": p,
            "ordem_subgrupo": sub[p],
            "ticker": ln["ticker"], "market": ln["market"],
            "entrada": ln["entrada"], "stop": ln["stop"], "alvo": ln["alvo"], "r_pct": ln["r_pct"],
            "tem_didi": ln["tem_didi"], "q_rompeu": ln["q_rompeu"],
            "q_consolidando": ln["q_consolidando"], "elite": ln["elite"],
            "mom1": ln["mom1"], "mom3": ln["mom3"], "mom6": ln["mom6"], "faixa_mom": ln["faixa_mom"],
            "didi_tipo": ln["didi_tipo"], "quality": ln["quality"],
            "consol_dias": ln["consol_dias"], "acima_ema20": ln["acima_ema20"],
        })

    if not registros:
        print(f"  [registro Confluencia] {len(linhas)} na foto, 0 novos (ja registrados hoje)")
        return 0

    existe = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if not existe:
            w.writeheader()
        for r in registros:
            w.writerow(r)
    print(f"  [registro Confluencia] +{len(registros)} sinais em historico_confluencia.csv "
          f"(prio1:{sub.get(1,0)} prio2:{sub.get(2,0)} prio3:{sub.get(3,0)} prio4:{sub.get(4,0)})")
    return len(registros)


if __name__ == "__main__":
    registrar()
