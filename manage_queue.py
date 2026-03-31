"""CLI para gerenciar a fila de publicação.

Uso:
    python manage_queue.py --list                    # Listar pendentes
    python manage_queue.py --list --all              # Listar todos (incluindo publicados)
    python manage_queue.py --delete 5                # Remover post #5
    python manage_queue.py --reschedule 5 "2026-04-01 10:00"  # Reagendar
    python manage_queue.py --add-image 5 /path/to/image.jpg   # Adicionar imagem
    python manage_queue.py --generate-images         # Gerar imagens faltantes
    python manage_queue.py --reset-post 7            # Regenerar um post específico
    python manage_queue.py --reset-post 7 --topic "GWM Ora 03 Skin BEV48 vs BYD Dolphin GS"
    python manage_queue.py --reset-grounded-posts    # Regenerar posts aterrados na fonte
    python manage_queue.py --stats                   # Estatísticas
"""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from database import get_session, ScheduledPost, init_db
from config import get_settings
from image_generator import _find_matching_vehicles, generate_and_host_post_image

GROUNDED_CATEGORIES = ("modelo_destaque", "comparativo", "tco_insight")


def _derive_topic_from_post(post: ScheduledPost) -> str | None:
    matches = _find_matching_vehicles(post.caption or "", limit=2)
    if post.category == "comparativo" and len(matches) >= 2:
        return f"{matches[0]['brand']} {matches[0]['model']} vs {matches[1]['brand']} {matches[1]['model']}"
    if matches:
        vehicle = matches[0]
        return f"{vehicle['brand']} {vehicle['model']}"

    first_line = (post.caption or "").splitlines()[0].strip()
    return first_line or None


def _regenerate_existing_post(post: ScheduledPost, sync_catalog_first: bool, topic_override: str | None = None):
    from content_generator import generate_single_post, sync_vehicle_catalog

    topic = topic_override or _derive_topic_from_post(post)

    if sync_catalog_first:
        sync_vehicle_catalog()

    new_post = generate_single_post(
        post.category,
        topic=topic,
        sync_catalog_first=False,
    )
    image_path, image_url = generate_and_host_post_image(
        caption=new_post["caption"],
        category=post.category or "geral",
        subtitle=new_post.get("image_prompt", ""),
        source_vehicles=new_post.get("source_vehicles"),
    )

    post.caption = new_post["caption"]
    post.hashtags = new_post.get("hashtags", "")
    post.image_path = image_path
    post.image_url = image_url


def list_posts(show_all: bool = False):
    session = get_session()
    query = session.query(ScheduledPost).order_by(ScheduledPost.scheduled_at)

    if not show_all:
        query = query.filter(ScheduledPost.published == False)

    posts = query.all()

    if not posts:
        print("📭 Nenhum post na fila.")
        return

    print(f"\n{'ID':>4}  {'Status':>6}  {'Categoria':<18}  {'Agendado para':<20}  {'Imagem':>6}  Legenda")
    print("-" * 100)

    for p in posts:
        status = "✅" if p.published else "⏳"
        has_img = "✅" if p.image_url else "❌"
        caption_preview = p.caption[:40].replace("\n", " ") + "..." if len(p.caption) > 40 else p.caption.replace("\n", " ")
        scheduled = p.scheduled_at.strftime("%Y-%m-%d %H:%M") if p.scheduled_at else "N/A"
        print(f"{p.id:>4}  {status:>6}  {p.category:<18}  {scheduled:<20}  {has_img:>6}  {caption_preview}")

    print(f"\nTotal: {len(posts)} posts")
    session.close()


def delete_post(post_id: int):
    session = get_session()
    post = session.query(ScheduledPost).filter_by(id=post_id).first()

    if not post:
        print(f"❌ Post #{post_id} não encontrado.")
        return

    if post.published:
        print(f"⚠️ Post #{post_id} já foi publicado. Tem certeza? (s/n)")
        if input().strip().lower() != "s":
            print("Cancelado.")
            return

    session.delete(post)
    session.commit()
    print(f"🗑️ Post #{post_id} removido.")
    session.close()


def reschedule_post(post_id: int, new_datetime: str):
    session = get_session()
    post = session.query(ScheduledPost).filter_by(id=post_id).first()

    if not post:
        print(f"❌ Post #{post_id} não encontrado.")
        return

    settings = get_settings()
    tz = ZoneInfo(settings.posting_timezone)

    try:
        new_dt = datetime.strptime(new_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError:
        print("❌ Formato inválido. Use: YYYY-MM-DD HH:MM")
        return

    old_dt = post.scheduled_at
    post.scheduled_at = new_dt
    session.commit()
    print(f"📅 Post #{post_id} reagendado: {old_dt} → {new_dt}")
    session.close()


def add_image_to_post(post_id: int, image_url: str):
    session = get_session()
    post = session.query(ScheduledPost).filter_by(id=post_id).first()

    if not post:
        print(f"❌ Post #{post_id} não encontrado.")
        return

    post.image_url = image_url
    session.commit()
    print(f"🖼️ Imagem adicionada ao post #{post_id}: {image_url}")
    session.close()


def generate_missing_images():
    session = get_session()
    posts = (
        session.query(ScheduledPost)
        .filter(
            ScheduledPost.published == False,
            ScheduledPost.image_url == None,
        )
        .order_by(ScheduledPost.scheduled_at)
        .all()
    )

    if not posts:
        print("✅ Nenhum post pendente sem imagem.")
        session.close()
        return

    generated = 0
    for post in posts:
        try:
            image_path, image_url = generate_and_host_post_image(
                caption=post.caption,
                category=post.category or "geral",
            )
            post.image_path = image_path
            post.image_url = image_url
            generated += 1
            print(f"🖼️ Post #{post.id} atualizado com imagem: {image_url}")
        except Exception as e:
            print(f"❌ Falha ao gerar imagem para post #{post.id}: {e}")

    session.commit()
    session.close()
    print(f"\n✅ {generated} posts atualizados com imagem.")


def reset_grounded_posts():
    from content_generator import sync_vehicle_catalog

    session = get_session()
    posts = (
        session.query(ScheduledPost)
        .filter(
            ScheduledPost.published == False,
            ScheduledPost.category.in_(GROUNDED_CATEGORIES),
        )
        .order_by(ScheduledPost.scheduled_at)
        .all()
    )

    if not posts:
        print("✅ Nenhum post pendente das categorias aterradas.")
        session.close()
        return

    sync_vehicle_catalog()
    print(f"♻️ Regenerando {len(posts)} posts das categorias aterradas...")
    reset_count = 0

    for post in posts:
        try:
            _regenerate_existing_post(post, sync_catalog_first=False)
            reset_count += 1
            print(f"🔄 Post #{post.id} regenerado [{post.category}]")
        except Exception as e:
            print(f"❌ Falha ao regenerar post #{post.id}: {e}")

    session.commit()
    session.close()
    print(f"\n✅ {reset_count} posts regenerados com nova legenda e imagem.")


def reset_post(post_id: int, topic_override: str | None = None):
    session = get_session()
    post = session.query(ScheduledPost).filter_by(id=post_id).first()

    if not post:
        print(f"❌ Post #{post_id} não encontrado.")
        session.close()
        return

    if post.published:
        print(f"⚠️ Post #{post_id} já foi publicado; não será regenerado.")
        session.close()
        return

    try:
        _regenerate_existing_post(post, sync_catalog_first=True, topic_override=topic_override)
        session.commit()
        print(f"✅ Post #{post.id} regenerado [{post.category}]")
    except Exception as e:
        print(f"❌ Falha ao regenerar post #{post.id}: {e}")
    finally:
        session.close()


def show_stats():
    session = get_session()

    total = session.query(ScheduledPost).count()
    published = session.query(ScheduledPost).filter_by(published=True).count()
    pending = session.query(ScheduledPost).filter_by(published=False).count()
    with_image = session.query(ScheduledPost).filter(
        ScheduledPost.published == False,
        ScheduledPost.image_url != None,
    ).count()
    without_image = pending - with_image

    print(f"""
📊 Estatísticas da fila
{'─' * 30}
Total de posts:       {total}
Publicados:           {published} ✅
Pendentes:            {pending} ⏳
  Com imagem:         {with_image} 🖼️
  Sem imagem:         {without_image} ❌
{'─' * 30}
""")

    # Próximos 5 posts
    next_posts = (
        session.query(ScheduledPost)
        .filter_by(published=False)
        .order_by(ScheduledPost.scheduled_at)
        .limit(5)
        .all()
    )

    if next_posts:
        print("📅 Próximos posts:")
        for p in next_posts:
            ready = "✅" if p.image_url else "⚠️ sem imagem"
            print(f"   #{p.id} [{p.category}] {p.scheduled_at.strftime('%d/%m %H:%M')} — {ready}")

    session.close()


def main():
    parser = argparse.ArgumentParser(description="Gerenciar fila de publicação PBEV")
    parser.add_argument("--list", action="store_true", help="Listar posts")
    parser.add_argument("--all", action="store_true", help="Incluir publicados (com --list)")
    parser.add_argument("--delete", type=int, metavar="ID", help="Remover post por ID")
    parser.add_argument("--reschedule", nargs=2, metavar=("ID", "DATETIME"),
                        help="Reagendar post: ID 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--add-image", nargs=2, metavar=("ID", "URL"),
                        help="Adicionar URL de imagem a um post")
    parser.add_argument("--generate-images", action="store_true",
                        help="Gerar imagens para posts pendentes sem imagem")
    parser.add_argument("--reset-post", type=int, metavar="ID",
                        help="Regenerar um post pendente específico")
    parser.add_argument("--topic", type=str,
                        help="Tema explícito para usar com --reset-post")
    parser.add_argument("--reset-grounded-posts", action="store_true",
                        help="Regenerar posts pendentes de modelo_destaque, comparativo e tco_insight")
    parser.add_argument("--stats", action="store_true", help="Mostrar estatísticas")

    args = parser.parse_args()
    init_db()

    if args.list:
        list_posts(show_all=args.all)
    elif args.delete:
        delete_post(args.delete)
    elif args.reschedule:
        reschedule_post(int(args.reschedule[0]), args.reschedule[1])
    elif args.add_image:
        add_image_to_post(int(args.add_image[0]), args.add_image[1])
    elif args.generate_images:
        generate_missing_images()
    elif args.reset_post:
        reset_post(args.reset_post, topic_override=args.topic)
    elif args.reset_grounded_posts:
        reset_grounded_posts()
    elif args.stats:
        show_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
