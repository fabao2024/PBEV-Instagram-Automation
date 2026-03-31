"""Content generation using Google Gemini API for Instagram posts.

Generates captions, hashtags, and content calendar for Guia PBEV Brasil.
Uses the same Gemini model as the EletriBrasil chatbot (gemini-2.5-flash-lite).
"""

import json
import importlib
import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

from config import get_settings
from database import get_session, ContentIdea, ScheduledPost
from ev_knowledge import PBEV_SYSTEM_CONTEXT, CONTENT_CATEGORIES, OPTIMAL_POSTING_HOURS
from image_generator import _find_matching_vehicles, generate_and_host_post_image
import vehicle_catalog as vehicle_catalog_module

logger = logging.getLogger(__name__)

GROUNDED_VEHICLE_CATEGORIES = {"modelo_destaque", "comparativo", "tco_insight"}
AUTO_GENERATED_CATEGORIES = tuple(
    category["id"] for category in CONTENT_CATEGORIES if category["id"] != "noticia_mercado"
)

VEHICLE_CATALOG = vehicle_catalog_module.VEHICLE_CATALOG
format_price_brl = vehicle_catalog_module.format_price_brl
get_random_vehicle_for_category = vehicle_catalog_module.get_random_vehicle_for_category
get_vehicle = vehicle_catalog_module.get_vehicle

CONTENT_SYSTEM_PROMPT = """Você é um social media manager especializado em veículos elétricos no Brasil.
Crie conteúdo para o Instagram do Guia PBEV Brasil (@guiapbev).

Regras:
- Português brasileiro, tom informativo mas acessível
- Legendas entre 150-300 palavras (Instagram favorece legendas médias)
- Use emojis com moderação (⚡🔋🚗🇧🇷💰)
- Hashtags: 15-20 por post, mix de alto volume e nicho
- Primeira linha DEVE ser um hook forte (pergunta ou dado impactante)
- Quebre o texto em parágrafos curtos (2-3 linhas)

CTA com link rastreável:
- Cada post DEVE ter exatamente 1 CTA com o link UTM fornecido no campo "cta_url"
- Use frases como "🔗 Link na bio" ou "Acesse: {cta_url}" dependendo do contexto
- Para posts sobre TCO, direcione ao simulador. Para comparativos, ao comparador.

Responda SEMPRE em JSON válido, sem markdown e sem backticks.
"""


def get_client() -> genai.Client:
    """Retorna client Gemini configurado."""
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _gen_config(max_tokens: int = 4096) -> types.GenerateContentConfig:
    """Configuração padrão para geração de conteúdo."""
    return types.GenerateContentConfig(
        system_instruction=CONTENT_SYSTEM_PROMPT,
        temperature=0.9,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
    )


def _parse_response(text: str) -> dict:
    """Limpa e parseia resposta JSON do Gemini."""
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1]
    if clean.endswith("```"):
        clean = clean.rsplit("```", 1)[0]
    clean = clean.strip()
    return json.loads(clean)


def sync_vehicle_catalog(local_repo_path: str | None = None) -> bool:
    """Atualiza vehicle_catalog.py da fonte e recarrega o modulo em memoria.

    Falhas de rede/parsing nao devem derrubar a geracao de posts.
    """
    global vehicle_catalog_module, VEHICLE_CATALOG, format_price_brl
    global get_random_vehicle_for_category, get_vehicle

    try:
        import sync_catalog

        ts_content = sync_catalog.fetch_constants_ts(local_repo_path)
        vehicles = sync_catalog.parse_vehicles(ts_content)
        if not vehicles:
            raise RuntimeError("catalog sync returned no vehicles")

        catalog_py = sync_catalog.generate_catalog_py(vehicles)
        sync_catalog.OUTPUT_FILE.write_text(catalog_py, encoding="utf-8")

        importlib.invalidate_caches()
        vehicle_catalog_module = importlib.reload(vehicle_catalog_module)
        VEHICLE_CATALOG = vehicle_catalog_module.VEHICLE_CATALOG
        format_price_brl = vehicle_catalog_module.format_price_brl
        get_random_vehicle_for_category = vehicle_catalog_module.get_random_vehicle_for_category
        get_vehicle = vehicle_catalog_module.get_vehicle
        logger.info(f"Catalogo sincronizado: {len(VEHICLE_CATALOG)} veiculos.")
        return True
    except Exception as e:
        logger.warning(f"Falha ao sincronizar catalogo; usando snapshot local: {e}")
        return False


def _catalog_vehicle_lines(vehicle: dict) -> list[str]:
    return [
        f"- Marca: {vehicle['brand']}",
        f"- Modelo: {vehicle['model']}",
        f"- Categoria no catalogo: {vehicle['cat']}",
        f"- Preco no catalogo: {format_price_brl(vehicle['price'])}",
        f"- Autonomia no catalogo: {vehicle['range']} km",
        f"- Potencia no catalogo: {vehicle.get('power', '?')} cv",
        f"- Bateria no catalogo: {vehicle.get('battery', '?')} kWh",
    ]


def _pick_related_vehicle(base_vehicle: dict, excluded: set[str] | None = None) -> dict | None:
    excluded = excluded or set()
    same_category = [
        vehicle for vehicle in VEHICLE_CATALOG
        if vehicle["cat"] == base_vehicle["cat"]
        and f"{vehicle['brand']}::{vehicle['model']}" not in excluded
    ]
    if same_category:
        same_category.sort(key=lambda vehicle: abs(vehicle["price"] - base_vehicle["price"]))
        return same_category[0]

    for vehicle in VEHICLE_CATALOG:
        key = f"{vehicle['brand']}::{vehicle['model']}"
        if key not in excluded:
            return vehicle
    return None


def _resolve_source_vehicles(category: str, topic: str | None = None) -> list[dict]:
    matched = _find_matching_vehicles(topic or "", limit=2) if topic else []

    if category == "comparativo":
        if len(matched) >= 2:
            return matched[:2]

        if len(matched) == 1:
            first = matched[0]
            excluded = {f"{first['brand']}::{first['model']}"}
            second = _pick_related_vehicle(first, excluded=excluded)
            return [vehicle for vehicle in [first, second] if vehicle]

        first = get_random_vehicle_for_category(category)
        if not first:
            return []

        excluded = {f"{first['brand']}::{first['model']}"}
        second = _pick_related_vehicle(first, excluded=excluded)
        return [vehicle for vehicle in [first, second] if vehicle]

    if matched:
        return matched[:1]

    if topic:
        vehicle = get_vehicle(topic)
        if vehicle:
            return [vehicle]

    if category in GROUNDED_VEHICLE_CATEGORIES:
        vehicle = get_random_vehicle_for_category(category)
        if vehicle:
            return [vehicle]

    return []


def _build_source_context(category: str, source_vehicles: list[dict]) -> str:
    if not source_vehicles:
        return ""

    blocks = []
    for index, vehicle in enumerate(source_vehicles, start=1):
        blocks.append(
            "\n".join(
                [f"VEICULO {index} - fonte: catalogo do Guia PBEV / guiapbev.cloud"]
                + _catalog_vehicle_lines(vehicle)
            )
        )

    rules = [
        "REGRAS DE FATO:",
        "- Quando citar modelo, versao, preco, autonomia, potencia, bateria ou categoria, use somente os dados do bloco DADOS_FONTE.",
        "- Nao invente numeros, versoes, equipamentos ou comparacoes fora do que estiver em DADOS_FONTE.",
        "- Se faltar um dado para sustentar uma afirmacao, prefira nao afirmar.",
    ]

    if category == "comparativo":
        rules.append("- No comparativo, compare apenas os veiculos listados em DADOS_FONTE.")

    if category == "tco_insight":
        rules.append("- Em TCO, use DADOS_FONTE para qualquer atributo tecnico do carro e evite custos numericos nao fornecidos.")

    return "\n\nDADOS_FONTE:\n" + "\n\n".join(blocks) + "\n\n" + "\n".join(rules)


def _build_generation_prompt(
    category: str,
    category_desc: str,
    cta_url: str,
    topic: str | None = None,
    day: str | None = None,
    hour: int | None = None,
    analytics_context: str = "",
    source_vehicles: list[dict] | None = None,
) -> str:
    schedule_line = ""
    if day is not None and hour is not None:
        schedule_line = f"Dia/Horario: {day} as {hour}h\n"

    topic_line = f"Topico especifico: {topic}\n" if topic else ""
    source_context = _build_source_context(category, source_vehicles or [])
    factuality_rules = (
        "\nREGRAS GERAIS DE FATO:\n"
        "- Se nao houver DADOS_FONTE, evite citar modelo, versao, preco, autonomia, potencia ou bateria especificos.\n"
        "- Se houver DADOS_FONTE, use apenas os veiculos e numeros fornecidos ali."
    )

    return f"""Gere UM post de Instagram para o Guia PBEV Brasil.

Categoria: {category_desc}
CTA URL rastreavel: {cta_url}
{schedule_line}{topic_line}{analytics_context}{source_context}{factuality_rules}
Escolha um angulo relevante dentro da categoria e crie um post completo.

Responda em JSON:
{{
  "caption": "...",
  "hashtags": "#tag1 #tag2 ...",
  "image_prompt": "descricao curta da imagem ideal para o post",
  "hook": "primeira linha impactante"
}}
"""


def generate_weekly_content(target_date: datetime | None = None) -> list[dict]:
    """Gera conteúdo para uma semana inteira.

    Returns:
        Lista de dicts com caption, hashtags, category, scheduled_at, image_prompt.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.posting_timezone)
    start_date = target_date or datetime.now(tz)
    sync_vehicle_catalog()

    weekly_slots = _build_weekly_slots(start_date, tz)

    # Adiciona URL rastreável para cada slot
    from analytics import get_cta_url
    for i, slot in enumerate(weekly_slots):
        slot["cta_url"] = get_cta_url(category=slot["category"], post_id=i)

    # Tenta puxar insights do Plausible (não-bloqueante)
    analytics_context = ""
    try:
        import asyncio
        from analytics import get_content_insights
        insights = asyncio.run(get_content_insights())
        if insights.get("recommendation"):
            analytics_context = f"""

INSIGHTS DO ANALYTICS (últimos 30 dias):
{insights['recommendation']}
Use esses dados para priorizar temas e CTAs.
"""
    except Exception as e:
        logger.debug(f"Analytics indisponível, gerando sem insights: {e}")

    client = get_client()

    posts = []
    for i, slot in enumerate(weekly_slots):
        cat_info = next((c for c in CONTENT_CATEGORIES if c["id"] == slot["category"]), None)
        cat_desc = json.dumps(cat_info, ensure_ascii=False) if cat_info else slot["category"]

        source_vehicles = _resolve_source_vehicles(slot["category"])
        prompt = _build_generation_prompt(
            category=slot["category"],
            category_desc=cat_desc,
            cta_url=slot.get("cta_url", settings.public_site_base_url),
            day=slot["day"],
            hour=slot["hour"],
            analytics_context=analytics_context,
            source_vehicles=source_vehicles,
        )

        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=_gen_config(max_tokens=2048),
            )
            post = _parse_response(response.text)
            posts.append({
                "caption": post["caption"],
                "hashtags": post["hashtags"],
                "category": slot["category"],
                "scheduled_at": slot["datetime"],
                "image_prompt": post.get("image_prompt", ""),
                "source_vehicles": source_vehicles,
            })
            logger.info(f"  Post {i+1}/{len(weekly_slots)} gerado: {slot['day']} {slot['hour']}h")
        except Exception as e:
            logger.warning(f"  Falha no slot {i+1} ({slot['day']} {slot['hour']}h): {e}")

    logger.info(f"✅ Gerados {len(posts)} posts para a semana de {start_date.date()}")
    return posts


def generate_single_post(category: str, topic: str | None = None, sync_catalog_first: bool = True) -> dict:
    """Gera um único post sobre um tópico específico."""
    client = get_client()
    from analytics import get_cta_url
    if sync_catalog_first:
        sync_vehicle_catalog()

    cat_info = next((c for c in CONTENT_CATEGORIES if c["id"] == category), None)
    cat_desc = json.dumps(cat_info, ensure_ascii=False) if cat_info else category
    source_vehicles = _resolve_source_vehicles(category, topic)
    prompt = _build_generation_prompt(
        category=category,
        category_desc=cat_desc,
        cta_url=get_cta_url(category=category, post_id=random.randint(1000, 9999)),
        topic=topic,
        source_vehicles=source_vehicles,
    )

    response = client.models.generate_content(
        model=get_settings().gemini_model,
        contents=prompt,
        config=_gen_config(max_tokens=2048),
    )
    post = _parse_response(response.text)
    post["category"] = category
    post["source_vehicles"] = source_vehicles
    return post


def save_posts_to_queue(posts: list[dict]) -> int:
    """Salva posts gerados na fila de publicação."""
    session = get_session()
    count = 0
    for post in posts:
        scheduled_at = post["scheduled_at"]
        if isinstance(scheduled_at, str):
            scheduled_at = datetime.fromisoformat(scheduled_at)

        image_url = post.get("image_url")
        image_path = post.get("image_path")

        if not image_url:
            try:
                image_path, image_url = generate_and_host_post_image(
                    caption=post["caption"],
                    category=post.get("category", "geral"),
                    subtitle=post.get("image_prompt", ""),
                    source_vehicles=post.get("source_vehicles"),
                )
            except Exception as e:
                logger.warning(f"Falha ao gerar imagem para post [{post.get('category', 'geral')}]: {e}")

        scheduled = ScheduledPost(
            caption=post["caption"],
            hashtags=post.get("hashtags", ""),
            image_url=image_url,
            image_path=image_path,
            scheduled_at=scheduled_at,
            category=post.get("category", "geral"),
            post_type="image",
        )
        session.add(scheduled)
        count += 1
    session.commit()
    session.close()
    logger.info(f"✅ {count} posts salvos na fila.")
    return count


def _build_weekly_slots(start: datetime, tz: ZoneInfo) -> list[dict]:
    """Monta slots de publicação para a semana baseado em horários ótimos."""
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    categories_cycle = list(AUTO_GENERATED_CATEGORIES)

    slots = []
    cat_idx = 0

    for day_offset in range(7):
        current_date = start + timedelta(days=day_offset)
        day_name = day_names[current_date.weekday()]
        day_config = next((d for d in OPTIMAL_POSTING_HOURS if d["day"] == day_name), None)

        if not day_config:
            continue

        for hour in day_config["hours"]:
            dt = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slots.append({
                "datetime": dt.isoformat(),
                "day": day_name,
                "hour": hour,
                "category": categories_cycle[cat_idx % len(categories_cycle)],
            })
            cat_idx += 1

    return slots
