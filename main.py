"""Main FastAPI application with webhook endpoints and scheduler."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request

from auto_responder import AutoResponder
from config import get_settings
from database import init_db
from scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + start scheduler. Shutdown: stop scheduler."""
    init_db()
    sched = create_scheduler()
    sched.start()
    logger.info("PBEV Instagram Bot iniciado.")
    yield
    sched.shutdown()
    logger.info("Bot encerrado.")


app = FastAPI(
    title="Guia PBEV Brasil - Instagram Bot",
    version="1.0.0",
    lifespan=lifespan,
)

responder = AutoResponder()


@app.get("/webhook")
async def webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification endpoint."""
    settings = get_settings()

    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        logger.info("Webhook verificado com sucesso.")
        return int(hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def webhook_receive(request: Request):
    """Receive Instagram webhook events."""
    body = await request.json()
    logger.debug("Webhook recebido: %s", body)

    for entry in body.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            message = messaging.get("message", {})
            text = message.get("text")

            if sender_id and text:
                logger.info("DM de %s: %s...", sender_id, text[:50])
                try:
                    await responder.handle_dm(sender_id=sender_id, text=text)
                except Exception as e:
                    logger.error("Falha ao processar DM de %s: %s", sender_id, e)

        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue

            value = change.get("value", {})
            comment_id = value.get("id")
            text = value.get("text")
            user_id = value.get("from", {}).get("id")
            media_id = value.get("media", {}).get("id")

            if comment_id and text and user_id:
                logger.info("Comentario de %s: %s...", user_id, text[:50])
                try:
                    await responder.handle_comment(
                        comment_id=comment_id,
                        text=text,
                        user_id=user_id,
                        media_id=media_id,
                    )
                except Exception as e:
                    logger.error("Falha ao processar comentario de %s: %s", user_id, e)

    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pbev-instagram-bot"}


@app.get("/api/queue")
async def get_queue():
    """List scheduled posts."""
    from database import ScheduledPost, get_session

    session = get_session()
    posts = (
        session.query(ScheduledPost)
        .filter(ScheduledPost.published == False)
        .order_by(ScheduledPost.scheduled_at)
        .limit(20)
        .all()
    )
    session.close()

    return [
        {
            "id": p.id,
            "category": p.category,
            "caption_preview": p.caption[:100] + "..." if len(p.caption) > 100 else p.caption,
            "scheduled_at": p.scheduled_at.isoformat(),
            "has_image": bool(p.image_url),
        }
        for p in posts
    ]


@app.post("/api/generate")
async def trigger_generation(days: int = 7):
    """Force content generation."""
    from content_generator import generate_weekly_content, save_posts_to_queue

    posts = generate_weekly_content()
    count = save_posts_to_queue(posts)
    return {"generated": count, "message": f"{count} posts gerados e agendados."}


@app.get("/api/analytics")
async def get_analytics():
    """Return Plausible insights for the last 30 days."""
    from analytics import get_content_insights

    try:
        insights = await get_content_insights()
        return {
            "status": "ok",
            "ig_traffic": insights.get("ig_traffic", {}),
            "best_categories": insights.get("best_categories", []),
            "top_pages": insights.get("top_pages", []),
            "recommendation": insights.get("recommendation", ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
