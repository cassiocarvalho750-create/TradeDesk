#!/usr/bin/env python3
"""
============================================================================
PATCH — injeta o painel de HUMOR DO S&P 500 nos seus scanners
============================================================================
Roda UMA vez, na pasta dos scanners. Ele:
  1. garante 'import humor_sp500 as hs' no topo de cada scanner;
  2. injeta o painel HTML logo apos <body> em cada HTML gerado, sem que voce
     precise mexer no codigo na mao.

Funciona mesmo que seus scanners estejam um pouco diferentes dos que eu vi:
ele procura o ponto onde o HTML e escrito e insere a linha ali.

USO:
    python patch_humor.py                 # aplica em todos os scanner*.py da pasta
    python patch_humor.py scanner.py scanner_insidebar.py   # so nos indicados

Precisa do arquivo humor_sp500.py na mesma pasta.
E idempotente: rodar de novo nao duplica nada.
============================================================================
"""
import sys, glob, re, io

MARCA = "# [humor_sp500] painel injetado"

def patch_arquivo(path):
    src = io.open(path, encoding="utf-8").read()
    if MARCA in src:
        print(f"  {path}: ja tinha o painel (nada a fazer)")
        return False

    orig = src

    # 1) garante o import (apos a primeira linha 'import bt_engine' ou no topo dos imports)
    if "import humor_sp500" not in src:
        m = re.search(r"^import bt_engine.*$", src, re.M)
        if m:
            src = src[:m.end()] + "\nimport humor_sp500 as hs  " + MARCA + src[m.end():]
        else:
            # cai no primeiro bloco de import
            m = re.search(r"^import .*$", src, re.M)
            ins = "\nimport humor_sp500 as hs  " + MARCA
            src = src[:m.end()] + ins + src[m.end():]

    # 2) injeta o painel na string html ANTES de ela ser gravada.
    #    Procuramos a variavel que guarda o html final e inserimos apos <body>.
    #    Estrategia: logo antes de a escrita acontecer, fazemos
    #        html = html.replace("<body>", "<body>"+hs.painel_html(), 1)
    #    Detecta o nome da variavel escrita em open(...).write(<var>).
    padrao_write = re.compile(r'open\(\s*([\w.]+)\s*,\s*["\']w["\'].*?\)\.write\(\s*([A-Za-z_]\w*)\s*\)')
    injetou = False
    novas_linhas = []
    for m in padrao_write.finditer(src):
        var_html = m.group(2)
        # so injeta se a variavel parece ser html (contem '<body>' em algum lugar do arquivo)
        if var_html in ("html",) or ("<body>" in src and var_html == "html"):
            novas_linhas.append((m.start(), var_html))

    # aplica a injecao imediatamente antes de cada open(...).write(html)
    if novas_linhas:
        # trabalha de tras pra frente pra nao baguncar os indices
        for pos, var_html in sorted(novas_linhas, reverse=True):
            # descobre a indentacao da linha do open(...)
            linha_ini = src.rfind("\n", 0, pos) + 1
            indent = re.match(r"[ \t]*", src[linha_ini:]).group(0)
            inj = (f'{indent}{var_html} = {var_html}.replace("<body>", '
                   f'"<body>"+hs.painel_html(), 1)  {MARCA}\n')
            src = src[:linha_ini] + inj + src[linha_ini:]
            injetou = True

    if not injetou:
        print(f"  {path}: NAO achei onde injetar (open(...).write(html)). "
              f"Verifique manualmente — veja o LEIA.")
        # ainda salva o import, que nao atrapalha
    if src != orig:
        io.open(path, "w", encoding="utf-8").write(src)
        print(f"  {path}: painel injetado {'OK' if injetou else '(so o import)'}")
        return True
    return False

def main():
    alvos = sys.argv[1:] or sorted(glob.glob("scanner*.py"))
    alvos = [a for a in alvos if a not in ("humor_sp500.py", "patch_humor.py")]
    if not alvos:
        print("Nenhum scanner*.py encontrado nesta pasta.")
        return
    print(f"Aplicando o painel de humor do S&P 500 em: {', '.join(alvos)}\n")
    for a in alvos:
        try:
            patch_arquivo(a)
        except Exception as e:
            print(f"  {a}: erro — {e}")
    print("\nPronto. Rode um scanner normalmente; o painel aparece no topo do HTML.")

if __name__ == "__main__":
    main()
