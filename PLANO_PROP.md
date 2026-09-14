# TradeDesk — Plano de Operação na Mesa Proprietária (Prop)

Guia para operar os sistemas validados (Agulhada + Insidebar) dentro das
regras da mesa. Baseado no Monte Carlo dos trades reais (cesta ampla).

═══════════════════════════════════════════════════════════════
## REGRAS DA MESA (resumo)
═══════════════════════════════════════════════════════════════
  - Target (meta):        +15%
  - Daily Pause:          -3% no dia  -> para de operar naquele dia
  - Max Loss:             -7% sobre o saldo INICIAL (fixo) -> perde a conta
  - Minimum Positions:    5 operacoes
  - Trading Period:       ilimitado  (sua maior vantagem: sem pressa)
  - Payout Split:         70/30 (voce fica com 70%)
  Proibicoes:
  - Trade Duration min 30s   (irrelevante p/ swing/diario — voce nunca fecha em 30s)
  - Trade Range min 10 cents (irrelevante p/ acoes liquidas)
  - Consistency Rule 50%     (CRITICA — ver secao propria)
  Saque:
  - Periodo minimo: 14 dias
  - Consistency Rule 50% tambem vale p/ saque
  - Minimo 3 dias com >= +0,5% de lucro

═══════════════════════════════════════════════════════════════
## 1. RISCO POR TRADE  ->  0,30% do saldo inicial
═══════════════════════════════════════════════════════════════
O inimigo n.1 e o Max Loss de -7%. O risco por trade tem de ser pequeno o
bastante para sobreviver a sequencias de perda.

Monte Carlo (Agulhada pivo+TRIX + Insidebar 3R combinados, 8000 simulacoes):

  Risco/trade   Prob. estourar -7%   Prob. atingir +15%   DD pior 5%
  ---------------------------------------------------------------------
  0,50%              1,7%                  97%              -5,0%
  0,40%              0,5%                  97%              -4,1%
  0,30%  <==         0,0%                  92%              -3,0%   ESCOLHIDO
  0,25%              0,1%                  82%              -2,5%
  0,20%              0,0%                  64%              -2,0%

  -> 0,30% e o ponto otimo: ZERO estouro do Max Loss, drawdown pior-caso -3%
     (bem dentro dos 7%), e ainda 92% de chance de bater a meta.
  -> NAO use 0,50% na mesa (1,7% de chance de perder a conta e inaceitavel),
     mesmo sendo o que voce usaria na conta propria.

  Em conta de tamanho X: risco por trade = 0,30% de X.
  Ex.: conta 50k -> risco R$150/trade | conta 100k -> R$300/trade.
  Tamanho da posicao = (0,30% do saldo) / (distancia entrada-stop em R$).

═══════════════════════════════════════════════════════════════
## 2. LIMITES DIARIOS
═══════════════════════════════════════════════════════════════
  - Daily Pause -3%: com risco 0,30%/trade, -3% = ~10 stops seguidos no dia.
    Muito improvavel, mas se acontecer, PARE (a mesa obriga). Regra pessoal
    mais conservadora: se perder -2% no dia, pare voluntariamente — preserva
    margem ate o -3% da mesa e protege o psicologico.
  - Nunca "tentar recuperar" apos um dia ruim aumentando risco. Isso quebra
    contas de prop. Amanha e outro dia (periodo ilimitado).

═══════════════════════════════════════════════════════════════
## 3. CONSISTENCY RULE 50% (a regra que molda tudo)
═══════════════════════════════════════════════════════════════
Nenhum dia pode representar mais de 50% do lucro total. Se um dia sozinho
passar de 50% do lucro acumulado, a mesa NAO libera saque.

Implicacao pratica:
  - NAO busque um "dia herois". Ganhar muito num dia so ATRAPALHA (quebra a
    regra). O objetivo e lucro distribuido em varios dias.
  - Com meta 15%: distribua em MUITOS dias pequenos. Ex.: ~1% a 1,5%/dia por
    ~12-15 dias, em vez de 5% em 3 dias.
  - Teto pratico por dia: mire NO MAXIMO ~2% de lucro/dia. Se um dia estiver
    indo muito bem (ja +2%), considere reduzir/parar para nao concentrar.
  - Isso conversa com o seu sistema: expectancia positiva + muitos trades
    pequenos = lucro distribuido = exatamente o que a regra premia.

═══════════════════════════════════════════════════════════════
## 4. PLANO DE EXECUCAO (passo a passo)
═══════════════════════════════════════════════════════════════
  1. Opere os DOIS sistemas (Agulhada pivo+TRIX + Insidebar). Mais sinais =
     lucro mais distribuido = ajuda na Consistency Rule.
  2. Risco fixo de 0,30% por trade. Sempre. Sem exceção.
  3. Alvo por trade conforme cada sistema:
     - Insidebar: parcial 50% em 2R (breakeven) + resto ate 3R.
     - Agulhada: stop pivo + parcial 2R (breakeven) + saida no TRIX.
  4. Limite diario: pare em -2% (voluntario) ou -3% (mesa). Teto de +2%/dia.
  5. Minimo 5 posicoes e minimo 3 dias com +0,5% -> naturalmente atendidos
     operando o sistema por ~2-3 semanas.
  6. Saque so apos 14 dias e com lucro distribuido (Consistency ok).


═══════════════════════════════════════════════════════════════
## 6. CUSTOS POR TAMANHO DE CONTA (custo US$0,75/trade)
═══════════════════════════════════════════════════════════════
O custo e FIXO em dolar (US$0,75/trade) mas o risco e percentual (0,30%).
Por isso o custo pesa MUITO mais nas contas pequenas.

  Conta      Risco/trade   Custo consome   Prob.meta   Prob.estouro   Trades~
  --------------------------------------------------------------------------
  US$ 2.000    US$ 6          12,5%          86,5%         2,0%        ~210
  US$ 10.000   US$ 30          2,5%          98,8%         0,3%        ~158
  US$ 20.000   US$ 60          1,2%          99,3%         0,2%        ~152
  US$ 40.000   US$ 120         0,6%          99,5%         0,1%        ~149

Lucro liquido por trade (bruto - US$0,75):
  US$ 2.000  -> +US$ 1,20/trade  (custo come 38% do lucro bruto!)
  US$ 10.000 -> +US$ 8,99/trade  (custo come 8%)
  US$ 20.000 -> +US$ 18,74/trade (custo come 4%)
  US$ 40.000 -> +US$ 38,23/trade (custo come 2%)

CONCLUSAO:
  - Todas as contas sao VIAVEIS (lucro liquido positivo).
  - A de US$ 2.000 e a menos eficiente: custo devora 38% do lucro, prob. de
    meta cai p/ 86% e risco de estouro sobe p/ 2%. "Modo dificil".
  - A partir de US$ 10.000 o custo vira irrelevante (<=8% do lucro), prob. de
    meta ~99% e estouro ~0%. RECOMENDADO operar contas >= US$ 10.000.
  - Se comecar na de 2.000 (mais barata de contratar), saiba que a matematica
    melhora MUITO ao subir de tamanho.

  Observacao: US$0,75/trade e so a corretagem informada. Se houver spread ou
  outras taxas, o efeito nas contas pequenas e ainda maior. Confirme todos os
  custos com a mesa.


═══════════════════════════════════════════════════════════════
## 7. ESCOLHA DA CONTA — retorno vs taxa (Swing Flex)
═══════════════════════════════════════════════════════════════
A taxa do plano e REEMBOLSAVEL no 1o saque da fase financiada (volta 100% +
seu lucro). So e perdida se REPROVAR a avaliacao. Entao o que voce arrisca de
verdade e a taxa, e so perde se falhar.

  Conta       Taxa Flex  Meta 15%  Prob.passar  Seu 70%   1o saque(+taxa)  EV/taxa
  ----------------------------------------------------------------------------------
  US$ 2.000     US$ 87     US$ 300     93%       US$ 210     US$ 297         2,2x
  US$ 10.000    US$ 420    US$1.500   ~100%      US$1.050    US$1.470        2,5x
  US$ 20.000    US$ 670    US$3.000   ~100%      US$2.100    US$2.770        3,1x
  US$ 40.000    US$1.240   US$6.000   ~100%      US$4.200    US$5.440        3,4x

  (EV/taxa = valor esperado por unidade de taxa, ja considerando a chance de
   reprovar e perder a taxa. Maior = melhor negocio.)

CONCLUSAO:
  - Contas MAIORES sao mais eficientes (melhor EV/taxa + custo corretagem menor
    + maior prob. de passar). US$ 20k/40k lideram.
  - US$ 10.000 = melhor PONTO DE ENTRADA: ~100% prob., custo baixo, taxa
    acessivel (US$420), retorno 2,5x.
  - US$ 2.000 = "test drive" barato (US$87) p/ aprender a mesa; menos eficiente
    e maior risco relativo — nao como conta principal.
  - No 1o saque a taxa volta -> no sucesso (~99% nas contas >=10k) ela nao e
    custo. O risco real e so a taxa, perdida so se reprovar.

  IMPORTANTE: as probabilidades vem do backtest (sem custos de mercado alem da
  corretagem, e sobre cesta ampla). O real pode diferir. E "prob ~100%" nao e
  garantia — e a chance na simulacao, nao no futuro.

═══════════════════════════════════════════════════════════════
## 5. PROJECAO REALISTA
═══════════════════════════════════════════════════════════════
Com 0,30%/trade e a expectancia combinada (~+0,35R liquida antes de custos),
cada trade rende em media ~0,10% do saldo. Para +15% de meta: ~150 trades.
Operando os 2 sistemas, isso e alcancavel em ~3-6 semanas SEM pressa (periodo
ilimitado). A simulacao da 92% de chance de bater a meta antes de estourar.

RESSALVAS:
  - O backtest nao inclui custos; na mesa ha custos e possivelmente comissao.
    Desconte isso — a expectancia real e menor, entao pode levar mais tempo.
  - 92% de chance de passar = 8% de nao passar. Nao e garantido.
  - Disciplina no risco 0,30% e no teto diario e o que separa passar de perder
    a conta. A matematica so funciona se voce seguir SEM desvios.

═══════════════════════════════════════════════════════════════
## 8. CHECKLIST OPERACIONAL (consultar SEMPRE)
═══════════════════════════════════════════════════════════════

------------------------------------------------------------------
ANTES DE ABRIR O DIA
------------------------------------------------------------------
[ ] Já perdi 3% da conta no total? -> Se SIM, PARE de operar (perto do Max
    Loss de 7%; nao arrisque a conta).
[ ] O mercado US esta em regime bom? (VTI acima da SMA200 e subindo)
    -> Se o VTI estiver abaixo da SMA200 e caindo, NAO opere US no Insidebar.
[ ] Defini o valor de risco de hoje: 0,30% do saldo inicial da conta.
    (2k=US$6 | 10k=US$30 | 20k=US$60 | 40k=US$120 por trade)

------------------------------------------------------------------
ANTES DE CADA TRADE  (todos tem de ser SIM)
------------------------------------------------------------------
[ ] O sinal veio do scanner (Agulhada pivo+TRIX OU Insidebar)? 
[ ] Vou entrar no CRITERIO do sistema?
    - Agulhada: no fechamento do candle do sinal.
    - Insidebar: no fechamento que rompe a maxima do inside bar.
[ ] Calculei a posicao: tamanho = (0,30% do saldo) / (entrada - stop).
[ ] O STOP esta definido no pivo 3x3? (nunca entrar sem stop)
[ ] O risco desse trade e exatamente 0,30%? (nao mais, sob nenhuma emocao)
[ ] Ja fiz +2% no dia? -> Se SIM, considere PARAR (Consistency Rule: nao
    concentrar lucro num dia).
[ ] Perder este trade me leva a -2% no dia? -> Se SIM, este e o ULTIMO do dia.

------------------------------------------------------------------
DURANTE O TRADE (gestao)
------------------------------------------------------------------
[ ] Parcial: realizar 50% da posicao ao atingir 2R.
[ ] Ao realizar a parcial: MOVER o stop da metade restante para o BREAKEVEN
    (preco de entrada). A partir daqui o trade nao da mais prejuizo.
[ ] Saida final da metade restante:
    - Insidebar: no alvo de 3R.
    - Agulhada: quando o TRIX virar (EMA4 cruza EMA9 p/ baixo) - acompanhar
      no grafico.
[ ] NUNCA mover o stop para baixo/afastar. Stop so sobe, nunca desce.

------------------------------------------------------------------
LIMITES DO DIA (regras de sobrevivencia)
------------------------------------------------------------------
[ ] Perda no dia chegou a -2%? -> PARE (voluntario, protege ate o -3% da mesa).
[ ] Perda no dia chegou a -3%? -> PARE (obrigatorio - Daily Pause da mesa).
[ ] Lucro no dia passou de ~2%? -> Considere parar (Consistency Rule).
[ ] NUNCA aumentar risco para "recuperar" perda. Amanha e outro dia
    (periodo ilimitado - sem pressa).

------------------------------------------------------------------
NO FECHAMENTO DO DIA (registro)
------------------------------------------------------------------
[ ] Anotar: nº de trades, resultado do dia (%), maior ganho/perda.
[ ] Nenhum dia deve virar >50% do lucro total (Consistency Rule).
    Se um dia ficou muito grande, pise no freio nos proximos.
[ ] Ja tenho 3 dias com +0,5%? (requisito de saque)
[ ] Ja fiz 5 posicoes no total? (minimo da mesa)

------------------------------------------------------------------
PARA SACAR (fase financiada)
------------------------------------------------------------------
[ ] Passaram 14 dias (periodo minimo)?
[ ] Tenho pelo menos 3 dias com +0,5% de lucro?
[ ] Nenhum dia isolado passa de 50% do lucro total (Consistency Rule)?
[ ] -> No 1o saque a taxa do plano volta 100% + seu lucro (payout 70%).

------------------------------------------------------------------
OS 5 MANDAMENTOS (se esquecer tudo, lembre destes)
------------------------------------------------------------------
1. RISCO SEMPRE 0,30% por trade. Sem exceção, sem emoção.
2. SEMPRE com stop no pivo. Nunca entrar sem stop, nunca afastar o stop.
3. PARE em -2% no dia. Nunca tente recuperar aumentando risco.
4. LUCRO DISTRIBUIDO. Teto ~2%/dia. Nao busque dia herois (Consistency Rule).
5. SEM PRESSA. Periodo ilimitado. A expectancia positiva trabalha no tempo.
