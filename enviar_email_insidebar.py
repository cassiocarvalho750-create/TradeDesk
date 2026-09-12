#!/usr/bin/env python3
"""
Envia por e-mail os sinais do INSIDEBAR: quadro "entrar hoje" (rompimento) e
"radar" (inside bar formado). Le painel_insidebar.json. Gráfico de candles +
EMA20 por ativo. Credenciais via Secrets (EMAIL_FROM, EMAIL_APP_PASS, EMAIL_TO).
USO: python enviar_email_insidebar.py
"""
import os, json, base64, io, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def carregar():
    try:
        d=json.load(open("painel_insidebar.json",encoding="utf-8"))
    except Exception:
        return [],[],""
    return d.get("entrar",[]), d.get("ativos",[]), d.get("captura","")

def grafico_png(a):
    """Candles + EMA20 + linhas de entrada/stop. Retorna base64 PNG."""
    price=a.get("price",[]); o=a.get("o",[]); h=a.get("h",[]); l=a.get("l",[]); ema=a.get("ema20s",[])
    if not price: return None
    n=len(price); x=list(range(n))
    fig,ax=plt.subplots(figsize=(7,3.2)); fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    for sp in ax.spines.values(): sp.set_color("#30363d")
    ax.tick_params(colors="#6b7d92", labelsize=7); ax.grid(True,color="#161b22",lw=.6)
    # EMA20
    if ema: ax.plot(x[:len(ema)],[v if v is not None else np.nan for v in ema],color="#e3b341",lw=1.3,label="EMA20")
    # candles
    if o and h and l and len(o)==n:
        cw=0.6
        for i in range(n):
            if price[i] is None or o[i] is None: continue
            up=price[i]>=o[i]; col="#3fb950" if up else "#f85149"
            ax.plot([i,i],[l[i],h[i]],color=col,lw=.7,zorder=3)
            y0,y1=min(o[i],price[i]),max(o[i],price[i])
            ax.add_patch(plt.Rectangle((i-cw/2,y0),cw,max(y1-y0,1e-9),facecolor=col,edgecolor=col,lw=.5,zorder=4))
    else:
        ax.plot(x,price,color="#58a6ff",lw=1.4)
    # entrada / stop
    if a.get("entry") is not None: ax.axhline(a["entry"],color="#3fb950",lw=.8,ls="--")
    if a.get("stop")  is not None: ax.axhline(a["stop"], color="#f85149",lw=.8,ls="--")
    tk=(a.get("ticker") or "")
    fig.suptitle(f"{tk} · {a.get('market','')}",color="#e6edf3",fontsize=10,y=.98)
    ax.legend(loc="upper left",fontsize=6,facecolor="#161b22",edgecolor="#30363d",labelcolor="#adbac7")
    fig.tight_layout(rect=[0,0,1,.95])
    buf=io.BytesIO(); fig.savefig(buf,format="png",dpi=110,facecolor="#0d1117"); plt.close(fig); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

def tv_link(a):
    tk=(a.get("ticker") or "")
    if a.get("tv"): return a["tv"]
    sym=("BMFBOVESPA:"+tk) if a.get("market")=="B3" else tk
    return "https://www.tradingview.com/chart/?symbol="+sym

def bloco_ativos(ativos, imgs, base_idx, entrar):
    partes=[]
    for k,a in enumerate(ativos):
        i=base_idx+k
        tk=a.get("ticker","")
        selo = ('<span style="background:#3fb950;color:#fff;font-size:11px;font-weight:bold;padding:2px 7px;border-radius:5px">ENTRAR HOJE</span>'
                if entrar else '<span style="background:#1f6feb;color:#fff;font-size:11px;font-weight:bold;padding:2px 7px;border-radius:5px">INSIDE BAR</span>')
        img=f"<img src='cid:ib{i}' style='width:100%;max-width:720px;border:1px solid #30363d;border-radius:8px'/>" if imgs.get(i) else ""
        alvo = a.get("alvo_final") or a.get("alvo2r") or a.get("alvo_parcial")
        partes.append(
            f"<div style='border:1px solid #ddd;border-radius:10px;padding:14px;margin:14px 0'>"
            f"<div style='font-size:19px;font-weight:bold'>{tk} <span style='font-size:12px;color:#888'>{a.get('market','')}</span> {selo}</div>"
            f"<table style='font-size:14px;color:#333;margin:8px 0'>"
            f"<tr><td style='padding:2px 14px 2px 0'><b>Entrada</b></td><td>{a.get('entry','—')}</td>"
            f"<td style='padding:2px 14px'><b>Stop (pivô)</b></td><td style='color:#d33'>{a.get('stop','—')}</td>"
            f"<td style='padding:2px 14px'><b>Parcial 2R</b></td><td>{a.get('parcial2r','—')}</td></tr></table>"
            f"{img}"
            f"<p><a href='{tv_link(a)}' style='display:inline-block;margin-top:10px;background:#1f6feb;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none'>📈 Ver no TradingView</a></p>"
            f"</div>")
    return "".join(partes)

def enviar():
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage
    FROM=os.environ.get("EMAIL_FROM",""); PASS=os.environ.get("EMAIL_APP_PASS",""); TO=os.environ.get("EMAIL_TO",FROM)
    if not FROM or not PASS:
        print("ERRO: defina EMAIL_FROM e EMAIL_APP_PASS (Secrets do GitHub)."); return 1
    entrar, radar, captura = carregar()
    hoje=datetime.date.today().strftime("%d/%m/%Y")
    # gerar imagens (indice global)
    imgs={}; idx=0; idx_entrar=idx
    for a in entrar:
        p=grafico_png(a)
        if p: imgs[idx]=p
        idx+=1
    idx_radar=idx
    for a in radar:
        p=grafico_png(a)
        if p: imgs[idx]=p
        idx+=1
    # HTML
    html=[f"<div style='font-family:sans-serif;max-width:760px;margin:auto'>"
          f"<h2 style='color:#1f6feb'>TradeDesk Insidebar — {hoje}</h2>"
          f"<p style='color:#666'>Capturado {captura}. Estrategia: entrada no rompimento, stop no pivo 3x3, parcial 50% em 2R (breakeven) + resto ate 3R.</p>"]
    if entrar:
        html.append(f"<h3 style='color:#2ea043'>🎯 Entrar hoje ({len(entrar)})</h3>")
        html.append(bloco_ativos(entrar, imgs, idx_entrar, True))
    if radar:
        html.append(f"<h3 style='color:#1f6feb'>📡 Radar — inside bar formado hoje ({len(radar)})</h3>")
        html.append(bloco_ativos(radar, imgs, idx_radar, False))
    if not entrar and not radar:
        html.append("<p>Nenhum sinal do Insidebar hoje.</p>")
    html.append("<p style='color:#aaa;font-size:12px'>Enviado automaticamente pelo TradeDesk. Leitura para analise propria.</p></div>")

    msg=MIMEMultipart("related")
    msg["Subject"]=f"TradeDesk Insidebar — {len(entrar)} p/ entrar, {len(radar)} no radar — {hoje}"
    msg["From"]=FROM; msg["To"]=TO
    alt=MIMEMultipart("alternative"); msg.attach(alt); alt.attach(MIMEText("".join(html),"html"))
    for i,b64 in imgs.items():
        im=MIMEImage(base64.b64decode(b64)); im.add_header("Content-ID",f"<ib{i}>"); msg.attach(im)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as srv:
            srv.login(FROM,PASS); srv.sendmail(FROM,[TO],msg.as_string())
        print(f"E-mail Insidebar enviado para {TO}."); return 0
    except Exception as e:
        print(f"ERRO ao enviar: {e}"); return 1

if __name__=="__main__":
    raise SystemExit(enviar())
