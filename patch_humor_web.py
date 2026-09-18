#!/usr/bin/env python3
"""
Injeta o painel de HUMOR DO S&P 500 nas paginas do site (docs/*.html).
Insere o snippet logo apos </header>. Idempotente (nao duplica).

USO:  python patch_humor_web.py            # todas as paginas docs/*.html
      python patch_humor_web.py docs/TradeDesk.html   # so as indicadas

Precisa do arquivo _humor_web_snippet.html na mesma pasta deste script.
"""
import sys, glob, io, os

MARCA = "[humor_sp500_web]"

def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    snip_path = os.path.join(aqui, "_humor_web_snippet.html")
    if not os.path.exists(snip_path):
        print("Falta _humor_web_snippet.html na pasta do script."); return
    snip = io.open(snip_path, encoding="utf-8").read().strip()

    alvos = sys.argv[1:] or sorted(glob.glob("docs/*.html"))
    # so paginas de scanner (tem </header>); pula paginas sem header
    feitos = 0
    for path in alvos:
        try:
            src = io.open(path, encoding="utf-8").read()
        except Exception as e:
            print(f"  {path}: erro ao ler ({e})"); continue
        if MARCA in src:
            print(f"  {path}: ja tinha o painel"); continue
        if "</header>" not in src:
            print(f"  {path}: sem <header> — pulado"); continue
        src2 = src.replace("</header>", "</header>\n" + snip, 1)
        io.open(path, "w", encoding="utf-8").write(src2)
        print(f"  {path}: painel inserido OK"); feitos += 1
    print(f"\n{feitos} pagina(s) atualizada(s).")

if __name__ == "__main__":
    main()
