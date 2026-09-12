#!/usr/bin/env python3
"""Junta os CSVs de varias pastas de precos numa unica pasta (sem duplicar
ativos). Uso: python juntar_cestas.py destino pasta1 pasta2 [pasta3...]
Ex.:  python juntar_cestas.py prices_todos prices prices_teste
"""
import sys, os, glob, shutil
if len(sys.argv)<3:
    print("uso: python juntar_cestas.py <destino> <pasta1> <pasta2> ...")
    sys.exit()
dest=sys.argv[1]; fontes=sys.argv[2:]
os.makedirs(dest, exist_ok=True)
vistos=set(); copiados=0; pulados=0
for pasta in fontes:
    for a in sorted(glob.glob(os.path.join(pasta,"*.csv"))):
        nome=os.path.basename(a).lower()
        if nome in vistos:
            pulados+=1; continue   # ja existe (duplicata) — nao copia
        vistos.add(nome)
        shutil.copy(a, os.path.join(dest,nome))
        copiados+=1
print(f"Juntado em '{dest}/': {copiados} ativos unicos (puladas {pulados} duplicatas)")
print(f"Agora rode: python backtest_didi_blocos.py {dest}")
