# Corrigir o deploy do Pages (timeout na publicação)

## O que estava acontecendo

O scan rodava com sucesso e gerava os JSON novos (com `quality`), mas a
**publicação no GitHub Pages travava** com "Timeout reached, aborting!".

Causa: havia DOIS sistemas de deploy do Pages competindo:
1. O deploy "clássico" (Settings > Pages > Deploy from a branch /docs), que
   dispara sozinho a cada commit em docs/.
2. O commit do robô a cada scan, que disparava esse deploy clássico.

Essa competição travava a fila de deployment.

## A correção

O novo `scan.yml` publica o Pages ele mesmo (jobs `scan` -> `deploy`, usando as
ações oficiais do GitHub). Passa a existir UM só caminho de deploy.

Para isso funcionar, é preciso trocar o modo do Pages no GitHub.

---

## Passo 1 — Subir o scan.yml novo

Copie o `scan.yml` para `C:\TradeDesk\.github\workflows\scan.yml` (substituindo)
e envie:

```
cd C:\TradeDesk
git add .
git commit -m "Deploy do Pages via Actions (corrige timeout)"
git pull --no-rebase
git push
```

(Se o `git pull` abrir o editor Vim pedindo mensagem de merge: aperte Esc,
digite `:wq` e Enter.)

## Passo 2 — Trocar o modo do Pages para GitHub Actions

1. No repositório: **Settings** -> **Pages**.
2. Em **Build and deployment** -> **Source**: troque de
   "Deploy from a branch" para **GitHub Actions**.
3. Não precisa configurar mais nada — o próprio workflow cuida do deploy.

> Isso desliga o deploy clássico que estava travando. A partir de agora, quem
> publica o site é o job `deploy` dentro do `scan`.

## Passo 3 — Rodar o scanner

- Botão "Rodar scanner agora" no site, ou
- Aba **Actions** -> **scan** -> **Run workflow**.

Agora o workflow vai: rodar o scanner, gerar os JSON, comitar, empacotar `docs/`
e publicar no Pages — tudo numa execução só. Ao terminar (verde), o site mostra
os dados novos, com os cards ordenados por qualidade.

## Conferir

Abra e procure por `quality`:
`https://cassiocarvalho750-create.github.io/TradeDesk/painel_us.json`

Se aparecer (ex.: `"quality": 87.4`), deu certo e os cards no site estarão
ordenados do melhor para o pior sinal.

---

## Observação

Como agora o deploy faz parte do workflow `scan`, você deixará de ver o
"pages build and deployment" separado na aba Actions — o deploy aparece como o
segundo job dentro de cada execução do `scan`. Isso é o esperado.
