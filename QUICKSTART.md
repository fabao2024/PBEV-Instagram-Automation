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
```

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

# Gerar imagens faltantes
python manage_queue.py --generate-images

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

## 13. Update seguro da VPS

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

## 14. Logs

```bash
journalctl -u pbev-instagram-bot -f
```
