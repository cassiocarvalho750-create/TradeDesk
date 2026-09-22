# COMO RODAR O FORWARD TEST DA CONFLUÊNCIA
# ============================================================
# Guarde este arquivo. Leia daqui a alguns meses, quando já
# tiver sinais acumulados. Explica tudo do zero.
# ============================================================

## O QUE É ISSO (relembrando)

Todo dia que os scanners rodam (com o pregão já fechado), o sistema tira uma
"foto" da aba **Confluência** e GRAVA cada ativo numa linha do arquivo
`historico_confluencia.csv`. Depois de meses, esse arquivo tem centenas de
sinais REAIS — gerados ao vivo, sem "olhar o futuro".

O forward test roda em cima desses sinais e mede a efetividade REAL da
confluência. É a validação mais honesta que existe, porque os sinais foram
capturados no momento, não escolhidos olhando o passado.

O que queremos descobrir:
  - a **confluência funciona** de verdade daqui pra frente?
  - qual **prioridade** rende mais?
      🥇 1 = DIDI entrou + Qullamäggie rompeu
      🔵 2 = DIDI entrou + Qullamäggie consolidando
      🥈 3 = só Qullamäggie rompeu
         4 = só DIDI
  - a **ordem** em que os ativos aparecem na fila prediz os melhores trades?
    (topo da lista vs resto; 1º do subgrupo vs resto)
  - a **faixa de momentum** (forte/médio/fraco) e o **selo ELITE** ajudam?

## ONDE FICAM OS DADOS

Um arquivo, gerado automaticamente na pasta C:\TradeDesk:

    historico_confluencia.csv

Ele CRESCE sozinho — cada dia de scan com pregão fechado acrescenta as linhas
novas. O GitHub Actions também o salva na nuvem (commit automático). Você não
precisa fazer nada para alimentá-lo; só deixar os scanners rodando como sempre.

Cada linha guarda tudo que o backtest precisa:
  - data, ordem_geral (posição na fila toda), prioridade, ordem_subgrupo
    (posição dentro da prioridade)
  - ticker, mercado
  - entrada, stop, alvo (3R), r_pct
  - tem_didi, q_rompeu, q_consolidando, elite
  - mom1/mom3/mom6, faixa_mom (forte/médio/fraco)
  - didi_tipo, quality (contexto DIDI) · consol_dias, acima_ema20 (contexto Qulla)

### À prova de erro (por que confiar nos dados)
  - Só grava quando TODOS os mercados da foto já fecharam (evita preço
    provisório de pregão aberto).
  - Pula se houver algum ativo "em formação" (candle do dia ainda aberto).
  - Não duplica o mesmo (data, ticker) — rodar o scanner 2x no dia é seguro.

## QUANDO RODAR

NÃO tenha pressa. Com poucos sinais o resultado é ruído (números que mudam a
cada semana). Espere acumular:
  - IDEAL: 3 a 6 meses de sinais, ou 100+ sinais no total.
  - Antes disso, qualquer conclusão engana. Resista à tentação.

Para ver quantos sinais já tem (no cmd, em C:\TradeDesk):

    find /c /v "" historico_confluencia.csv

(mostra o nº de linhas; subtraia 1 do cabeçalho = nº de sinais)

## COMO RODAR (passo a passo)

1. Atualize os dados. Se os scanners rodam na NUVEM (GitHub Actions), traga a
   versão mais recente do repositório, que inclui o CSV que a nuvem acumulou:

       cd C:\TradeDesk
       git pull

2. (Se ainda não tiver) instale o yfinance, que baixa os preços:

       pip install yfinance

3. Rode o forward test:

       python backtest_confluencia.py

   Opções (não obrigatórias):
       python backtest_confluencia.py --alvo 3 --hold 60
       --alvo  = alvo em R (padrão 3, o mesmo do setup Qullamäggie)
       --hold  = máximo de dias no trade (padrão 60)

4. Leia o resultado na tela.

## COMO INTERPRETAR

O relatório tem 5 blocos:

- **GERAL** — nº de trades, win rate, expectância (R por trade) e R acumulado.
  Se a expectância for positiva (exp > 0), a confluência tem edge real ao vivo.

- **Por PRIORIDADE** — a pergunta central. Se a prioridade 1 (os dois setups
  confirmam) tiver expectância consistentemente maior que a 4 (só DIDI), a
  confluência está fazendo o que promete: quanto mais forte o cruzamento, melhor
  o trade. Se a 1 não ganhar da 4, a confluência não está agregando — e aí vale
  repensar.

- **Por POSIÇÃO na fila** — se "topo3 (fila geral)" e "1º do subgrupo" renderem
  mais que o resto, a ordenação (momentum + menor R%) está mesmo colocando os
  melhores no topo. É a validação da regra de ordenação.

- **Por FAIXA de momentum** — forte vs médio vs fraco. Confirma (ou não) que
  momentum é fator de sucesso, como você suspeitava.

- **Por selo ELITE** — se os que cumprem os critérios rigorosos do criador
  rendem mais, o selo vale como filtro de qualidade.

### Regras de ouro (para não se enganar)
  - Só confie numa vantagem que seja GRANDE **e** com amostra GRANDE (30+
    trades no grupo). Diferença pequena = quase sempre ruído.
  - Win rate parecido entre grupos = provavelmente ruído. Vantagem real aparece
    como win rate E expectância consistentemente melhores.
  - Compare o GERAL com o backtest histórico do Qulla (~+0,80R/trade): se
    parecido, o sistema é robusto; se bem menor, o histórico era otimista —
    ajuste as expectativas (e talvez o risco).

## SOBRE A PRIORIDADE 4 (só DIDI)

Os sinais só-DIDI não têm preço de rompimento do Qulla, então usamos o
**fechamento do dia** como entrada (o mesmo critério de entrada do DIDI) e a
mínima registrada como stop. Assim a prioridade 4 também entra no backtest e dá
para compará-la com as outras.

## SE DER ERRO

- "Arquivo historico_confluencia.csv nao encontrado": os scanners ainda não
  rodaram com a versão nova, ou faltou o `git pull`. Atualize primeiro.
- "... esta vazio (so cabecalho)": o arquivo existe mas ainda não houve nenhum
  scan com pregão fechado. Espere os scans diários alimentarem.
- "ModuleNotFoundError: yfinance": rode `pip install yfinance`.
- Poucos trades no resultado: amostra ainda pequena. Espere acumular mais.
- Muitos "ignorados: sem historico de preco": ticker saiu de negociação ou
  mudou de nome; é ignorado sem quebrar o resto.

## LEMBRETES

- Isso é um projeto de MÉDIO PRAZO. O valor aparece com o tempo. Deixe rodando.
- Guarde o `historico_confluencia.csv` com carinho — é seu registro real de
  meses de operação. Não apague. Faça backup de vez em quando.

## RESUMO ULTRA-RÁPIDO (se esquecer tudo)

    cd C:\TradeDesk
    git pull
    pip install yfinance     (só na 1ª vez)
    python backtest_confluencia.py

    -> lê os sinais da Confluência acumulados e mostra a efetividade real:
       geral, por prioridade, por posição na fila, por faixa de momentum e por
       selo elite. Espere 3-6 meses de dados antes de confiar nos números.

# ------------------------------------------------------------
# NOTA: o registro antigo por setup isolado (historico_sinais_didi.csv e
# historico_sinais_insidebar.csv, com o backtest_sinais_reais.py) continua
# existindo, mas o foco agora é a CONFLUÊNCIA — que é o que você usa para
# decidir os trades. Se um dia quiser rodar aqueles, o comando era:
#     python backtest_sinais_reais.py didi
#     python backtest_sinais_reais.py insidebar
# ------------------------------------------------------------
