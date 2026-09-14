# COMO RODAR O BACKTEST DOS SINAIS REAIS (Forward Test)
# ============================================================
# Guarde este arquivo. Leia daqui a alguns meses, quando tiver
# sinais suficientes acumulados. Explica tudo do zero.
# ============================================================

## O QUE É ISSO (relembrando)

Todo dia que os scanners rodam, eles GRAVAM automaticamente cada sinal num
arquivo de histórico. Depois de meses, esses arquivos têm centenas de sinais
REAIS — gerados ao vivo, sem "olhar o futuro". O backtest sobre eles mede a
efetividade REAL do scanner (mais honesta que o backtest histórico, que foi
calibrado no passado que já conhecíamos).

Objetivo: descobrir (a) se o scanner funciona de verdade daqui pra frente, e
(b) quais SITUAÇÕES dentro dele valem mais (ex.: no DIDI, o tipo "3 juntos" com
MME70 subindo rende mais que "abertura abaixo"?).

## ONDE FICAM OS DADOS

Dois arquivos, gerados automaticamente na pasta C:\TradeDesk:
  historico_sinais_didi.csv        (sinais da Agulhada)
  historico_sinais_insidebar.csv   (sinais do Insidebar)

Eles CRESCEM sozinhos — cada dia de scan acrescenta as linhas novas. O
GitHub Actions também os salva na nuvem (commit automático). Não precisa fazer
nada para alimentá-los; só deixar os scanners rodando como sempre.

## QUANDO RODAR

NÃO tenha pressa. Com poucos sinais o resultado é ruído (números que mudam
toda hora). Espere acumular:
  - IDEAL: 3 a 6 meses de sinais, ou 100+ sinais por sistema.
  - Antes disso, qualquer conclusão é enganosa. Resista à tentação.

Para ver quantos sinais já tem (no cmd, em C:\TradeDesk):
  Windows:  find /c /v "" historico_sinais_didi.csv
  (mostra o nº de linhas; subtraia 1 do cabeçalho = nº de sinais)

## COMO RODAR (passo a passo)

1. Garanta que os históricos estão atualizados. Se você roda os scanners na
   NUVEM (GitHub Actions), baixe a versão mais recente do repositório:
       cd C:\TradeDesk
       git pull

   (Isso traz os CSVs de histórico que a nuvem foi acumulando.)

2. Rode o backtest de cada sistema:
       python backtest_sinais_reais.py didi
       python backtest_sinais_reais.py insidebar

3. Leia o resultado na tela. Ele mostra:
   - GERAL: nº de trades, win rate, expectância, R acumulado.
   - POR CATEGORIA: a efetividade de cada situação, para você ver quais valem
     mais. No DIDI: por tipo (3JUNTOS/ABERTURA/ADXHOJE), por MME70
     (ACIMA_SUB/ACIMA_LAT/ABAIXO) e a combinação. No Insidebar: por grupo
     (ENTRAR/RADAR).

## COMO INTERPRETAR

- GERAL positivo (exp > 0): o scanner tem edge real ao vivo. Ótimo.
- Compare com o backtest histórico (VALIDACAO_*.md): se parecido (~+0,3R), o
  sistema é ROBUSTO e confiável. Se bem menor, o histórico era otimista — não
  é o fim do mundo, mas ajuste as expectativas (e talvez o risco).
- POR CATEGORIA: se uma categoria tiver expectância MUITO melhor de forma
  CONSISTENTE e com amostra grande (30+ trades), vale priorizá-la. MAS cuidado:
  já vimos (nos testes de "blocos") que diferenças entre categorias muitas
  vezes são ruído. Só confie se a vantagem for grande E a amostra for grande.
- Regra de ouro: win rate parecido entre categorias = provavelmente ruído.
  Vantagem real aparece como win rate e expectância consistentemente melhores.

## SE DER ERRO

- "Arquivo historico_sinais_*.csv nao encontrado": os scanners ainda não
  rodaram com a versão nova, ou você não deu git pull. Rode os scanners /
  atualize o repositório primeiro.
- "ModuleNotFoundError: yfinance": instale com  pip install yfinance
- Poucos trades no resultado: amostra ainda pequena. Espere acumular mais.
- Datas/preços estranhos: o script baixa preços do Yahoo a partir da data de
  cada sinal. Se um ticker saiu de negociação ou mudou de nome, ele é ignorado
  (não quebra o resto).

## LEMBRETES

- Isso é um projeto de MÉDIO PRAZO. O valor aparece com o tempo. Deixe rodando.
- O forward test é a validação mais honesta que existe. Quando amadurecer,
  ele te dá a resposta definitiva sobre a efetividade real dos seus scanners.
- Guarde os CSVs de histórico com carinho — são seu registro real de meses de
  operação. Não apague. Se possível, faça backup de vez em quando.

## RESUMO ULTRA-RÁPIDO (se esquecer tudo)

    cd C:\TradeDesk
    git pull
    python backtest_sinais_reais.py didi
    python backtest_sinais_reais.py insidebar

    -> lê os sinais acumulados e mostra a efetividade real, geral e por
       categoria. Espere 3-6 meses de dados antes de confiar nos números.
