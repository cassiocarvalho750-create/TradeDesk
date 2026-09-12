# TradeDesk Insidebar — Resumo da Validação (Backtest)

Documento de referencia com os resultados dos backtests que validaram o setup.
Gerado a partir dos testes sobre dados historicos diarios (~10 anos).

═══════════════════════════════════════════════════════════════
## 1. A ESTRATEGIA (configuracao final validada)
═══════════════════════════════════════════════════════════════

Estrutura: TENDENCIA -> CONSOLIDACAO -> INSIDE BAR -> ROMPIMENTO.
Compra (LONG), grafico diario.

Filtros de entrada:
  - Tendencia: Close > EMA20; EMA20 subindo (vs 5 candles atras);
    estrutura de alta = HighestHigh(20 recentes) > HighestHigh(20 anteriores).
  - Nao esticado: Close <= EMA20 x 1,08 (max 8% acima).
  - Consolidacao (3 a 10 candles antes do inside bar):
      amplitude da janela < 3,0 x ATR20;
      cada candle com Low >= EMA20(daquele candle) x 0,95 (furar ate 5%).
  - Inside bar classico + compressao: range do IB < 80% do range da mae.
  - Posicao: Low do IB <= EMA20 x 1,05.

Execucao:
  - Entrada: CLOSE do candle que rompe a maxima do inside bar (rompimento
    por fechamento).
  - Stop: ultimo pivo de baixa 3x3 disponivel na entrada.
  - Alvo: 3R (saida integral). Risco por trade: 0,5% do capital.

═══════════════════════════════════════════════════════════════
## 2. RESULTADOS DO BACKTEST — duas cestas, dois alvos
═══════════════════════════════════════════════════════════════

  Cesta          Alvo   Trades  WinRate  Expectancia  Acumulado
  -----------------------------------------------------------------
  Techs (38)      1R      351     60%      +0,195R        +68R
  Techs (38)      2R      351     51%      +0,344R       +120R
  Techs (38)      3R      351     48%      +0,463R       +162R
  Variada (39)    1R      603     60%      +0,185R       +112R
  Variada (39)    2R      603     49%      +0,276R       +166R
  Variada (39)    3R      603     47%      +0,373R       +225R  <== escolhido

  Observacao: o padrao e IDENTICO nas duas cestas. Alvo maior = menor win rate
  mas MAIOR expectancia e acumulado. O 1R tem o maior win rate (~60%) mas o
  MENOR retorno — prova de que "acertar mais" nao significa "ganhar mais".
  A expectancia do 3R (+0,37 variada / +0,46 techs) e do 1R (+0,185 / +0,195)
  sao proximas entre cestas -> comportamento estavel = sistema robusto.

  Cesta "Techs": NVDA, MSFT, AMD, META, GOOG, TSM, etc. (tecnologia).
  Cesta "Variada": bancos, energia, consumo, saude, industria, utilities,
    + acoes B3 (JPM, KO, XOM, JNJ, CAT, VALE3, PETR4, ITUB4, etc.).

═══════════════════════════════════════════════════════════════
## 3. CONCLUSOES
═══════════════════════════════════════════════════════════════

1. ALVO 3R > 2R nas DUAS cestas. Deixar o lucro correr ate 3R rende mais que
   sair em 2R, apesar do win rate um pouco menor. Confirmado de forma
   independente (nao foi so efeito das techs).

2. SETUP E ROBUSTO. Na cesta variada (ativos totalmente diferentes das techs),
   manteve expectancia positiva (+0,373R com 3R) e win rate ~47%, proximo ao
   das techs. Nao desabou -> o resultado nao era overfitting.

3. AMOSTRA GRANDE. 603 trades na cesta variada dao confianca estatistica real.
   Funcionou em setores variados: bancos, industria, varejo, mineracao,
   eletricas — a logica "inside bar apos consolidacao em tendencia" e
   universal, nao especifica de um setor.

4. HISTORICO DE OTIMIZACOES (o que mudou e por que):
   - Alvo 2R -> 3R: melhor expectancia (backtest).
   - Estrutura HH+HL (pivos) -> HighestHigh recente>anterior: o HH+HL era
     rigido demais e piorava tudo; a troca subiu +65R -> +140R e win 41%->47%.
   - Consolidacao afrouxada (ampl 2,5->3,0; penetracao 2%->5%): +140R -> +162R
     nas techs; deixou passar bons casos sem descaracterizar o setup.
   - Stop: testado pivo 2x2, min 5/10 candles, min do IB — o pivo 3x3 (atual)
     ficou entre os melhores e com melhor win rate. Stops mais colados PIORAM
     (sao estopados por pullbacks normais).
   - Saida parcial (50% em 1R + 50% em 3R): testada, da win 54% mas expectancia
     menor. Optou-se por 3R integral (maior retorno, perfil aguenta win menor).


══════════════════════════════════════════════════════════## 3b. ESTRATEGIA DE SAIDA (DEFINITIVA)
═══════════════════════════════════════════════════════════════

Operacional:
  1. Entrada no rompimento da maxima do inside bar (Close acima).
  2. Stop inicial = ultimo pivo 3x3.
  3. Ao atingir 2R: realizar 50% da posicao E mover o stop da metade
     restante para o BREAKEVEN (preco de entrada).
  4. Metade restante corre ate 3R.

Racional: segura a posicao inteira ate 2R (captura mais dos movimentos
medios antes de realizar), e so entao protege com breakeven. Escolhida
apos testes proprios comparando com parcial 1R e saidas integrais.

(Historico dos testes anteriores — parcial 1R+3R, alvos integrais 1R/2R/3R
— permanece registrado nas versoes anteriores deste doc / nas ferramentas
teste_parcial2.py e teste_be.py para reproducao.)

═══════════════════════════════════════════════════════════════
## 4. RESSALVAS HONESTAS (ler sempre)
═══════════════════════════════════════════════════════════════

- Os backtests NAO incluem CUSTOS (corretagem, spread, slippage). Cada trade
  tem custo real que reduz o resultado. Com centenas de trades, isso soma.
  O resultado real fica ABAIXO dos numeros acima.
- Passado nao garante futuro. Backtest mostra como o setup SE TERIA comportado,
  nao como vai se comportar.
- O resultado e de ~10 ANOS. Diluido, e algo como +5% a +8% ao ano sobre o
  capital (risco fixo 0,5%/trade) — retorno solido de swing, nao "ficar rico".
- Execucao importa: entrar no rompimento, respeitar o stop (mesmo quando parece
  longe), e deixar correr ate 3R sem sair antes por ansiedade. Sem disciplina,
  o resultado real nao bate com o backtest.
- Sequencias de perda de 5-7 seguidas sao ESPERADAS (win ~47%), nao sinal de
  falha. Manter o risco de 0,5% permite atravessa-las.

═══════════════════════════════════════════════════════════════
## 5. FERRAMENTAS (como reproduzir/testar)
═══════════════════════════════════════════════════════════════

  python backtest_insidebar.py <pasta> <alvoR>
     ex.: python backtest_insidebar.py prices 3
  python otimizar_insidebar.py <pasta>       (varia parametros)
  python diagnostico_insidebar.py TICKER     (checa 1 ativo)
  python baixar_dados.py <pasta> <tickers>   (baixa dados p/ novas cestas)

  Ver TESTE_ROBUSTEZ.md e COMO_RODAR_BACKTEST.md para detalhes.

  Parametros ficam no topo de insidebar_engine.py (EMA_LEN, CONS_*, IB_*, etc.)
  e ALVO_R no scanner_insidebar.py.
