"""APScheduler configuration for automated post publishing."""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_settings
from database import get_session, ScheduledPost
from publisher import InstagramPublisher

logger = logging.getLogger(__name__)


def _caption_headline(text: str | None) -> str:
    return (text or "").splitlines()[0].strip().lower()


def _find_recent_duplicate(session, post: ScheduledPost, now: datetime, hours: int = 24) -> ScheduledPost | None:
    cutoff = now - timedelta(hours=hours)
    recent_posts = (
        session.query(ScheduledPost)
        .filter(
            ScheduledPost.published == True,
            ScheduledPost.published_at != None,
            ScheduledPost.published_at >= cutoff,
        )
        .all()
    )

    current_headline = _caption_headline(post.caption)
    for recent in recent_posts:
        same_image = bool(post.image_url) and post.image_url == recent.image_url
        same_headline = current_headline and current_headline == _caption_headline(recent.caption)
        if same_image or same_headline:
            return recent
    return None


async def publish_due_posts():
    """Verifica e publica posts que estão na hora."""
    settings = get_settings()
    tz = ZoneInfo(settings.posting_timezone)
    now = datetime.now(tz)

    session = get_session()
    due_posts = (
        session.query(ScheduledPost)
        .filter(
            ScheduledPost.published == False,
            ScheduledPost.scheduled_at <= now,
            ScheduledPost.image_url != None,  # Só publica se tiver imagem
        )
        .order_by(ScheduledPost.scheduled_at)
        .limit(3)  # Máximo 3 por ciclo (rate limiting)
        .all()
    )

    if not due_posts:
        logger.debug("📭 Nenhum post pendente para publicação.")
        session.close()
        return

    publisher = InstagramPublisher()

    for post in due_posts:
        try:
            duplicate = _find_recent_duplicate(session, post, now)
            if duplicate:
                post.published = True
                post.published_at = now
                post.ig_media_id = f"duplicate_of_{duplicate.id}"
                logger.warning(
                    f"⚠️ Post {post.id} marcado como duplicado do post {duplicate.id}; pulando publicação."
                )
                session.commit()
                continue

            result = await publisher.publish_image_post(
                image_url=post.image_url,
                caption=post.caption,
                hashtags=post.hashtags,
            )
            post.published = True
            post.published_at = now
            post.ig_media_id = result.get("media_id")
            logger.info(f"✅ Post {post.id} publicado: {result['media_id']}")
            session.commit()

        except Exception as e:
            logger.error(f"❌ Falha ao publicar post {post.id}: {e}")

    session.close()


async def generate_weekly_content_job():
    """Job semanal para gerar conteúdo da próxima semana."""
    from content_generator import generate_weekly_content, save_posts_to_queue

    logger.info("🗓️ Gerando conteúdo semanal...")
    try:
        posts = generate_weekly_content()
        count = save_posts_to_queue(posts)
        logger.info(f"✅ {count} posts gerados e agendados para a semana.")
    except Exception as e:
        logger.error(f"❌ Erro ao gerar conteúdo semanal: {e}")


def create_scheduler() -> AsyncIOScheduler:
    """Cria e configura o scheduler."""
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.posting_timezone)

    # Verifica posts pendentes a cada 5 minutos
    scheduler.add_job(
        publish_due_posts,
        CronTrigger(minute="*/5"),
        id="publish_due_posts",
        name="Publicar posts agendados",
        replace_existing=True,
    )

    # Gera conteúdo toda segunda às 6h
    scheduler.add_job(
        generate_weekly_content_job,
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="weekly_content_gen",
        name="Gerar conteúdo semanal",
        replace_existing=True,
    )

    logger.info("⏰ Scheduler configurado: publish a cada 5min, content gen segunda 6h")
    return scheduler
