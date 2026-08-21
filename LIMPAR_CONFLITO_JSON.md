# Acabar de vez com o conflito dos JSON (passo unico)

Voce vinha tendo conflito no Git porque tanto a nuvem quanto o seu PC geravam
os mesmos arquivos JSON de painel. Agora isso esta resolvido:

- O TradeDesk_LOCAL.bat passa a usar uma pasta separada (_local) para ver a
  pagina no seu PC. Essa pasta e ignorada pelo Git.
- O .gitignore ignora os JSON gerados localmente na raiz.
- A pasta docs/ (que o site publica) continua sendo atualizada SO pela nuvem.

## Passo unico (rode UMA vez, no cmd em C:\TradeDesk)

Primeiro, faca o Git "esquecer" os JSON locais da raiz que ele ainda rastreia
(isso NAO apaga os arquivos, so para de versiona-los):

    git rm --cached painel_us.json painel_b3.json 2>nul
    git rm --cached scanner_us_tradedesk_USA.json scanner_b3_tradedesk_BRL.json 2>nul
    git rm --cached scanner_us.html scanner_b3.html 2>nul
    git rm --cached ultimo_scan.txt 2>nul

Depois adicione o .gitignore e o .bat novos e suba:

    git add .gitignore TradeDesk_LOCAL.bat
    git commit -m "Ignora arquivos locais do scanner (fim dos conflitos de JSON)"
    git pull --no-rebase
    git push

Pronto. A partir de agora, rodar o scanner local nao gera mais conflito:
os arquivos locais sao ignorados, e a nuvem cuida do que e publicado.

## Como usar o modo local a partir de agora

Dois cliques no TradeDesk_LOCAL.bat, como antes. A unica diferenca invisivel
e que ele monta a pagina numa pasta _local (ignorada pelo Git) em vez de mexer
em docs/. Voce nao percebe diferenca no uso — so nao ha mais conflito.
