# Diagnóstico de um ticker — "por que fulano não apareceu?"

Ferramenta para auditar a decisão do scanner sobre um ativo específico.
Roda a MESMA lógica do scanner e mostra, critério por critério, com os
números exatos, por que o ativo passou ou não no setup da Agulhada.

## Como rodar (no computador, na pasta C:\TradeDesk)

```
python diagnostico.py A
python diagnostico.py PETR4.SA
python diagnostico.py AAPL --timeframe 2h
python diagnostico.py VALE3.SA --timeframe 1wk
```

- Para ações dos EUA: só o ticker (ex.: `A`, `AAPL`, `NVDA`).
- Para ações da B3: acrescente `.SA` (ex.: `PETR4.SA`, `VALE3.SA`).
- `--timeframe` aceita: 1d (padrão), 1wk, 4h, 2h, 1h, 15m, 5m.

## O que ele mostra

Para o último candle do ativo, checa os 4 pilares do setup:

1. **Gatilho Bollinger** — a banda está abrindo (primeira expansão) hoje?
2. **Candle verde** — fechou acima da abertura?
3. **DIDI** — houve cruzamento MA3>MA8 hoje ou nos últimos N candles (janela do timeframe)?
4. **ADX** — o evento de força ocorreu na janela? Decompõe as 3 sub-condições:
   - (a) ADX inclinando para cima (hoje > ontem)
   - (b) DI+ > DI-
   - (c) ADX >= 105% do DI-

No fim, dá o **veredito**: se passou (apareceria no scanner) ou, se não,
**exatamente em quais critérios foi reprovado**.

## Exemplo de uso

Quando um ativo te parecer candidato no TradingView mas não aparecer no
painel, rode o diagnóstico dele. Em vez de interpretar o gráfico no olho,
você vê o número exato que o scanner calculou e onde o ativo travou.

Nota: o ADX exige as TRÊS sub-condições juntas (a+b+c). Um ADX que só
"subiu" (condição a) mas com DI+ < DI- (condição b falha) NÃO dispara o
evento — o diagnóstico deixa isso explícito.
