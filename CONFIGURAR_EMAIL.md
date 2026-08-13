# E-mail diário com os sinais do TradeDesk

Envia, de segunda a sexta às 14h de Brasília, um e-mail com os ativos
selecionados pelo scanner (ações US+B3), cada um com o gráfico do TradeDesk
(Didi + ADX + Bollinger) e link para o TradingView.

## Passo 1 — Criar uma "senha de app" do Google (só uma vez)

O envio usa o Gmail. Por segurança, o Google não deixa usar sua senha normal
em scripts — você cria uma "senha de app" específica:

1. A conta precisa ter **verificação em duas etapas** ativada.
   (myaccount.google.com → Segurança → Verificação em duas etapas)
2. Acesse: https://myaccount.google.com/apppasswords
3. Dê um nome (ex.: "TradeDesk") e clique em Criar.
4. O Google mostra uma senha de **16 letras** (ex.: `abcd efgh ijkl mnop`).
   Copie — é ela que vai no Secret (sem espaços: `abcdefghijklmnop`).

## Passo 2 — Guardar as credenciais nos Secrets do GitHub

Os Secrets ficam criptografados no GitHub, nunca aparecem no código nem nos logs.

No seu repositório TradeDesk:
1. Settings → Secrets and variables → Actions → New repository secret
2. Crie estes três:
   - `EMAIL_FROM`     = seu e-mail do Gmail (ex.: voce@gmail.com)
   - `EMAIL_APP_PASS` = a senha de app de 16 letras (sem espaços)
   - `EMAIL_TO`       = o e-mail que vai RECEBER (pode ser o mesmo)

## Passo 3 — Subir os arquivos

Copie para C:\TradeDesk (substituindo):
   - enviar_email.py
   - .github/workflows/email.yml

E envie:
   git add .
   git commit -m "E-mail diario com sinais do scanner"
   git pull --no-rebase
   git push

## Passo 4 — Testar sem esperar as 14h

No GitHub: aba Actions → workflow "email-diario" → Run workflow.
Em 2-3 minutos o e-mail deve chegar. Se não chegar, veja o log do passo
"Enviar e-mail" — ele diz o que houve (credencial errada, etc.).

## Observações

- Horário: o cron roda às 17h UTC = 14h de Brasília. No horário de verão (se
  voltar a existir), pode sair 1h diferente — me avise que ajusto.
- O e-mail é enviado mesmo sem sinais (avisa "nenhum hoje"), pra você saber
  que o sistema rodou.
- Cobre ações US+B3 (o diário). Para incluir Forex/Commodities/Setores depois,
  é só ampliar.
- O GitHub Actions às vezes atrasa o disparo do cron em alguns minutos (é
  normal da plataforma, não é erro).
