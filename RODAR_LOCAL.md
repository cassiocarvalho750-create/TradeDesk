# Rodar o TradeDesk localmente (no seu PC)

Além de rodar na nuvem (GitHub Actions), você pode rodar o scanner no seu
próprio computador e ver o resultado na página bonita — sem depender de token,
sem esperar a nuvem. Só precisa de internet para baixar os dados do Yahoo.

## Jeito fácil (recomendado): o atalho

Dê dois cliques no arquivo **TradeDesk_LOCAL.bat** (na pasta C:\TradeDesk).
Ele faz tudo sozinho:
  1. roda o scanner de ações US + B3;
  2. abre a página no navegador já com os resultados.

Uma janela preta (o "servidor") vai ficar aberta enquanto você usa a página.
NÃO feche essa janela enquanto estiver olhando os sinais — ela é o que serve
a página. Quando terminar, é só fechá-la.

## Jeito manual (se quiser controlar cada passo)

Abra o cmd na pasta C:\TradeDesk e rode:

    python scanner_us.py          (ações EUA)
    python scanner_b3.py          (ações B3)
    python scanner_etf.py         (setores)
    python scanner_forex.py       (forex + commodities)

Isso gera os arquivos painel_*.json na pasta. Depois suba o servidor:

    python -m http.server 8000

E abra no navegador (deixe o cmd aberto):

    http://localhost:8000/docs/TradeDesk.html
    http://localhost:8000/docs/TradeDeskSetores.html
    http://localhost:8000/docs/TradeDeskForex.html   (etc.)

Para outros timeframes, use a flag --timeframe:

    python scanner_us.py --timeframe 2h
    python scanner_us.py --timeframe 1wk


## IMPORTANTE: as paginas ficam em docs\

O scanner gera os JSON na pasta raiz (C:\TradeDesk), mas as paginas HTML
ficam na subpasta docs\. Entao, ao rodar manualmente, copie os JSON para docs\
antes de abrir a pagina:

    copy /Y painel_us.json docs\
    copy /Y painel_b3.json docs\

E abra sempre com /docs/ no endereco:

    http://localhost:8000/docs/TradeDesk.html

(O atalho TradeDesk_LOCAL.bat ja faz essa copia automaticamente — por isso
o jeito facil e recomendado.)

## Por que precisa do "servidor"?

Se você abrir o HTML dando dois cliques (arquivo solto), o navegador bloqueia
a leitura dos JSONs por segurança. O comando "python -m http.server" cria um
mini-site local que resolve isso — a página passa a funcionar como um site
normal. É seguro: roda só na sua máquina, ninguém de fora acessa.

## Local x Nuvem — quando usar cada um

- LOCAL: resultado na hora, sem token, bom para uma consulta rápida agora.
  Só funciona com seu PC ligado e você rodando o .bat.
- NUVEM: roda sozinho no horário agendado, publica no site, acessível do
  celular e de qualquer lugar, manda o e-mail diário. Não depende do seu PC.

Os dois usam exatamente o mesmo scanner e a mesma lógica — a diferença é só
ONDE roda e como você acessa. Pode usar os dois conforme a conveniência.
