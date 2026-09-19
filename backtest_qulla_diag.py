#!/usr/bin/env python3
"""
DIAGNOSTICO do setup Qullamaggie — testa se o payoff alto e REAL ou artefato.
Roda o mesmo setup mas com varias saidas e mostra a distribuicao dos R.

Uso: python backtest_qulla_diag.py <pasta>
"""
import glob, sys, os, argparse
import numpy as np, pandas as pd
import backtest_didi as bd

MOM_1M, MOM_3M, MOM_6M = 20.0, 60.0, 100.0   # afrouxado 30/90/150 -> 20/60/100 (validado: +0.738R, pega lideres moderados)
CONSOL_MIN, CONSOL_MAX = 5, 15
ATR_CONTRACAO = 1.10   # afrouxado de 1.0 -> 1.10 (validado: +21% sinais, exp igual)
DIST_EMA_MAX = 0.10
EMA_PROX = 20
MAX_HOLD = 120

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(h, l, c, n):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def indicadores(d):
    c, h, l = d["Close"], d["High"], d["Low"]; d = d.copy()
    d["ema20"] = ema(c, 20); d["ema10"] = ema(c, 10)
    d["atr5"] = atr(h,l,c,5); d["atr20"] = atr(h,l,c,20)
    d["mom1"]=(c/c.shift(21)-1)*100; d["mom3"]=(c/c.shift(63)-1)*100; d["mom6"]=(c/c.shift(126)-1)*100
    return d

def eh_lider(r): return (r["mom1"]>=MOM_1M) or (r["mom3"]>=MOM_3M) or (r["mom6"]>=MOM_6M)

def consol_ok(d, i):
    c,h,l = d["Close"],d["High"],d["Low"]
    for n in range(CONSOL_MAX, CONSOL_MIN-1, -1):
        if i-n < 1: continue
        jan = slice(i-n, i)
        hh = h.iloc[jan].max(); ll = l.iloc[jan].min(); e20 = d["ema20"].iloc[jan].mean()
        if not (d["atr5"].iloc[i-1] < d["atr20"].iloc[i-1]*ATR_CONTRACAO): continue
        if e20<=0 or abs(c.iloc[i-1]-e20)/e20 > DIST_EMA_MAX: continue
        if ll < e20*0.90: continue
        return True, float(hh)
    return False, None

def trades_setup(d, tk, saida):
    """saida: 'trail10','trail20','alvo3','alvo2' """
    d = indicadores(d)
    c,h,l = d["Close"],d["High"],d["Low"]
    emaT = ema(c, 10) if saida=="trail10" else ema(c, 20)
    n=len(d); out=[]; i=130
    while i < n-1:
        r = d.iloc[i]
        if not eh_lider(r): i+=1; continue
        ok, topo = consol_ok(d, i)
        if not ok: i+=1; continue
        if not (float(h.iloc[i])>topo): i+=1; continue
        entry = max(topo, float(d["Open"].iloc[i])); stop=float(l.iloc[i]); risk=entry-stop
        if risk<=0: i+=1; continue
        p1=p2=None; st=stop; saiu=i+1
        alvo_fixo = entry + (3.0 if saida=="alvo3" else 2.0)*risk
        for j in range(i+1, min(i+MAX_HOLD,n)):
            saiu=j; lo=float(l.iloc[j]); hi=float(h.iloc[j]); cl=float(c.iloc[j])
            if saida in ("alvo2","alvo3"):
                if lo<=st: out.append(-1.0); break
                if hi>=alvo_fixo: out.append((alvo_fixo-entry)/risk); break
            else:  # trailing com parcial 2R
                if p1 is None:
                    if lo<=st: p1=-1.0;p2=-1.0;break
                    if hi>=entry+2*risk: p1=2.0; st=entry
                if p1 is not None and p2 is None:
                    if lo<=st: p2=0.0 if st==entry else -1.0; break
                    if cl<float(emaT.iloc[j]): p2=(cl-entry)/risk; break
        else:
            if saida in ("alvo2","alvo3"):
                out.append((float(c.iloc[min(i+MAX_HOLD,n-1)])-entry)/risk)
        if saida.startswith("trail"):
            if p1 is None: fim=(float(c.iloc[min(i+MAX_HOLD,n-1)])-entry)/risk; p1=fim;p2=fim
            elif p2 is None: p2=(float(c.iloc[min(i+MAX_HOLD,n-1)])-entry)/risk
            out.append(0.5*p1+0.5*p2)
        i=saiu+1
    return out

def stats(rs):
    if not rs: return None
    a=np.array(rs); N=len(a); wr=100*(a>0).mean(); exp=a.mean(); acc=a.sum()
    g=a[a>0]; p=a[a<=0]; po=(g.mean()/abs(p.mean())) if len(g) and len(p) else 0
    med=np.median(a)
    # sem o top 5% dos ganhos
    k=max(1,int(N*0.05)); idx=np.argsort(a)[-k:]; sem_top=np.delete(a,idx)
    exp_sem_top = sem_top.mean() if len(sem_top) else 0
    maxR=a.max()
    return dict(N=N,wr=wr,exp=exp,acc=acc,po=po,med=med,exp_sem_top=exp_sem_top,maxR=maxR,topk=k)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("pasta",nargs="?",default="prices_todos"); a=ap.parse_args()
    arqs=sorted(glob.glob(f"{a.pasta}/*.csv")); dfs=[]
    for arq in arqs:
        tk=os.path.basename(arq).replace(".csv","").upper()
        if tk=="SP500": continue
        try:
            d=bd.carrega(arq)
            if len(d)>=200: dfs.append((tk,d))
        except: pass
    print(f"DIAGNOSTICO QULLAMAGGIE | cesta '{a.pasta}' | {len(dfs)} ativos\n")
    print(f"  {'saida':<10}{'trades':>7}{'win':>6}{'exp':>9}{'mediana':>9}{'exp s/top5%':>13}{'maiorR':>9}{'payoff':>8}")
    print("  "+"-"*71)
    for saida,rot in [("trail10","EMA10"),("trail20","EMA20"),("alvo2","alvo 2R"),("alvo3","alvo 3R")]:
        todos=[]
        for tk,d in dfs:
            try: todos+=trades_setup(d,tk,saida)
            except: pass
        s=stats(todos)
        if s:
            print(f"  {rot:<10}{s['N']:>7}{s['wr']:>5.0f}%{s['exp']:>+8.2f}R{s['med']:>+8.2f}R"
                  f"{s['exp_sem_top']:>+12.2f}R{s['maxR']:>+8.1f}R{s['po']:>8.2f}")
    print("\n  Como ler:")
    print("  - Se 'exp s/top5%' cai MUITO vs 'exp': poucos trades gigantes seguram tudo (fragil).")
    print("  - Se a MEDIANA e negativa mas exp e positiva: a maioria perde, ganha nos outliers.")
    print("  - 'maiorR' mostra o maior acerto isolado (se for >30R, desconfie).")

if __name__=="__main__":
    main()
