# Teste de ROBUSTEZ do Insidebar (checar overfitting)

Ao longo dos ajustes, otimizamos varios parametros na MESMA cesta de 38 techs.
Isso melhorou os numeros nesses dados (+65R -> +162R), mas parte pode ser
"overfitting" — o sistema decorou aquela cesta em vez de achar regras
universais. O jeito de descobrir e testar em ativos DIFERENTES.

## Passo 1 — Baixar uma cesta diferente

No cmd, em C:\TradeDesk:

    python baixar_dados.py

Isso baixa uma cesta ampla e variada (bancos, energia, consumo, saude,
industria, utilities + algumas B3) para a pasta prices_teste/. E o oposto das
techs vencedoras — de proposito.

(Para escolher seus proprios tickers:
    python baixar_dados.py prices_teste JPM KO XOM ITUB4.SA ... )

## Passo 2 — Rodar o backtest nesta cesta nova

    python backtest_insidebar.py prices_teste

## Passo 3 — Comparar

Compare a expectancia e o win rate desta cesta nova com os da cesta de techs:
  - techs (atual): win ~48%, exp ~+0.46R
  - cesta nova: ???

INTERPRETACAO:
- Se os numeros da cesta nova forem PARECIDOS (win ~45-50%, exp positiva):
  otimo — o setup e ROBUSTO, funciona alem das techs. Confie mais nele.
- Se DESABAREM (win < 40%, exp perto de zero ou negativa): parte do resultado
  era overfitting. O setup depende do tipo de ativo. Nesse caso, considere
  voltar alguns parametros para valores mais conservadores.

O resultado REAL do seu trading tende a ficar entre as duas cestas.

## Dica

Quanto mais ativos e mais variados na cesta de teste, mais confiavel a
conclusao. A cesta padrao do baixar_dados.py ja e bem diversa; pode ampliar.
