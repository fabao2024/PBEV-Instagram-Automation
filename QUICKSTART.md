# Quick Start - VPS Ubuntu

Guia curto para subir, validar e operar o bot em uma VPS Ubuntu.

## 1. Enviar o projeto

```bash
scp pbev-instagram-bot.tar.gz usuario@seu-vps:/tmp/

sudo mkdir -p /opt/pbev-instagram-bot
cd /opt
sudo tar xzf /tmp/pbev-instagram-bot.tar.gz --strip-components=1 -C pbev-instagram-bot
sudo chown -R $USER:$USER /opt/pbev-instagram-bot
cd /opt/pbev-instagram-bot
```

## 2. Rodar o check

```bash
sudo bash setup_check.sh
```

## 3. Criar o `.env`

```bash
cp .env.example .env
nano .env
```

Preencha no minimo:
- `GEMINI_API_KEY`
- `META_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`
- `FACEBOOK_PAGE_ID`
- `FACEBOOK_PAGE_ACCESS_TOKEN`
- `PUBLIC_SITE_URL`
- `IMAGE_BASE_URL`
- `WEBHOOK_URL`

Valores esperados em producao:

```env
HOST=0.0.0.0
PORT=8001
PUBLIC_SITE_URL=https://guiapbev.cloud
IMAGE_BASE_URL=https://bot.seu-dominio.com
WEBHOOK_URL=https://bot.seu-dominio.com/webhook
ENABLE_AI_IMAGE_GENERATION=true
IMAGE_GENERATION_PROVIDER=gemini
IMAGE_GENERATION_MODEL=gemini-3.1-flash-image-preview
IMAGE_GENERATION_SIZE=1280x1280
```

Notas:
- `META_ACCESS_TOKEN` e usado para publicar posts
- `FACEBOOK_PAGE_ACCESS_TOKEN` e usado para responder DMs
- o token da pagina deve ser obtido via `GET /me/accounts?fields=id,name,access_token`
- se esse token expirar em poucas horas, voce provavelmente salvou um token temporario e nao o page token final
- depois de renovar ou trocar `META_ACCESS_TOKEN`, rode `python refresh_token.py --sync-page-token`
- para testar Z.AI como gerador de fundo, preencha `ZAI_API_KEY` e troque `IMAGE_GENERATION_PROVIDER=zai`
- um baseline bom para Z.AI e `IMAGE_GENERATION_MODEL=glm-image`

## 4. Setup Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 5. Inicializar banco e testar Meta

```bash
python -c "from database import init_db; init_db()"
python publish.py --test
```

Se `--test` passar, o token e a conta IG estao OK.

Para DMs, confira tambem:
- `FACEBOOK_PAGE_ID`
- `FACEBOOK_PAGE_ACCESS_TOKEN`
- permissao `instagram_manage_messages`

## 6. Configurar Nginx e HTTPS

Use o vhost do bot apontando para `127.0.0.1:8001`.

Passos gerais:

```bash
sudo cp nginx/pbev-instagram-bot.conf /etc/nginx/sites-available/pbev-instagram-bot
sudo ln -s /etc/nginx/sites-available/pbev-instagram-bot /etc/nginx/sites-enabled/pbev-instagram-bot
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d bot.seu-dominio.com
```

Observacao:
- nao coloque `limit_req_zone` dentro do arquivo do site
- essa diretiva so pode existir no contexto `http` do `nginx.conf`

## 7. Iniciar o bot

```bash
python main.py
```

Ou com `systemd`:

```bash
sudo cp pbev-instagram-bot.service /etc/systemd/system/pbev-instagram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now pbev-instagram-bot
```

## 8. Validar health

```bash
curl http://127.0.0.1:8001/health
curl https://bot.seu-dominio.com/health
systemctl status pbev-instagram-bot --no-pager
```

## 9. Gerar e revisar a fila

```bash
python generate_content.py --days 7 --save
python manage_queue.py --stats
python manage_queue.py --list
python manage_queue.py --list --all
```

Lembrete:
- o scheduler so publica posts com imagem
- se um post estiver sem `image_url`, ele fica parado na fila
- se um post ja estiver vencido e voce gerar a imagem depois, ele pode publicar no proximo ciclo

## 10. Comandos do dia a dia

```bash
# Teste de pipeline completo
python publish.py --generate-and-post modelo_destaque --topic "BYD Dolphin Mini"

# Publicar um post da fila
python publish.py --post 5

# Ver fila
python manage_queue.py --list

# Ver pendentes + publicados
python manage_queue.py --list --all

# Estatisticas
python manage_queue.py --stats

# Preview HTML de um post
python manage_queue.py --preview 5

# Gerar imagens faltantes
python manage_queue.py --generate-images

# Reaplicar correcoes atuais aos pendentes e reagendar
python manage_queue.py --refresh-pending --start-at "2026-04-02 09:00" --interval-hours 24

# Reagendar
python manage_queue.py --reschedule 5 "2026-04-01 10:00"

# Remover um post
python manage_queue.py --delete 5
```

## 11. Posts aterrados no catalogo

Categorias com dados do catalogo:
- `modelo_destaque`
- `comparativo`
- `tco_insight`

Comandos:

```bash
# Regenerar todos os pendentes dessas categorias
python manage_queue.py --reset-grounded-posts

# Regenerar um post
python manage_queue.py --reset-post 7

# Regenerar um comparativo com tema explicito
python manage_queue.py --reset-post 7 --topic "GWM Ora 03 Skin BEV48 vs BYD Dolphin GS"
```

## 12. Sync do catalogo

Manual:

```bash
python sync_catalog.py
```

Automatico:
- o bot tenta sincronizar o catalogo antes de gerar a semana
- tambem tenta sincronizar antes de gerar ou regenerar um post

Se a sync falhar:
- ele continua usando o snapshot local atual

## 13. Imagens e CTA

- quando o post menciona um veiculo reconhecido, o bot tenta usar a foto real do catalogo
- imagens `.avif` do catalogo sao convertidas via `pillow-avif-plugin`
- se nao houver foto de veiculo, o bot so tenta gerar um fundo com IA em `dica_ev`, `tco_insight` e `noticia_mercado`
- quando houver foto real do carro no catalogo, ela tem prioridade e a IA nao entra no fluxo
- para feed, prefira CTA tipo `link na bio`; URL em legenda nao e um fluxo confiavel de clique no Instagram

## 14. Update seguro da VPS

O [deploy.sh](/c:/Users/fabio/OneDrive/Documentos/I.A%20jobs/testes/Guia%20PBEV/Guia-PBEV-Brasil/instagram/pbev-instagram-bot-configurado/deploy.sh) atual nao e mais bootstrap de maquina nova.
Hoje ele e um script de update seguro para VPS existente.

Uso:

```bash
cd /opt/pbev-instagram-bot
chmod +x deploy.sh
sudo ./deploy.sh
```

Ele:
- atualiza dependencias
- garante diretorios e permissoes
- atualiza `systemd`
- valida o Nginx sem sobrescrever o vhost existente
- reinicia o bot e testa o health local

## 15. Logs

```bash
journalctl -u pbev-instagram-bot -f
```

## 16. Tokens Meta

```bash
# Verificar status dos dois tokens
python refresh_token.py --check

# Renovar META_ACCESS_TOKEN
python refresh_token.py

# Sincronizar FACEBOOK_PAGE_ACCESS_TOKEN a partir do token Meta atual
python refresh_token.py --sync-page-token

# Reiniciar depois de qualquer alteracao
sudo systemctl restart pbev-instagram-bot
```

Leitura rapida:
- `Status do token Meta: Valido: Sim` indica que publicacao deve funcionar
- `Status do token da pagina: Valido: Sim` indica que DMs devem funcionar
- `Alinhado ao META_ACCESS_TOKEN atual: Nao` nao e erro imediato, mas vale sincronizar
## 17. Casos comuns

- erro `(#190) This method must be called with a Page Access Token`:
  o valor em `FACEBOOK_PAGE_ACCESS_TOKEN` nao e token de pagina valido
- erro `code 190 / subcode 463` em DMs:
  o token salvo expirou; normalmente isso indica que o valor em `FACEBOOK_PAGE_ACCESS_TOKEN` nao e o page token final obtido de `/me/accounts`
- erro `attempt to write a readonly database`:
  o bot publicou, mas nao conseguiu marcar o item como publicado; isso pode causar duplicacao
- DM respondendo e depois erro `(#230) Requires pages_messaging permission`:
  o webhook esta recebendo a propria mensagem do bot; mantenha o `main.py` atualizado para ignorar o proprio remetente
- preview do post:
  use `python manage_queue.py --preview ID` e abra a URL retornada no navegador
