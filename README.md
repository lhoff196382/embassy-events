# 🌍 Embassy Cultural Events — Brasília

Monitora automaticamente eventos culturais em embaixadas e consulados em Brasília e envia um e-mail a cada 5 dias com a agenda, indicando se o evento é gratuito ou pago.

## Como configurar (5 minutos)

### 1. Criar repositório no GitHub

```bash
cd embassy-events
git init
git add .
git commit -m "feat: embassy events scraper"
gh repo create embassy-events --public --push --source=.
```

### 2. Configurar Secrets no GitHub

Vá em **Settings → Secrets and variables → Actions → New repository secret** e adicione:

| Secret               | Valor                                                   |
|----------------------|---------------------------------------------------------|
| `GMAIL_USER`         | seu e-mail Gmail (ex: `seuemail@gmail.com`)             |
| `GMAIL_APP_PASSWORD` | senha de app Gmail (veja abaixo como gerar)             |
| `EMAIL_TO`           | e-mail destino (pode ser o mesmo Gmail ou outro)        |
| `SERPAPI_KEY`        | *opcional* — chave SerpAPI para resultados mais ricos   |

### 3. Gerar senha de app Gmail

1. Acesse [myaccount.google.com/security](https://myaccount.google.com/security)
2. Habilite **Verificação em duas etapas** (se não tiver)
3. Em **Senhas de app**, crie uma nova senha para "Email"
4. Cole os 16 caracteres gerados no secret `GMAIL_APP_PASSWORD`

### 4. Testar agora

No GitHub, vá em **Actions → Embassy Cultural Events → Run workflow**.

---

## Agendamento

O workflow roda automaticamente nos dias **1, 6, 11, 16, 21 e 26** de cada mês às 08:00 BRT.

## Fontes monitoradas

- Instituto Francês do Brasil
- Goethe-Institut Brasília
- Instituto Cervantes
- British Council Brasil
- Instituto Italiano de Cultura
- Instituto Camões
- Embaixada do Japão
- Embaixada dos EUA

## Melhorar resultados (opcional)

Crie uma conta gratuita em [serpapi.com](https://serpapi.com) (100 buscas/mês grátis) e adicione a chave como `SERPAPI_KEY`. Isso dá acesso a resultados do Google, muito mais ricos que o DuckDuckGo.
