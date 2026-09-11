# Como rodar o BACKTEST do Insidebar

O backtest roda LOCALMENTE no seu PC. Ele le precos historicos, aplica a
logica do Insidebar em cada dia do passado, simula os trades (entrada no
fechamento do rompimento, stop no pivo 3x3, alvo em 3R) e mostra o resultado.
Nao mexe no seu scanner do dia a dia — e uma ferramenta separada de analise.

## Passo 1 — Colocar os dados no lugar

Descompacte o all_prices.zip dentro de C:\TradeDesk, de modo que fique:

    C:\TradeDesk\prices\nvda.csv
    C:\TradeDesk\prices\msft.csv
    ... (os 38 arquivos CSV)

ATENCAO (pegadinha do Windows): as vezes o descompactador cria uma pasta a
mais (ex.: C:\TradeDesk\all_prices\prices\). Se isso acontecer, mova a pasta
"prices" para dentro de C:\TradeDesk. Os CSVs tem que estar em
C:\TradeDesk\prices\ diretamente.

Para conferir, no cmd:
    dir C:\TradeDesk\prices
Deve listar nvda.csv, msft.csv, etc.

## Passo 2 — Abrir o cmd na pasta

No Explorer, va ate C:\TradeDesk, clique na barra de endereco, apague, digite
"cmd" e Enter. Ou abra o cmd e:
    cd C:\TradeDesk

## Passo 3 — Rodar o backtest

    python backtest_insidebar.py prices

Mostra, por ativo: numero de trades, win rate e expectancia (em R). No fim, o
total agregado. Tambem gera o arquivo trades_insidebar.csv (abre no Excel) com
cada trade: ticker, data de entrada, entry, stop, alvo, data de saida, e o
resultado em R.

## Passo 4 (opcional) — Otimizador de parametros

    python otimizar_insidebar.py prices

Testa variacoes de cada parametro (compressao, contracao, amplitude, nao
esticado, alvo) e mostra o efeito de cada um na expectancia. Foi assim que
descobrimos que o alvo 3R deu melhor resultado que 2R.

## Testar com SEUS proprios dados

Os CSVs precisam ter as colunas: date,open,high,low,close,volume
(o cabecalho exato). Coloque quantos ativos quiser na pasta prices (ou crie
outra pasta e passe o nome dela no comando, ex.: python backtest_insidebar.py
minha_pasta). Quanto mais ativos e mais historico, mais confiavel o resultado.

## Se der erro

- "can't open file" ou "No such file": o Python nao achou o script. Confira
  que voce esta em C:\TradeDesk (o script tem que estar ali).
- "prices" nao encontrado / 0 ativos: os CSVs nao estao em C:\TradeDesk\prices.
- "ModuleNotFoundError: pandas/numpy": rode
    pip install pandas numpy
- Demora: e normal levar de alguns segundos a 1-2 minutos, dependendo de
  quantos ativos.

## Lembrete importante (para nao superestimar)

O backtest mostra como o setup SE TERIA comportado no passado, nesses ativos.
Nao inclui custos (corretagem, spread, slippage) e a cesta atual e enviesada
para acoes de tecnologia que subiram muito. O resultado real tende a ser mais
modesto. Use como validacao e estudo, nao como promessa de retorno futuro.
