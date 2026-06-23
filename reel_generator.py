"""Reel generator using FFmpeg.

Converts existing feed images (1080x1080) into vertical videos (1080x1920)
with Ken Burns effect, text overlay, and fade transitions.

Output: MP4 H.264, 15-20 seconds, suitable for Instagram Reels.
"""

import logging
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Literal

from image_generator import BRAND_COLORS, CATEGORY_PALETTES, get_font, hex_to_rgb
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "generated_images"
REEL_DIR = Path(__file__).parent / "generated_reels"

# Reel dimensions (9:16 vertical)
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
REEL_DURATION = 15  # seconds

# Fonts available on system (checked by image_generator)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def ensure_dirs():
    REEL_DIR.mkdir(parents=True, exist_ok=True)


def _get_reel_font_path(bold: bool = True) -> str:
    """Returns the font path, preferring custom fonts if available."""
    assets_dir = Path(__file__).parent / "assets" / "fonts"
    for name in (["Montserrat-Bold.ttf"] if bold else ["Montserrat-Regular.ttf"]):
        path = assets_dir / name
        if path.exists():
            return str(path)
    return FONT_BOLD if bold else FONT_REGULAR


def create_reel_overlay(
    headline: str,
    subtitle: str = "",
    category: str = "geral",
    output_path: Path | None = None,
) -> Path:
    """Creates a PNG overlay (1080x1920) with text for the reel.

    This transparent PNG is composited on top of the video by FFmpeg.
    """
    ensure_dirs()
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = REEL_DIR / f"reel_overlay_{ts}.png"

    palette = CATEGORY_PALETTES.get(category, CATEGORY_PALETTES["geral"])
    accent = hex_to_rgb(palette["accent"])

    # Create transparent overlay
    overlay = Image.new("RGBA", (REEL_WIDTH, REEL_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # --- Top accent bar ---
    draw.rectangle([(0, 0), (REEL_WIDTH, 10)], fill=accent + (255,))

    # --- Logo ---
    logo_font = get_font(32, bold=True)
    draw.text((60, 40), "⚡ GUIA PBEV BRASIL", fill=accent + (255,), font=logo_font)

    # --- Category badge ---
    category_labels = {
        "modelo_destaque": "MODELO",
        "comparativo": "VS",
        "dica_ev": "DICA",
        "tco_insight": "TCO",
        "noticia_mercado": "NEWS",
        "geral": "EV",
        "reel": "EV",
    }
    label = category_labels.get(category, "EV")
    badge_font = get_font(20, bold=True)
    bbox = badge_font.getbbox(label)
    badge_w = (bbox[2] - bbox[0]) + 24
    badge_h = (bbox[3] - bbox[1]) + 14
    bx = REEL_WIDTH - 60 - badge_w
    by = 48
    draw.rounded_rectangle(
        [(bx, by), (bx + badge_w, by + badge_h)],
        radius=6,
        fill=accent + (255,),
    )
    draw.text(
        (bx + 12, by + 5),
        label,
        fill=hex_to_rgb(BRAND_COLORS["dark_bg"]) + (255,),
        font=badge_font,
    )

    # --- Headline (center area, large) ---
    # Wrap text to fit
    headline_font = get_font(64, bold=True)
    max_width = REEL_WIDTH - 120
    words = headline.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = headline_font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    # Draw headline (max 5 lines) in lower-center area
    text_color = (255, 255, 255, 255)
    line_height = 72
    total_h = len(lines[:5]) * line_height
    start_y = REEL_HEIGHT - 400 - (total_h // 2)

    for i, line in enumerate(lines[:5]):
        # Shadow for readability
        draw.text((62, start_y + i * line_height + 3), line, fill=(0, 0, 0, 160), font=headline_font)
        draw.text((60, start_y + i * line_height), line, fill=text_color, font=headline_font)

    # --- Subtitle ---
    if subtitle:
        sub_font = get_font(36, bold=False)
        sub_y = start_y + len(lines[:5]) * line_height + 20
        sub_max = REEL_WIDTH - 120
        sub_words = subtitle.split()
        sub_line = ""
        sub_lines = []
        for word in sub_words:
            test = f"{sub_line} {word}".strip()
            bbox = sub_font.getbbox(test)
            if bbox[2] - bbox[0] <= sub_max:
                sub_line = test
            else:
                if sub_line:
                    sub_lines.append(sub_line)
                sub_line = word
        if sub_line:
            sub_lines.append(sub_line)

        muted = (200, 200, 200, 230)
        for i, line in enumerate(sub_lines[:3]):
            draw.text((60, sub_y + i * 42), line, fill=muted, font=sub_font)

    # --- Footer ---
    footer_font = get_font(28, bold=True)
    footer_y = REEL_HEIGHT - 120
    draw.text((60, footer_y), "guiapbev.cloud", fill=accent + (255,), font=footer_font)
    draw.text(
        (60, footer_y + 38),
        "@guiapbevbrasil",
        fill=(180, 180, 180, 220),
        font=get_font(24, bold=False),
    )

    # "Link na bio" badge
    badge2_font = get_font(22, bold=True)
    bbox2 = badge2_font.getbbox("🔗 Link na bio")
    bw2 = bbox2[2] - bbox2[0] + 30
    draw.rounded_rectangle(
        [(60, footer_y - 65), (60 + bw2, footer_y - 25)],
        radius=20,
        fill=(255, 255, 255, 40),
    )
    draw.text((75, footer_y - 58), "🔗 Link na bio", fill=accent + (255,), font=badge2_font)

    overlay.save(output_path, "PNG")
    logger.info(f"🎬 Reel overlay criado: {output_path}")
    return output_path


def generate_reel_video(
    source_image: Path,
    overlay_png: Path,
    output_path: Path | None = None,
    duration: int = REEL_DURATION,
    zoom_mode: Literal["in", "out"] = "in",
) -> Path:
    """Generate a vertical reel video using FFmpeg.

    Args:
        source_image: Path to the 1080x1080 feed image.
        overlay_png: Path to the text overlay PNG (1080x1920).
        output_path: Output MP4 path. Auto-generated if None.
        duration: Video duration in seconds (default 15).
        zoom_mode: "in" (zoom from 1.0 to 1.15) or "out" (1.15 to 1.0).

    Returns:
        Path to the generated MP4.
    """
    ensure_dirs()
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = REEL_DIR / f"reel_{ts}.mp4"

    source_image = Path(source_image)
    overlay_png = Path(overlay_png)

    if not source_image.exists():
        raise FileNotFoundError(f"Imagem fonte não encontrada: {source_image}")
    if not overlay_png.exists():
        raise FileNotFoundError(f"Overlay não encontrado: {overlay_png}")

    # Calculate zoompan parameters
    total_frames = duration * 30  # 30 fps
    if zoom_mode == "in":
        zoom_expr = f"min(zoom+0.0005,1.15)"
    else:
        zoom_expr = f"if(eq(on,0),1.15,max(zoom-0.0005,1.0))"

    # FFmpeg filter chain:
    # 1. Scale image to fill 1080x1920 (with blur background)
    # 2. Apply zoompan (Ken Burns)
    # 3. Overlay text PNG
    # 4. Fade in/out
    filter_complex = (
        # Scale image to cover 1080x1920
        f"[0:v]scale={REEL_WIDTH}:{REEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={REEL_WIDTH}:{REEL_HEIGHT},"
        # Slight blur for background depth
        f"gblur=sigma=2[bg];"
        # Scale original image to fit center (maintain aspect)
        f"[0:v]scale={REEL_WIDTH}:{REEL_WIDTH}:force_original_aspect_ratio=decrease,"
        f"pad={REEL_WIDTH}:{REEL_WIDTH}:(ow-iw)/2:(oh-ih)/2:color=black@0[img];"
        # Zoompan on the centered image
        f"[img]format=yuv420p,"
        f"zoompan=z='{zoom_expr}':d={total_frames}:s={REEL_WIDTH}x{REEL_WIDTH}:fps=30[zoomed];"
        # Composite zoomed image on blurred background
        f"[bg][zoomed]overlay=(W-w)/2:(H-h)/2[base];"
        # Overlay text PNG
        f"[base][1:v]overlay=0:0[with_text];"
        # Fade in (0.5s) and fade out (last 0.5s)
        f"[with_text]fade=t=in:st=0:d=0.5,"
        f"fade=t=out:st={duration - 0.5}:d=0.5,"
        f"format=yuv420p[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(source_image),
        "-loop", "1", "-i", str(overlay_png),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-t", str(duration),
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info(f"🎬 Gerando reel: {output_path.name} ({duration}s)")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg falhou: {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg erro: {result.stderr[-300:]}")

    file_size = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"✅ Reel gerado: {output_path} ({file_size:.1f} MB)")
    return output_path


def generate_and_host_reel(
    source_image_path: Path,
    headline: str,
    subtitle: str = "",
    category: str = "geral",
    image_base_url: str = "",
    public_dir: Path | None = None,
    duration: int = REEL_DURATION,
) -> tuple[Path, str]:
    """Full pipeline: generate overlay, create video, copy to public dir, return URL.

    Args:
        source_image_path: Path to existing feed image (1080x1080).
        headline: Main text for the reel.
        subtitle: Secondary text.
        category: Content category (for colors).
        image_base_url: Base URL for public hosting (e.g., https://bot.guiapbev.cloud).
        public_dir: Where to copy the MP4 for nginx serving.
        duration: Video duration in seconds.

    Returns:
        Tuple of (local_path, public_url).
    """
    if public_dir is None:
        public_dir = Path("/var/www/pbev-images")
    public_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = source_image_path.stem.replace(" ", "_")
    overlay_path = REEL_DIR / f"overlay_{slug}_{ts}.png"
    video_path = REEL_DIR / f"reel_{slug}_{ts}.mp4"
    public_filename = f"reel_{slug}_{ts}.mp4"

    # Step 1: Create text overlay
    create_reel_overlay(
        headline=headline,
        subtitle=subtitle,
        category=category,
        output_path=overlay_path,
    )

    # Step 2: Generate video with FFmpeg
    generate_reel_video(
        source_image=source_image_path,
        overlay_png=overlay_path,
        output_path=video_path,
        duration=duration,
        zoom_mode="in",
    )

    # Step 3: Copy to public directory
    public_path = public_dir / public_filename
    shutil.copy2(video_path, public_path)

    # Step 4: Build URL
    base = image_base_url.rstrip("/")
    public_url = f"{base}/ig-images/{public_filename}"

    logger.info(f"🎬 Reel pronto e hospedado: {public_url}")
    return video_path, public_url


def extract_headline_from_caption(caption: str, max_length: int = 60) -> str:
    """Extract a short headline from a caption for the reel overlay.

    Takes the first line or first sentence, truncated to max_length.
    """
    if not caption:
        return "Guia PBEV Brasil"

    # First line
    first_line = caption.split("\n")[0].strip()

    # If first line is a question and too long, try first sentence
    if len(first_line) > max_length:
        sentences = first_line.split(". ")
        if sentences:
            first_line = sentences[0]

    if len(first_line) > max_length:
        first_line = first_line[:max_length - 3] + "..."

    return first_line


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python reel_generator.py <caminho_da_imagem.jpg> [headline]")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    headline = sys.argv[2] if len(sys.argv) > 2 else "Teste de Reel"

    print(f"Gerando reel de: {image_path}")
    print(f"Headline: {headline}")

    local_path, url = generate_and_host_reel(
        source_image_path=image_path,
        headline=headline,
        category="geral",
        image_base_url="https://bot.guiapbev.cloud",
    )

    print(f"\n✅ Reel gerado!")
    print(f"   Local: {local_path}")
    print(f"   URL:   {url}")
    print(f"   Tamanho: {local_path.stat().st_size / (1024*1024):.1f} MB")
