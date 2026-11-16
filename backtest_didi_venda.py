import glob, os, sys, warnings
warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(1, os.getcwd())
import scanner as sc, bt_engine as bt
def sim(d, S, i0):
    o,h,l,c=(d[k].values for k in ("Open","High","Low","Close")); n=len(d); out=[]; i=i0
    while i<n-1:
        if S[i]:
            e=c[i]; st=h[i]
            if PIVO:
                for k in range(i-3, 5, -1):
                    if h[k]==h[k-3:k+4].max(): st=max(h[k],h[i]) ; break
            r=st-e
            if r<=0 or r/e<0.005: i+=1; continue
            tg=e-3*r; res=None
            for j in range(i+1, min(i+121,n)):
                if h[j]>=st: res=-1.0 if o[j]<st else -(o[j]-e)/r; break
                if l[j]<=tg: res=3.0; break
            if res is None: j=min(i+120,n-1); res=(e-c[j])/r
            out.append((i,res)); i=j+1
        else: i+=1
    return out
for PIVO in (False,True):
 print("STOP:", "ultimo pivo de alta 3x3" if PIVO else "maxima do candle do sinal")
 for ini,nome in (("2015-01-01","2015-2021"),("2022-01-01","2022-2026")):
     A=[];B=[];nsig=0;nd=0;fig=0
     for f in sorted(glob.glob("prices_todos/*.csv")):
         d=pd.read_csv(f,parse_dates=["date"]).set_index("date"); d.columns=[c.capitalize() for c in d.columns]
         d=d[(d.index>=pd.Timestamp(ini)-pd.Timedelta(days=400))]
         if nome=="2015-2021": d=d[d.index<"2022-01-01"]
         if len(d)<400: continue
         s=bt.compute_signals_windowed(d, didi_window=5, adx_window=3)
         S=s["signal_venda"].values; c=s["Close"]; e70=c.ewm(span=70,adjust=False).mean()
         ok=((c<e70)&((e70/e70.shift(5)-1)*100<-0.15)).values
         i0=int(np.searchsorted(d.index.values, np.datetime64(ini)))
         i0=max(i0,250); nsig+=int(S[i0:].sum()); nd=max(nd,len(d)-i0)
         for i,r in sim(s,S,i0): (A if ok[i] else B).append(r)
     def st(x): 
         x=np.array(x); return f"n={len(x)} acerto {np.mean(x>0)*100:.0f}% expectancia {x.mean():+.2f}R" if len(x) else "n=0"
     print(nome, f"| sinais/dia na amostra {nsig/nd:.1f}")
     print("   abaixo da MME70 caindo:", st(A)); print("   demais:", st(B)); print("   todos:", st(A+B))
