# TradeDesk Agulhada do Didi — Resumo da Validação (Backtest)

Documento de referencia com os resultados dos backtests que validaram o setup
da Agulhada. Testes sobre dados historicos diarios (~10 anos), duas cestas.

═══════════════════════════════════════════════════════════════
## 1. O SETUP (sinal de compra — como o scanner detecta)
═══════════════════════════════════════════════════════════════

Indicadores: Bollinger (8,2); Didi Index (medias 3/8/20); ADX(8,8)/DMI; TRIX.
Sinal de COMPRA (diario) exige TUDO:
  - Bollinger ABRINDO (largura crescendo hoje).
  - Candle VERDE (Close > Open).
  - DIDI: cruzamento MA3>MA8 recente (na janela) E ainda comprado hoje
    (didi3 > 0 e nao caindo).
  - ADX COMPRADO (as 3 condicoes hoje: subindo + DI+>DI- + ADX>=100% do DI-;
    OU a 1a virada na janela) E ADX SUBINDO hoje.
  Painel mostra so os "bons": ABERTURA HOJE, 3 JUNTOS, ou ADX virou hoje.

Execucao (definida apos backtest):
  - Entrada: fechamento do candle do sinal.
  - Stop: ultimo pivo de baixa 3x3.
  - Saida: parcial 50% em 2R (primeiro objetivo, mostrado no card) + restante
    sai quando o TRIX vira (EMA4 do TRIX cruza a EMA9 para baixo) — acompanhado
    no grafico (TradingView), nao e um preco fixo no card.

═══════════════════════════════════════════════════════════════
## 2. RESULTADOS DO BACKTEST — 3 stops x 2 saidas, sem sobreposicao
═══════════════════════════════════════════════════════════════

(sem sobreposicao = nao abre novo trade enquanto um estiver aberto)

CESTA TECHS (36 ativos):
  Stop       Saida   Trades  Win   Exp       Acum
  ----------------------------------------------------
  min_ent    TRIX     1947   40%   +0,537R   +1046R
  min_ent    ADX      2262   36%   +0,440R    +996R
  min_ant    TRIX     1536   43%   +0,428R    +657R
  min_ant    ADX      2200   40%   +0,180R    +395R
  pivo       TRIX      984   47%   +0,503R    +494R
  pivo       ADX      2191   41%   +0,084R    +184R

CESTA VARIADA (110 ativos):
  Stop       Saida   Trades  Win   Exp       Acum
  ----------------------------------------------------
  min_ent    TRIX     6426   38%   +0,269R   +1730R
  min_ent    ADX      7636   34%   +0,222R   +1694R
  min_ant    TRIX     5029   40%   +0,292R   +1469R
  min_ant    ADX      7420   38%   +0,122R    +904R
  pivo       TRIX     3327   44%   +0,346R   +1151R  <== escolhido
  pivo       ADX      7393   40%   +0,066R    +490R

═══════════════════════════════════════════════════════════════
## 3. CONCLUSOES
═══════════════════════════════════════════════════════════════

1. SAIDA TRIX >> SAIDA ADX, nas DUAS cestas, com qualquer stop. O "kick do ADX"
   (sair quando o ADX vira p/ baixo) corta os trades cedo demais e destroi a
   expectancia (pivo+ADX = +0,066R na variada, quase neutro). A saida pelo TRIX
   e claramente superior.

2. STOP no PIVO 3x3 e o melhor na cesta variada (a mais confiavel): maior win
   rate (44%) e maior expectancia (+0,346R) entre as saidas TRIX. Mesmo padrao
   do Insidebar — stop mais "largo" (pivo) protege melhor contra ruido.
   -> CONFIGURACAO ESCOLHIDA: stop pivo 3x3 + parcial 2R + saida TRIX.

3. ROBUSTO: a expectancia caiu das techs p/ a variada (+0,503R -> +0,346R no
   pivo+TRIX), queda saudavel (parte do brilho nas techs era vies da cesta),
   mas manteve-se claramente positiva em 3327 trades. Nao era overfitting.

4. MUITO MAIS ATIVA que o Insidebar: a Agulhada gera ~10x mais trades (3327 vs
   ~350 na variada). Expectancia parecida (~+0,35R), mas volume muito maior.
   Isso significa mais R acumulado no total, POReM muito mais CUSTOS reais
   (corretagem, spread, slippage) que o backtest nao conta. Com milhares de
   trades, custos comem parte relevante da expectancia. Considerar isso ao
   alocar capital entre os dois sistemas.

═══════════════════════════════════════════════════════════════
## 4. RESSALVAS HONESTAS (ler sempre)
═══════════════════════════════════════════════════════════════

- Backtest NAO inclui custos. Na Agulhada isso pesa MAIS que no Insidebar,
  pelo volume de trades. O resultado liquido real fica bem abaixo do bruto.
- A Agulhada tem MAIS componentes (DIDI, ADX, BB, TRIX, janelas) = mais graus
  de liberdade = maior risco de overfitting. Por isso o teste na cesta variada
  foi essencial (e passou).
- Passado nao garante futuro.
- A saida TRIX exige acompanhamento no grafico (nao e ordem fixa). Se voce nao
  sair disciplinadamente quando o TRIX virar, o resultado real difere do teste.
- Sequencias de perda existem (win 44%). Manter risco por trade controlado.

═══════════════════════════════════════════════════════════════
## 5. FERRAMENTAS
═══════════════════════════════════════════════════════════════

  python backtest_didi.py <pasta>        (roda as 6 combinacoes stop x saida)
  python backtest_insidebar.py <pasta> <alvoR>   (o outro sistema)
  python baixar_dados.py <pasta> <tickers>       (montar cestas)

  Parametros do sinal ficam em bt_engine.py (ADX_DIM_RATIO, janelas DIDI/ADX,
  Bollinger) e no scanner.py (calculo do stop pivo e alvo 2R).
