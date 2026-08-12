#!/usr/bin/env python3
"""
Gera imagens dos graficos do TradeDesk (Didi + ADX + Bollinger) para os ativos
selecionados e envia um e-mail HTML com os graficos, dados e link do TradingView.

Le os paineis painel_us.json e painel_b3.json (aplica o mesmo filtro de sinais
bons) e envia via SMTP (Gmail por padrao).

Credenciais vem de variaveis de ambiente (Secrets do GitHub Actions), NUNCA do
codigo:
  EMAIL_FROM     - e-mail que envia (ex.: voce@gmail.com)
  EMAIL_APP_PASS - senha de app do Google (16 caracteres)
  EMAIL_TO       - e-mail que recebe (pode ser o mesmo)

USO: python enviar_email.py
"""
import os, json, base64, io, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------- filtro/ordenacao (igual ao painel) ----------
def _rank(a):
    prim = bool(a.get("bb_primeira")); conf = bool(a.get("confluencia"))
    if conf and prim: return 0
    if conf: return 1
    if prim: return 2
    return 9

def carregar_sinais():
    ativos=[]
    captura=""
    for f in ("painel_us.json","painel_b3.json"):
        try:
            d=json.load(open(f,encoding="utf-8"))
            ativos += d.get("ativos",[])
            if d.get("captura") and not captura: captura=d["captura"]
        except Exception:
            pass
    ativos=[a for a in ativos if _rank(a)<9]
    ativos.sort(key=lambda a:(_rank(a), -(a.get("quality") or -1)))
    return ativos, captura

# ---------- desenhar o grafico de um ativo ----------
def grafico_png(a):
    """Gera PNG (base64) com 3 paineis: Didi, ADX/DI, Bollinger+preco."""
    dates = a.get("dates") or list(range(len(a.get("price",[]))))
    price = a.get("price",[])
    if not price: return None
    n=len(price); x=list(range(n))
    fig,(ax1,ax2,ax3)=plt.subplots(3,1,figsize=(7,7),sharex=True,
                                   gridspec_kw={"height_ratios":[1,1,1.4]})
    fig.patch.set_facecolor("#0d1117")
    for ax in (ax1,ax2,ax3):
        ax.set_facecolor("#0d1117")
        for s in ax.spines.values(): s.set_color("#30363d")
        ax.tick_params(colors="#6b7d92", labelsize=7)
        ax.grid(True, color="#161b22", linewidth=.6)

    # Didi Index
    dc=a.get("didi_curta",[]); dl=a.get("didi_longa",[])
    if dc: ax1.plot(x[:len(dc)],dc,color="#3fb950",lw=1.3,label="curta")
    if dl: ax1.plot(x[:len(dl)],dl,color="#f85149",lw=1.3,label="longa")
    ax1.axhline(0,color="#6b7d92",lw=.6,ls="--")
    ax1.set_ylabel("DIDI",color="#adbac7",fontsize=8)
    ax1.legend(loc="upper left",fontsize=6,facecolor="#161b22",edgecolor="#30363d",labelcolor="#adbac7")

    # ADX / DI
    adx=a.get("adx",[]); dip=a.get("dip",[]); dim=a.get("dim",[])
    if adx: ax2.plot(x[:len(adx)],adx,color="#e6edf3",lw=1.4,label="ADX")
    if dip: ax2.plot(x[:len(dip)],dip,color="#3fb950",lw=1.0,label="DI+")
    if dim: ax2.plot(x[:len(dim)],dim,color="#f85149",lw=1.0,label="DI-")
    ax2.set_ylabel("ADX/DI",color="#adbac7",fontsize=8)
    ax2.legend(loc="upper left",fontsize=6,facecolor="#161b22",edgecolor="#30363d",labelcolor="#adbac7")

    # Bollinger + preco
    bs=a.get("bb_sup",[]); bm=a.get("bb_mid",[]); bi=a.get("bb_inf",[])
    ax3.plot(x,price,color="#58a6ff",lw=1.5,label="Preço")
    if bs: ax3.plot(x[:len(bs)],bs,color="#8b949e",lw=.9)
    if bm: ax3.plot(x[:len(bm)],bm,color="#6e7681",lw=.7,ls="--")
    if bi: ax3.plot(x[:len(bi)],bi,color="#8b949e",lw=.9)
    if bs and bi:
        m=min(len(bs),len(bi))
        ax3.fill_between(x[:m],bi[:m],bs[:m],color="#1f6feb",alpha=.06)
    ax3.set_ylabel("Bollinger",color="#adbac7",fontsize=8)

    # eixo X com poucas datas
    step=max(1,n//6)
    ax3.set_xticks(x[::step])
    ax3.set_xticklabels([str(dates[i])[-5:] if i<len(dates) else "" for i in x[::step]],
                        rotation=0, fontsize=6)

    tk=(a.get("ticker") or "").replace("=X","")
    fig.suptitle(f"{tk}  ·  {a.get('market','')}  ·  nota {round(a.get('quality',0))}",
                 color="#e6edf3",fontsize=11,y=.98)
    fig.tight_layout(rect=[0,0,1,.96])
    buf=io.BytesIO(); fig.savefig(buf,format="png",dpi=110,facecolor="#0d1117")
    plt.close(fig); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ---------- montar HTML do e-mail ----------
def tv_link(a):
    tk=(a.get("ticker") or "").replace("=X","")
    if a.get("tv"): return a["tv"]
    sym = ("BMFBOVESPA:"+tk) if a.get("market")=="B3" else tk
    return "https://www.tradingview.com/chart/?symbol="+sym

def montar_html(ativos, captura, imgs):
    hoje=datetime.date.today().strftime("%d/%m/%Y")
    if not ativos:
        return (f"<div style='font-family:sans-serif'><h2>TradeDesk — {hoje}</h2>"
                f"<p>Nenhum sinal de qualidade hoje (Agulhada do Didi, ações US+B3).</p>"
                f"<p style='color:#888'>Capturado: {captura}</p></div>")
    partes=[f"<div style='font-family:sans-serif;max-width:760px;margin:auto'>"
            f"<h2 style='color:#1f6feb'>TradeDesk — {hoje}</h2>"
            f"<p style='color:#666'>{len(ativos)} sinal(is) · Agulhada do Didi · ações US+B3 · capturado {captura}</p>"]
    for i,a in enumerate(ativos):
        tk=(a.get("ticker") or "").replace("=X","")
        selos=[]
        if a.get("bb_primeira"): selos.append("<span style='background:#e3b341;color:#1a1200;font-size:11px;font-weight:bold;padding:2px 7px;border-radius:5px'>ABERTURA HOJE</span>")
        if a.get("confluencia"): selos.append("<span style='background:#3fb950;color:#fff;font-size:11px;font-weight:bold;padding:2px 7px;border-radius:5px'>3 JUNTOS</span>")
        img_html = f"<img src='cid:graf{i}' style='width:100%;max-width:720px;border:1px solid #30363d;border-radius:8px'/>" if imgs.get(i) else ""
        partes.append(
            f"<div style='border:1px solid #ddd;border-radius:10px;padding:16px;margin:16px 0'>"
            f"<div style='font-size:20px;font-weight:bold'>{tk} "
            f"<span style='font-size:13px;color:#888'>{a.get('market','')}</span> "
            f"<span style='float:right;background:#eef;color:#1f6feb;padding:2px 10px;border-radius:6px'>nota {round(a.get('quality',0))}</span></div>"
            f"<div style='margin:8px 0'>{' '.join(selos)}</div>"
            f"<table style='font-size:14px;color:#333;margin:8px 0'>"
            f"<tr><td style='padding:2px 16px 2px 0'><b>Preço</b></td><td>{a.get('close','—')}</td>"
            f"<td style='padding:2px 16px'><b>Stop</b></td><td style='color:#d33'>{a.get('stop','—')}</td>"
            f"<td style='padding:2px 16px'><b>R%</b></td><td>{a.get('r_pct','—')}%</td></tr></table>"
            f"{img_html}"
            f"<p><a href='{tv_link(a)}' style='display:inline-block;margin-top:10px;background:#1f6feb;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none'>📈 Ver no TradingView</a></p>"
            f"</div>")
    partes.append("<p style='color:#aaa;font-size:12px'>Enviado automaticamente pelo TradeDesk. Leitura para análise própria.</p></div>")
    return "".join(partes)

# ---------- enviar ----------
def enviar():
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage

    EMAIL_FROM=os.environ.get("EMAIL_FROM","")
    EMAIL_PASS=os.environ.get("EMAIL_APP_PASS","")
    EMAIL_TO  =os.environ.get("EMAIL_TO", EMAIL_FROM)
    if not EMAIL_FROM or not EMAIL_PASS:
        print("ERRO: defina EMAIL_FROM e EMAIL_APP_PASS (Secrets do GitHub).")
        return 1

    ativos,captura=carregar_sinais()
    print(f"{len(ativos)} sinal(is) para enviar.")
    imgs={}
    for i,a in enumerate(ativos):
        try:
            p=grafico_png(a)
            if p: imgs[i]=p
        except Exception as e:
            print(f"  falha ao gerar grafico de {a.get('ticker')}: {e}")

    html=montar_html(ativos,captura,imgs)
    hoje=datetime.date.today().strftime("%d/%m/%Y")
    msg=MIMEMultipart("related")
    msg["Subject"]=f"TradeDesk — {len(ativos)} sinal(is) — {hoje}"
    msg["From"]=EMAIL_FROM; msg["To"]=EMAIL_TO
    alt=MIMEMultipart("alternative"); msg.attach(alt)
    alt.attach(MIMEText(html,"html"))
    for i,b64 in imgs.items():
        img=MIMEImage(base64.b64decode(b64)); img.add_header("Content-ID",f"<graf{i}>")
        msg.attach(img)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
            s.login(EMAIL_FROM,EMAIL_PASS)
            s.sendmail(EMAIL_FROM,[EMAIL_TO],msg.as_string())
        print(f"E-mail enviado para {EMAIL_TO}.")
        return 0
    except Exception as e:
        print(f"ERRO ao enviar e-mail: {e}")
        return 1

if __name__=="__main__":
    raise SystemExit(enviar())
