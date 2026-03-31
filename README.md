# Guia PBEV Brasil - Instagram Automation Bot

Bot de automacao para o Instagram do Guia PBEV Brasil.

Ele cobre:
- geracao de posts com Gemini
- fila e agendamento com SQLite + APScheduler
- publicacao automatica via Meta Graph API
- respostas automaticas via webhook
- geracao de imagens branded com dados do catalogo

## Como o projeto funciona

```text
1. O bot gera legenda + hashtags
2. Gera ou atualiza a imagem do post
3. Salva tudo na fila SQLite
4. O scheduler verifica a fila a cada 5 minutos
5. So publica posts que tenham imagem publica disponivel
```

## Estado atual do fluxo de conteudo

- `modelo_destaque`, `comparativo` e `tco_insight` usam dados do catalogo sincronizado do projeto `Guia-PBEV-Brasil`
- antes de gerar ou regenerar esses posts, o bot tenta sincronizar `src/constants.ts` e atualizar [vehicle_catalog.py](/c:/Users/fabio/OneDrive/Documentos/I.A%20jobs/testes/Guia%20PBEV/Guia-PBEV-Brasil/instagram/pbev-instagram-bot-configurado/vehicle_catalog.py)
- `comparativo` suporta fotos reais dos dois veiculos quando as imagens do catalogo estao disponiveis
- `noticia_mercado` continua disponivel para uso manual, mas foi removida da geracao semanal automatica

## Pre-requisitos

1. Conta Instagram Business conectada a uma Facebook Page
2. App Meta com permissoes:
- `instagram_basic`
- `instagram_content_publish`
- `instagram_manage_comments`
- `instagram_manage_messages`
- `pages_show_list`
3. Chave do Google Gemini
4. VPS Ubuntu com Python 3.11+
5. Dominio com HTTPS para webhook e imagens publicas

## Setup local ou VPS

```bash
cd /opt
git clone <repo-url> pbev-instagram-bot
cd pbev-instagram-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python -c "from database import init_db; init_db()"
python publish.py --test
```

## Variaveis importantes

- `HOST=0.0.0.0`
- `PORT=8001`
- `PUBLIC_SITE_URL=https://guiapbev.cloud`
- `IMAGE_BASE_URL=https://bot.seu-dominio.com`
- `WEBHOOK_URL=https://bot.seu-dominio.com/webhook`

Observacao:
- `PUBLIC_SITE_URL` deve apontar para o site rastreado no Plausible
- `IMAGE_BASE_URL` deve apontar para o host que serve `/ig-images/`
- `SITE_URL` ficou como legado para compatibilidade

## Operacao diaria

```bash
# Rodar API + scheduler
python main.py

# Testar conexao com a Meta
python publish.py --test

# Gerar 1 post manual e publicar
python publish.py --generate-and-post modelo_destaque --topic "BYD Dolphin Mini"

# Gerar conteudo da semana e salvar
python generate_content.py --days 7 --save
```

## Fila de posts

```bash
# Ver pendentes
python manage_queue.py --list

# Ver pendentes + publicados
python manage_queue.py --list --all

# Ver estatisticas
python manage_queue.py --stats

# Reagendar
python manage_queue.py --reschedule 5 "2026-04-01 10:00"

# Remover 1 post
python manage_queue.py --delete 5
```

Regra importante:
- o scheduler so publica posts com `image_url`
- post sem imagem fica pendente na fila

## Comandos de imagem

```bash
# Gerar imagens faltantes para pendentes
python manage_queue.py --generate-images

# Publicar um post da fila manualmente
python publish.py --post 5
```

## Regeneracao de posts aterrados

Categorias aterradas:
- `modelo_destaque`
- `comparativo`
- `tco_insight`

Comandos:

```bash
# Regenerar todas as categorias aterradas pendentes
python manage_queue.py --reset-grounded-posts

# Regenerar um post especifico
python manage_queue.py --reset-post 7

# Regenerar um comparativo preservando um tema explicito
python manage_queue.py --reset-post 7 --topic "GWM Ora 03 Skin BEV48 vs BYD Dolphin GS"
```

## Sync do catalogo

Manual:

```bash
python sync_catalog.py
```

Automatico:
- `generate_weekly_content()` tenta sincronizar o catalogo antes da geracao semanal
- `generate_single_post()` tenta sincronizar antes de gerar ou regenerar um post

Se a sync falhar:
- o bot continua usando o snapshot local atual de [vehicle_catalog.py](/c:/Users/fabio/OneDrive/Documentos/I.A%20jobs/testes/Guia%20PBEV/Guia-PBEV-Brasil/instagram/pbev-instagram-bot-configurado/vehicle_catalog.py)

## VPS e deploy

O projeto roda bem em VPS com:
- app Python na porta `8001`
- Nginx fazendo proxy para `127.0.0.1:8001`
- Nginx servindo `/ig-images/` a partir de `/var/www/pbev-images`
- `systemd` usando [pbev-instagram-bot.service](/c:/Users/fabio/OneDrive/Documentos/I.A%20jobs/testes/Guia%20PBEV/Guia-PBEV-Brasil/instagram/pbev-instagram-bot-configurado/pbev-instagram-bot.service)

O script [deploy.sh](/c:/Users/fabio/OneDrive/Documentos/I.A%20jobs/testes/Guia%20PBEV/Guia-PBEV-Brasil/instagram/pbev-instagram-bot-configurado/deploy.sh) hoje e um update seguro para VPS existente. Ele:
- atualiza dependencias
- garante diretorios e permissoes
- atualiza `systemd`
- valida o Nginx existente sem sobrescrever o vhost
- reinicia o bot e testa o health local

## Health e logs

```bash
# Health local
curl http://127.0.0.1:8001/health

# Health publico
curl https://bot.seu-dominio.com/health

# Logs do bot
journalctl -u pbev-instagram-bot -f
```

## Repo privado

Antes do primeiro push para GitHub, revise o guia:
- [PRIVATE_REPO.md](/c:/Users/fabio/OneDrive/Documentos/I.A%20jobs/testes/Guia%20PBEV/Guia-PBEV-Brasil/instagram/pbev-instagram-bot-configurado/PRIVATE_REPO.md)

Ele cobre:
- o que pode e o que nao pode ir para git
- como verificar se este diretorio esta dentro de um repo maior
- como criar um repo privado standalone com push via SSH

## Estrutura principal

```text
pbev-instagram-bot/
|-- main.py
|-- config.py
|-- database.py
|-- content_generator.py
|-- image_generator.py
|-- publisher.py
|-- publish.py
|-- manage_queue.py
|-- scheduler.py
|-- sync_catalog.py
|-- vehicle_catalog.py
|-- auto_responder.py
|-- analytics.py
|-- deploy.sh
|-- pbev-instagram-bot.service
|-- README.md
|-- QUICKSTART.md
```
