"""Image generator for Instagram posts.

Cria imagens branded usando templates Pillow com a identidade visual do Guia PBEV.
Suporta 3 formatos: feed (1080x1080), story (1080x1920), carousel (1080x1080).

Estratégia: templates com backgrounds de cor sólida + texto overlay.
Para imagens de veículos, usa fotos do catálogo ou URLs externas.
"""

import os
import re
import logging
import unicodedata
from pathlib import Path
from io import BytesIO
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# --- Brand Identity ---
BRAND_COLORS = {
    "primary": "#0D9F6E",       # Verde elétrico
    "primary_dark": "#057A55",
    "secondary": "#1E40AF",     # Azul profundo
    "accent": "#F59E0B",        # Amarelo energia
    "dark_bg": "#111827",       # Fundo escuro
    "light_bg": "#F9FAFB",
    "white": "#FFFFFF",
    "text_dark": "#1F2937",
    "text_light": "#F3F4F6",
    "text_muted": "#9CA3AF",
}

# Categorias → paletas de cor
CATEGORY_PALETTES = {
    "modelo_destaque": {"bg": "#111827", "accent": "#0D9F6E", "text": "#FFFFFF"},
    "comparativo":     {"bg": "#1E3A5F", "accent": "#F59E0B", "text": "#FFFFFF"},
    "dica_ev":         {"bg": "#0D9F6E", "accent": "#FFFFFF", "text": "#FFFFFF"},
    "tco_insight":     {"bg": "#111827", "accent": "#F59E0B", "text": "#FFFFFF"},
    "noticia_mercado": {"bg": "#1E40AF", "accent": "#0D9F6E", "text": "#FFFFFF"},
    "geral":           {"bg": "#111827", "accent": "#0D9F6E", "text": "#FFFFFF"},
}

ASSETS_DIR = Path(__file__).parent / "assets"
OUTPUT_DIR = Path(__file__).parent / "generated_images"

# Instagram dimensions
SIZES = {
    "feed": (1080, 1080),
    "story": (1080, 1920),
    "carousel": (1080, 1080),
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def ensure_dirs():
    ASSETS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (ASSETS_DIR / "fonts").mkdir(exist_ok=True)
    (ASSETS_DIR / "logos").mkdir(exist_ok=True)
    (ASSETS_DIR / "vehicles").mkdir(exist_ok=True)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Carrega fonte. Fallback para default se não houver custom."""
    font_dir = ASSETS_DIR / "fonts"

    # Tenta carregar fontes customizadas (coloque .ttf em assets/fonts/)
    candidates = [
        font_dir / ("Montserrat-Bold.ttf" if bold else "Montserrat-Regular.ttf"),
        font_dir / ("Inter-Bold.ttf" if bold else "Inter-Regular.ttf"),
    ]

    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)

    # Fallback: fonte default do sistema
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
                                  else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Quebra texto em linhas que cabem na largura máxima."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


class ImageGenerator:
    """Gerador de imagens para posts do Instagram."""

    def __init__(self):
        ensure_dirs()

    def create_post_image(
        self,
        headline: str,
        subtitle: str = "",
        category: str = "geral",
        post_format: Literal["feed", "story", "carousel"] = "feed",
        vehicle_image_path: str | None = None,
        output_filename: str | None = None,
    ) -> Path:
        """Cria imagem completa para um post.

        Args:
            headline: Texto principal (grande, impactante).
            subtitle: Texto secundário (menor).
            category: Categoria do post (define paleta de cores).
            post_format: Formato da imagem.
            vehicle_image_path: Caminho para foto do veículo (opcional).
            output_filename: Nome do arquivo de saída.

        Returns:
            Path do arquivo gerado.
        """
        width, height = SIZES[post_format]
        palette = CATEGORY_PALETTES.get(category, CATEGORY_PALETTES["geral"])

        # Criar canvas
        img = Image.new("RGB", (width, height), hex_to_rgb(palette["bg"]))
        draw = ImageDraw.Draw(img)

        # --- Layout zones ---
        padding = 80
        content_width = width - (padding * 2)

        if post_format == "story":
            # Story: mais espaço vertical
            logo_y = 100
            headline_y = 400
            subtitle_y = None  # calculado após headline
            footer_y = height - 200
        else:
            # Feed/Carousel: layout quadrado
            logo_y = 60
            headline_y = 280
            subtitle_y = None
            footer_y = height - 140

        # --- Accent bar (topo) ---
        accent_color = hex_to_rgb(palette["accent"])
        draw.rectangle([(0, 0), (width, 8)], fill=accent_color)

        # --- Decorative element (canto) ---
        self._draw_accent_corner(draw, width, height, accent_color)

        # --- Vehicle image (se fornecida) ---
        if vehicle_image_path and os.path.exists(vehicle_image_path):
            self._overlay_vehicle(img, vehicle_image_path, post_format)

        # --- Logo area ---
        logo_font = get_font(28, bold=True)
        draw.text(
            (padding, logo_y),
            "⚡ GUIA PBEV BRASIL",
            fill=accent_color,
            font=logo_font,
        )

        # Linha separadora sob o logo
        logo_bbox = logo_font.getbbox("⚡ GUIA PBEV BRASIL")
        line_y = logo_y + (logo_bbox[3] - logo_bbox[1]) + 16
        draw.line(
            [(padding, line_y), (padding + 200, line_y)],
            fill=accent_color,
            width=3,
        )

        # --- Headline ---
        headline_font = get_font(56 if post_format == "feed" else 52, bold=True)
        headline_lines = wrap_text(headline.upper(), headline_font, content_width)

        text_color = hex_to_rgb(palette["text"])
        y_cursor = headline_y

        for line in headline_lines[:4]:  # Max 4 linhas
            draw.text((padding, y_cursor), line, fill=text_color, font=headline_font)
            line_height = headline_font.getbbox(line)[3] - headline_font.getbbox(line)[1]
            y_cursor += line_height + 12

        # --- Subtitle ---
        if subtitle:
            subtitle_font = get_font(30, bold=False)
            sub_y = y_cursor + 30
            sub_lines = wrap_text(subtitle, subtitle_font, content_width)
            muted_color = hex_to_rgb(BRAND_COLORS["text_muted"])

            for line in sub_lines[:3]:
                draw.text((padding, sub_y), line, fill=muted_color, font=subtitle_font)
                sub_line_height = subtitle_font.getbbox(line)[3] - subtitle_font.getbbox(line)[1]
                sub_y += sub_line_height + 8

        # --- Footer ---
        footer_font = get_font(22, bold=False)
        draw.text(
            (padding, footer_y),
            "guiapbev.cloud",
            fill=accent_color,
            font=footer_font,
        )
        draw.text(
            (padding, footer_y + 32),
            "@guiapbev",
            fill=hex_to_rgb(BRAND_COLORS["text_muted"]),
            font=get_font(20, bold=False),
        )

        # --- Category badge ---
        self._draw_category_badge(draw, category, width, padding, accent_color)

        # --- Save ---
        if not output_filename:
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"pbev_{category}_{post_format}_{ts}.jpg"

        output_path = OUTPUT_DIR / output_filename
        img.save(output_path, "JPEG", quality=95)
        logger.info(f"🖼️ Imagem gerada: {output_path}")
        return output_path

    def create_comparison_image(
        self,
        model_a: str,
        model_b: str,
        specs_a: dict | None = None,
        specs_b: dict | None = None,
        vehicle_photo_path_a: Path | None = None,
        vehicle_photo_path_b: Path | None = None,
    ) -> Path:
        """Cria imagem comparativa lado a lado."""
        width, height = 1080, 1080
        img = Image.new("RGB", (width, height), hex_to_rgb(BRAND_COLORS["dark_bg"]))
        draw = ImageDraw.Draw(img)

        accent = hex_to_rgb(BRAND_COLORS["accent"])
        green = hex_to_rgb(BRAND_COLORS["primary"])
        white = hex_to_rgb(BRAND_COLORS["white"])
        muted = hex_to_rgb(BRAND_COLORS["text_muted"])

        # Top accent bar
        draw.rectangle([(0, 0), (width, 8)], fill=accent)

        # Header
        header_font = get_font(36, bold=True)
        draw.text((80, 60), "⚡ COMPARATIVO", fill=accent, font=header_font)

        # Divider line (center)
        draw.line([(540, 140), (540, 940)], fill=muted, width=1)
        draw.text((490, 110), "VS", fill=accent, font=get_font(28, bold=True))

        # Vehicle photos
        photo_top = 160
        photo_height = 240
        photo_width = 420
        self._draw_comparison_photo(
            img=img,
            photo_path=vehicle_photo_path_a,
            box=(80, photo_top, 80 + photo_width, photo_top + photo_height),
            placeholder_label=model_a,
        )
        self._draw_comparison_photo(
            img=img,
            photo_path=vehicle_photo_path_b,
            box=(580, photo_top, 580 + photo_width, photo_top + photo_height),
            placeholder_label=model_b,
        )

        # Model names
        model_font = get_font(32, bold=True)
        draw.text((80, 430), model_a.upper(), fill=green, font=model_font)
        draw.text((580, 430), model_b.upper(), fill=green, font=model_font)

        # Specs comparison
        if specs_a and specs_b:
            spec_font = get_font(24, bold=False)
            label_font = get_font(20, bold=False)
            y = 520

            for key in specs_a:
                if key in specs_b:
                    # Label
                    draw.text((80, y), key, fill=muted, font=label_font)
                    draw.text((580, y), key, fill=muted, font=label_font)
                    y += 28

                    # Values
                    draw.text((80, y), str(specs_a[key]), fill=white, font=spec_font)
                    draw.text((580, y), str(specs_b[key]), fill=white, font=spec_font)
                    y += 50

        # Footer
        footer_font = get_font(22, bold=False)
        draw.text((80, 980), "guiapbev.cloud/comparador", fill=green, font=footer_font)

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"pbev_comparativo_{ts}.jpg"
        img.save(output_path, "JPEG", quality=95)
        logger.info(f"🖼️ Comparativo gerado: {output_path}")
        return output_path

    def _draw_comparison_photo(
        self,
        img: Image.Image,
        photo_path: Path | None,
        box: tuple[int, int, int, int],
        placeholder_label: str,
    ):
        """Desenha foto do veículo no box do comparativo, com fallback textual."""
        draw = ImageDraw.Draw(img)
        left, top, right, bottom = box
        box_width = right - left
        box_height = bottom - top

        if photo_path and photo_path.exists():
            try:
                photo = Image.open(photo_path).convert("RGB")
                ratio = max(box_width / photo.width, box_height / photo.height)
                new_w = int(photo.width * ratio)
                new_h = int(photo.height * ratio)
                photo = photo.resize((new_w, new_h), Image.LANCZOS)

                crop_left = max((new_w - box_width) // 2, 0)
                crop_top = max((new_h - box_height) // 2, 0)
                photo = photo.crop((crop_left, crop_top, crop_left + box_width, crop_top + box_height))
                img.paste(photo, (left, top))
            except Exception as e:
                logger.warning(f"⚠️ Falha ao renderizar foto no comparativo: {e}")
                draw.rounded_rectangle(box, radius=18, fill=hex_to_rgb("#172033"))
        else:
            draw.rounded_rectangle(box, radius=18, fill=hex_to_rgb("#172033"))

        draw.rounded_rectangle(box, radius=18, outline=hex_to_rgb(BRAND_COLORS["primary"]), width=2)

        if not photo_path or not photo_path.exists():
            label_font = get_font(22, bold=True)
            muted = hex_to_rgb(BRAND_COLORS["text_muted"])
            lines = wrap_text(placeholder_label.upper(), label_font, box_width - 40)[:3]
            y = top + (box_height // 2) - (len(lines) * 18)
            for line in lines:
                draw.text((left + 20, y), line, fill=muted, font=label_font)
                y += 36

    def _draw_accent_corner(self, draw: ImageDraw.Draw, width: int, height: int,
                            accent_color: tuple):
        """Desenha elemento decorativo no canto superior direito."""
        # Triângulo sutil
        draw.polygon(
            [(width - 200, 0), (width, 0), (width, 200)],
            fill=(*accent_color, 30),  # Muito transparente
        )
        # Linhas diagonais
        for i in range(3):
            offset = i * 40
            draw.line(
                [(width - 120 + offset, 0), (width, 120 - offset)],
                fill=(*accent_color, 60),
                width=1,
            )

    def _draw_category_badge(self, draw: ImageDraw.Draw, category: str,
                             width: int, padding: int, accent_color: tuple):
        """Desenha badge da categoria no canto superior direito."""
        category_labels = {
            "modelo_destaque": "MODELO",
            "comparativo": "VS",
            "dica_ev": "DICA",
            "tco_insight": "TCO",
            "noticia_mercado": "NEWS",
            "geral": "EV",
        }
        label = category_labels.get(category, "EV")
        badge_font = get_font(18, bold=True)
        bbox = badge_font.getbbox(label)
        badge_w = (bbox[2] - bbox[0]) + 24
        badge_h = (bbox[3] - bbox[1]) + 12

        x = width - padding - badge_w
        y = 60

        draw.rounded_rectangle(
            [(x, y), (x + badge_w, y + badge_h)],
            radius=6,
            fill=accent_color,
        )
        draw.text(
            (x + 12, y + 4),
            label,
            fill=hex_to_rgb(BRAND_COLORS["dark_bg"]),
            font=badge_font,
        )

    def _overlay_vehicle(self, img: Image.Image, vehicle_path: str,
                         post_format: str):
        """Overlay de foto de veículo (com transparência se PNG)."""
        try:
            vehicle = Image.open(vehicle_path)
            width, height = img.size

            if post_format == "story":
                # Story: veículo no meio
                target_w = int(width * 0.85)
                ratio = target_w / vehicle.width
                target_h = int(vehicle.height * ratio)
                vehicle = vehicle.resize((target_w, target_h), Image.LANCZOS)
                x = (width - target_w) // 2
                y = int(height * 0.35)
            else:
                # Feed: veículo na parte inferior
                target_w = int(width * 0.75)
                ratio = target_w / vehicle.width
                target_h = int(vehicle.height * ratio)
                vehicle = vehicle.resize((target_w, target_h), Image.LANCZOS)
                x = (width - target_w) // 2
                y = height - target_h - 160

            if vehicle.mode == "RGBA":
                img.paste(vehicle, (x, y), vehicle)
            else:
                img.paste(vehicle, (x, y))

        except Exception as e:
            logger.warning(f"⚠️ Não foi possível carregar imagem do veículo: {e}")


# --- Vehicle photo from catalog ---

async def download_vehicle_photo(vehicle: dict, cache_dir: Path | None = None) -> Path | None:
    """Baixa a foto real do veículo do guiapbev.cloud ou GitHub.

    Converte automaticamente avif/webp para JPEG (Meta API só aceita JPEG/PNG).
    Usa cache local para evitar downloads repetidos.

    Args:
        vehicle: Dict do veículo (do vehicle_catalog.VEHICLE_CATALOG).
        cache_dir: Diretório para cache das imagens.

    Returns:
        Path do arquivo JPEG local, ou None se falhar.
    """
    import httpx
    from vehicle_catalog import get_image_url

    if cache_dir is None:
        cache_dir = ASSETS_DIR / "vehicles"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Nome normalizado para cache (sempre .jpg)
    slug = vehicle["img"].rsplit(".", 1)[0]
    slug = slug.replace(" ", "-").lower()
    cached_path = cache_dir / f"{slug}.jpg"

    # Se já tem cache, retorna direto
    if cached_path.exists() and cached_path.stat().st_size > 1000:
        logger.debug(f"📸 Cache hit: {cached_path}")
        return cached_path

    # Tenta baixar do site primeiro, fallback pro GitHub
    for source in ["site", "github"]:
        url = get_image_url(vehicle, source=source)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Converte para JPEG via Pillow (suporta avif, webp, png)
                    img = Image.open(BytesIO(resp.content))
                    img = img.convert("RGB")

                    # Redimensiona para 1080px de largura (mantém proporção)
                    if img.width > 1080:
                        ratio = 1080 / img.width
                        new_h = int(img.height * ratio)
                        img = img.resize((1080, new_h), Image.LANCZOS)

                    img.save(cached_path, "JPEG", quality=90)
                    logger.info(f"📸 Foto baixada ({source}): {vehicle['brand']} {vehicle['model']}")
                    return cached_path

        except Exception as e:
            logger.warning(f"⚠️ Falha ao baixar de {source}: {e}")
            continue

    logger.error(f"❌ Não foi possível baixar foto de {vehicle['brand']} {vehicle['model']}")
    return None


def download_vehicle_photo_sync(vehicle: dict, cache_dir: Path | None = None) -> Path | None:
    """Versão síncrona do download da foto do veículo."""
    import httpx
    from vehicle_catalog import get_image_url

    if cache_dir is None:
        cache_dir = ASSETS_DIR / "vehicles"
    cache_dir.mkdir(parents=True, exist_ok=True)

    slug = vehicle["img"].rsplit(".", 1)[0]
    slug = slug.replace(" ", "-").lower()
    cached_path = cache_dir / f"{slug}.jpg"

    if cached_path.exists() and cached_path.stat().st_size > 1000:
        logger.debug(f"📸 Cache hit: {cached_path}")
        return cached_path

    for source in ["site", "github"]:
        url = get_image_url(vehicle, source=source)
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    img = Image.open(BytesIO(resp.content))
                    img = img.convert("RGB")

                    if img.width > 1080:
                        ratio = 1080 / img.width
                        new_h = int(img.height * ratio)
                        img = img.resize((1080, new_h), Image.LANCZOS)

                    img.save(cached_path, "JPEG", quality=90)
                    logger.info(f"📸 Foto baixada ({source}): {vehicle['brand']} {vehicle['model']}")
                    return cached_path
        except Exception as e:
            logger.warning(f"⚠️ Falha ao baixar de {source}: {e}")
            continue

    logger.error(f"❌ Não foi possível baixar foto de {vehicle['brand']} {vehicle['model']}")
    return None


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^\w\s]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _vehicle_match_tokens(vehicle: dict) -> list[str]:
    """Gera aliases de busca para o veículo."""
    brand = _normalize_text(vehicle["brand"])
    model = _normalize_text(vehicle["model"])
    aliases = {
        f"{brand} {model}".strip(),
        model,
    }

    trim_suffixes = {
        "gl", "gs", "gt", "gts", "plus", "premium", "comfort", "luxury",
        "elite", "land", "awd", "icon", "xpower", "skin", "rs", "se",
        "sedan", "suv", "bev48", "bev58", "bev63", "bev", "dm", "dm i",
        "dm-i", "ev", "e", "xdrive30", "xdrive40", "edrive20", "edrive35",
    }
    model_words = model.split()

    while model_words and model_words[-1] in trim_suffixes:
        model_words.pop()
        if model_words:
            base_model = " ".join(model_words)
            aliases.add(base_model)
            aliases.add(f"{brand} {base_model}".strip())

    return [alias for alias in aliases if alias]


def _find_matching_vehicles(text: str, limit: int = 2) -> list[dict]:
    """Tenta identificar veículos mencionados no texto."""
    from vehicle_catalog import VEHICLE_CATALOG

    haystack = f" {_normalize_text(text)} "
    matches: list[tuple[int, dict]] = []

    for vehicle in VEHICLE_CATALOG:
        best_len = 0

        for token in _vehicle_match_tokens(vehicle):
            if token and f" {token} " in haystack:
                best_len = max(best_len, len(token))

        if best_len:
            matches.append((best_len, vehicle))

    matches.sort(key=lambda item: item[0], reverse=True)

    unique: list[dict] = []
    seen = set()
    for _, vehicle in matches:
        key = f"{vehicle['brand']}::{vehicle['model']}"
        if key not in seen:
            unique.append(vehicle)
            seen.add(key)
        if len(unique) >= limit:
            break

    return unique


def create_vehicle_post_image(
    vehicle: dict,
    vehicle_photo_path: Path | None = None,
    category: str = "modelo_destaque",
    post_format: str = "feed",
) -> Path:
    """Cria imagem completa para post usando foto REAL do catálogo + template branded.

    Combina:
    1. Template branded (fundo, cores, tipografia Guia PBEV)
    2. Foto real do veículo (do guiapbev.cloud)
    3. Specs overlay (preço, autonomia, potência)
    4. Badge de categoria + CTA

    Args:
        vehicle: Dict do veículo (do vehicle_catalog.VEHICLE_CATALOG).
        vehicle_photo_path: Foto já baixada (ou None para template sem foto).
        category: Categoria do post.
        post_format: "feed" (1080x1080) ou "story" (1080x1920).

    Returns:
        Path da imagem JPEG gerada.
    """
    from vehicle_catalog import format_price_brl

    gen = ImageGenerator()
    width, height = SIZES.get(post_format, (1080, 1080))
    palette = CATEGORY_PALETTES.get(category, CATEGORY_PALETTES["geral"])

    img = Image.new("RGB", (width, height), hex_to_rgb(palette["bg"]))
    draw = ImageDraw.Draw(img)
    padding = 80
    content_width = width - (padding * 2)
    accent = hex_to_rgb(palette["accent"])
    text_color = hex_to_rgb(palette["text"])
    muted = hex_to_rgb(BRAND_COLORS["text_muted"])

    # --- Foto do veículo (parte superior/central) ---
    if vehicle_photo_path and vehicle_photo_path.exists():
        photo = Image.open(vehicle_photo_path).convert("RGB")

        # Crop para preencher a parte superior (16:9 → square crop)
        target_h = int(height * 0.5)  # Metade superior
        ratio = max(width / photo.width, target_h / photo.height)
        new_w = int(photo.width * ratio)
        new_h = int(photo.height * ratio)
        photo = photo.resize((new_w, new_h), Image.LANCZOS)

        # Centraliza e cropa
        left = (new_w - width) // 2
        top = (new_h - target_h) // 2
        photo = photo.crop((left, top, left + width, top + target_h))

        # Aplica overlay gradiente escuro na base (pra texto ficar legível)
        overlay = Image.new("RGBA", (width, target_h), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for y in range(target_h):
            alpha = int(180 * (y / target_h) ** 1.5)  # Gradiente de cima (claro) pra baixo (escuro)
            overlay_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

        photo_rgba = photo.convert("RGBA")
        photo_rgba = Image.alpha_composite(photo_rgba, overlay)
        img.paste(photo_rgba.convert("RGB"), (0, 0))

        text_start_y = target_h + 30
    else:
        text_start_y = 200

    # --- Accent bar topo ---
    draw.rectangle([(0, 0), (width, 6)], fill=accent)

    # --- Logo PBEV ---
    logo_font = get_font(24, bold=True)
    draw.text((padding, 20), "⚡ GUIA PBEV BRASIL", fill=accent, font=logo_font)

    # --- Badge categoria ---
    gen._draw_category_badge(draw, category, width, padding, accent)

    # --- Nome do modelo (grande) ---
    model_name = f"{vehicle['brand']} {vehicle['model']}".upper()
    title_font = get_font(48, bold=True)
    draw.text((padding, text_start_y), model_name, fill=text_color, font=title_font)

    # --- Preço ---
    price_y = text_start_y + 60
    price_font = get_font(36, bold=True)
    price_text = format_price_brl(vehicle["price"])
    draw.text((padding, price_y), price_text, fill=accent, font=price_font)

    # --- Specs grid (2 colunas) ---
    specs_y = price_y + 60
    spec_font = get_font(24, bold=False)
    spec_label_font = get_font(18, bold=False)

    specs = [
        ("Autonomia", f"{vehicle['range']} km"),
        ("Potência", f"{vehicle.get('power', '?')} cv"),
        ("Bateria", f"{vehicle.get('battery', '?')} kWh"),
        ("Categoria", vehicle["cat"]),
    ]

    col_width = content_width // 2
    for i, (label, value) in enumerate(specs):
        col = i % 2
        row = i // 2
        x = padding + (col * col_width)
        y = specs_y + (row * 60)

        draw.text((x, y), label, fill=muted, font=spec_label_font)
        draw.text((x, y + 22), value, fill=text_color, font=spec_font)

    # --- Footer ---
    footer_y = height - 100
    footer_font = get_font(22, bold=False)
    draw.text((padding, footer_y), "guiapbev.cloud", fill=accent, font=footer_font)
    draw.text((padding, footer_y + 30), "@guiapbev", fill=muted, font=get_font(18, bold=False))

    # --- Linha separadora acima do footer ---
    draw.line([(padding, footer_y - 16), (width - padding, footer_y - 16)], fill=(*accent, 80), width=1)

    # --- Save ---
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = f"{vehicle['brand']}-{vehicle['model']}".lower().replace(" ", "-")
    output_path = OUTPUT_DIR / f"pbev_{slug}_{ts}.jpg"
    img.save(output_path, "JPEG", quality=95)
    logger.info(f"🖼️ Post image gerada: {output_path}")
    return output_path


# --- Image hosting helper ---

async def upload_image_to_hosting(image_path: Path) -> str:
    """Faz upload da imagem para um serviço de hosting e retorna URL pública.

    A Meta Graph API precisa de uma URL pública para a imagem.
    Opções de hosting:
    1. Imgur API (gratuito, sem auth para uploads anônimos)
    2. Cloudinary (free tier generoso)
    3. Seu próprio VPS servindo estáticos via Nginx

    Este exemplo usa o próprio VPS como host estático.
    """
    import shutil

    # Copia para diretório servido pelo Nginx
    static_dir = Path("/var/www/pbev-images")
    static_dir.mkdir(parents=True, exist_ok=True)

    dest = static_dir / image_path.name
    shutil.copy2(image_path, dest)

    # Retorna URL pública (configure no Nginx)
    from config import get_settings
    settings = get_settings()
    base_url = settings.image_host_base_url

    # Assumindo que Nginx serve /var/www/pbev-images em /ig-images/
    return f"{base_url}/ig-images/{image_path.name}"


def upload_image_to_hosting_sync(image_path: Path) -> str:
    """Versão síncrona do upload para uso em jobs e scripts locais."""
    import shutil

    static_dir = Path("/var/www/pbev-images")
    static_dir.mkdir(parents=True, exist_ok=True)

    dest = static_dir / image_path.name
    shutil.copy2(image_path, dest)

    from config import get_settings
    settings = get_settings()
    base_url = settings.image_host_base_url

    return f"{base_url}/ig-images/{image_path.name}"


def generate_and_host_post_image(
    caption: str,
    category: str = "geral",
    subtitle: str = "",
    source_vehicles: list[dict] | None = None,
) -> tuple[str, str]:
    """Gera uma imagem contextual e retorna path local + URL pública."""
    headline = caption.splitlines()[0].strip() if caption else ""
    headline = re.sub(r"[^\w\s\-\?\!\.,:]+", "", headline, flags=re.UNICODE)
    headline = re.sub(r"\s+", " ", headline).strip()

    if not headline:
        headline = category.replace("_", " ").upper()

    text_context = " ".join(part for part in [caption, subtitle] if part)
    vehicles = list(source_vehicles or [])
    if not vehicles:
        vehicles = _find_matching_vehicles(text_context, limit=2)
    img_gen = ImageGenerator()

    if category == "comparativo" and len(vehicles) >= 2:
        from vehicle_catalog import format_price_brl

        specs_a = {
            "Preço": format_price_brl(vehicles[0]["price"]),
            "Autonomia": f"{vehicles[0]['range']} km",
            "Potência": f"{vehicles[0].get('power', '?')} cv",
        }
        specs_b = {
            "Preço": format_price_brl(vehicles[1]["price"]),
            "Autonomia": f"{vehicles[1]['range']} km",
            "Potência": f"{vehicles[1].get('power', '?')} cv",
        }
        vehicle_photo_path_a = download_vehicle_photo_sync(vehicles[0])
        vehicle_photo_path_b = download_vehicle_photo_sync(vehicles[1])
        image_path = img_gen.create_comparison_image(
            model_a=f"{vehicles[0]['brand']} {vehicles[0]['model']}",
            model_b=f"{vehicles[1]['brand']} {vehicles[1]['model']}",
            specs_a=specs_a,
            specs_b=specs_b,
            vehicle_photo_path_a=vehicle_photo_path_a,
            vehicle_photo_path_b=vehicle_photo_path_b,
        )
    elif vehicles:
        vehicle = vehicles[0]
        vehicle_photo_path = download_vehicle_photo_sync(vehicle)
        image_path = create_vehicle_post_image(
            vehicle=vehicle,
            vehicle_photo_path=vehicle_photo_path,
            category=category,
            post_format="feed",
        )
    else:
        image_path = img_gen.create_post_image(
            headline=headline[:60],
            subtitle=subtitle[:120],
            category=category,
        )

    image_url = upload_image_to_hosting_sync(image_path)
    return str(image_path), image_url
