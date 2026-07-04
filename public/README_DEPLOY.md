# TradeDesk · Agulhada do Didi — Deploy (site + scanner na nuvem)

Arquitetura **sem servidor**: o site (GitHub Pages) lê arquivos JSON; o scanner (Python)
roda no **GitHub Actions**, gera os JSON e os publica de volta no repositório. Um botão no
site dispara o scan sob demanda via API do GitHub.

```
Navegador (GitHub Pages: docs/TradeDesk.html)
      │  clique "Rodar scanner agora"  →  API do GitHub (workflow_dispatch)
      ▼
GitHub Actions  →  roda scanner_us.py / scanner_b3.py  →  gera painel_*.json
      │  commit em docs/
      ▼
Site recarrega os JSON e redesenha os indicadores (DIDI, ADX, BB)
```

---

## Estrutura do repositório

```
seu-repo/
├── .github/workflows/scan.yml     ← workflow (botão + agendamento)
├── requirements.txt
├── scanner.py  scanner_us.py  scanner_b3.py
├── bt_engine.py  run_backtest_v2.py  us_universe.py
└── docs/                           ← publicado pelo GitHub Pages
    ├── TradeDesk.html              ← o site
    ├── painel_us.json  painel_b3.json   (gerados pelo Actions)
    └── ...
```

Os `.py` ficam na **raiz** (o Actions roda a partir dela). O site e os JSON ficam em `docs/`.

---

## Passo a passo (uma vez só)

### 1. Criar o repositório
1. Crie um repositório no GitHub (pode ser **público**; para privado com Pages é preciso conta Pro).
2. Suba todos os arquivos mantendo a estrutura acima. A branch principal deve se chamar `main`
   (se for `master`, troque `ref:"main"` no `TradeDesk.html` e `main` onde aparecer).

### 2. Ativar o GitHub Pages
1. Repositório → **Settings** → **Pages**.
2. Em *Build and deployment* → *Source*: **Deploy from a branch**.
3. Branch: **main**, pasta: **/docs**. Salve.
4. Após ~1 min, o site fica em `https://SEU_USUARIO.github.io/SEU_REPO/TradeDesk.html`.

### 3. Permitir que o Actions comite os resultados
1. **Settings** → **Actions** → **General**.
2. Em *Workflow permissions*: marque **Read and write permissions**. Salve.
   (O workflow já pede `contents: write`, mas essa opção precisa estar habilitada na conta/repo.)

### 4. Gerar o token para o botão (fine-grained, permissão mínima)
1. GitHub → foto do perfil → **Settings** → **Developer settings** →
   **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Repository access**: *Only select repositories* → escolha **este repositório**.
3. **Permissions** → *Repository permissions* → **Actions**: **Read and write**.
   (Só isso. Nada mais é necessário.)
4. Gere e **copie** o token (`github_pat_...`). Ele só aparece uma vez.

### 5. Configurar o site
1. Abra o site publicado e clique na engrenagem **⚙**.
2. Informe `usuario/repositorio` e cole o token.
3. Salve. **O token fica apenas no seu navegador** (localStorage) — nunca vai para o repositório.

Pronto. Clique em **Rodar scanner agora**.

---

## Uso no dia a dia

- **Rodar scanner agora** — dispara o scan na nuvem. Leva alguns minutos (o universo US é grande).
  O site acompanha o progresso e recarrega o painel ao terminar.
- **Recarregar** — só relê o último resultado já publicado, sem rodar nada.
- **Mercado** (Ambos / EUA / B3) — filtra o que carregar e o que o scan varre.
- **Agendamento automático** — além do botão, o workflow roda sozinho às **18:30 (BRT)** em
  dias úteis, após o fechamento. Ajuste o `cron` em `scan.yml` se quiser outro horário
  (o cron usa **UTC**: 18:30 BRT = 21:30 UTC).

---

## Segurança do token — leia

- O token dá poder de **disparar Actions** neste repositório. Com permissão *Actions: read and write*
  e escopo restrito a um único repositório, o dano possível é mínimo (rodar/ver workflows), mas trate-o como senha.
- Como o site é público, **o token nunca pode ser escrito no código**. Por isso ele é digitado na
  engrenagem e salvo só no seu navegador. Qualquer pessoa com acesso físico ao seu navegador o veria —
  em máquina compartilhada, use a aba Actions do GitHub para disparar manualmente em vez do botão.
- Para revogar: Developer settings → Fine-grained tokens → **Revoke**. Gere outro quando quiser.

---

## Sem botão (alternativa mais simples)

Se preferir não lidar com token: ignore os passos 4–5. O scan roda sozinho pelo **agendamento**
(passo do `cron`) e você também pode dispará-lo manualmente em **Actions → scan → Run workflow**.
O site então só usa o botão **Recarregar**. Nesse modo o `TradeDesk.html` funciona sem nenhum token.

---

## Ajustes comuns

- **Horário do scan**: edite a linha `cron:` em `.github/workflows/scan.yml`.
- **Piso de liquidez** (US): `US_MIN_VOL_FIN_MI` em `run_backtest_v2.py`.
- **Largura da faixa de compressão do Didi** no gráfico: constante `band=0.15` em `TradeDesk.html`.
- **Rate limit do Yahoo** no Actions: se muitos tickers falharem, reduza o lote — os scripts
  aceitam `--chunk 50` (adicione ao comando no `scan.yml`).
