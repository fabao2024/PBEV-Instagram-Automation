"""Instagram publisher via Meta Graph API.

Handles image upload and post publishing for Instagram Business accounts.

Fluxo da API:
1. POST /ig-user/media — cria container de mídia (image_url + caption)
2. POST /ig-user/media_publish — publica o container
"""

import logging
import time

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _raise_meta_error(resp: httpx.Response, action: str):
    """Raise a readable error that includes Meta's response body."""
    try:
        details = resp.json()
    except Exception:
        details = resp.text

    raise RuntimeError(f"{action} falhou: HTTP {resp.status_code} - {details}")


class InstagramPublisher:
    """Publica posts no Instagram via Meta Graph API."""

    def __init__(self):
        self.settings = get_settings()
        self.access_token = self.settings.meta_access_token
        self.ig_account_id = self.settings.instagram_business_account_id

    @property
    def _base_params(self) -> dict:
        return {"access_token": self.access_token}

    async def publish_image_post(
        self,
        image_url: str,
        caption: str,
        hashtags: str = "",
    ) -> dict:
        """Publica um post de imagem no Instagram.

        Args:
            image_url: URL pública da imagem (Instagram faz download dela).
            caption: Legenda do post.
            hashtags: Hashtags adicionais.

        Returns:
            Dict com media_id e status.
        """
        full_caption = f"{caption}\n\n{hashtags}".strip()

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Criar container de mídia
            container_response = await client.post(
                f"{GRAPH_API_BASE}/{self.ig_account_id}/media",
                params={
                    **self._base_params,
                    "image_url": image_url,
                    "caption": full_caption,
                },
            )
            container_response.raise_for_status()
            container_data = container_response.json()
            container_id = container_data["id"]
            logger.info(f"📦 Container criado: {container_id}")

            # Step 2: Aguardar processamento (poll status)
            await self._wait_for_container(client, container_id)

            # Step 3: Publicar
            publish_response = await client.post(
                f"{GRAPH_API_BASE}/{self.ig_account_id}/media_publish",
                params={
                    **self._base_params,
                    "creation_id": container_id,
                },
            )
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            media_id = publish_data["id"]

            logger.info(f"✅ Post publicado! Media ID: {media_id}")
            return {"media_id": media_id, "status": "published"}

    async def publish_carousel_post(
        self,
        image_urls: list[str],
        caption: str,
        hashtags: str = "",
    ) -> dict:
        """Publica um carousel (múltiplas imagens)."""
        full_caption = f"{caption}\n\n{hashtags}".strip()

        async with httpx.AsyncClient(timeout=120) as client:
            # Criar containers individuais para cada imagem
            children_ids = []
            for url in image_urls:
                resp = await client.post(
                    f"{GRAPH_API_BASE}/{self.ig_account_id}/media",
                    params={
                        **self._base_params,
                        "image_url": url,
                        "is_carousel_item": "true",
                    },
                )
                resp.raise_for_status()
                children_ids.append(resp.json()["id"])
                await self._wait_for_container(client, resp.json()["id"])

            # Criar container do carousel
            carousel_resp = await client.post(
                f"{GRAPH_API_BASE}/{self.ig_account_id}/media",
                params={
                    **self._base_params,
                    "media_type": "CAROUSEL",
                    "caption": full_caption,
                    "children": ",".join(children_ids),
                },
            )
            carousel_resp.raise_for_status()
            carousel_id = carousel_resp.json()["id"]
            await self._wait_for_container(client, carousel_id)

            # Publicar
            pub_resp = await client.post(
                f"{GRAPH_API_BASE}/{self.ig_account_id}/media_publish",
                params={
                    **self._base_params,
                    "creation_id": carousel_id,
                },
            )
            pub_resp.raise_for_status()
            media_id = pub_resp.json()["id"]

            logger.info(f"✅ Carousel publicado! Media ID: {media_id} ({len(image_urls)} imagens)")
            return {"media_id": media_id, "status": "published", "images": len(image_urls)}

    async def reply_to_comment(self, comment_id: str, message: str) -> dict:
        """Responde a um comentário no Instagram."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GRAPH_API_BASE}/{comment_id}/replies",
                params={
                    **self._base_params,
                    "message": message,
                },
            )
            if resp.is_error:
                _raise_meta_error(resp, f"Resposta ao comentario {comment_id}")
            return resp.json()

    async def send_dm(self, recipient_id: str, message: str) -> dict:
        """Envia DM via Instagram Messaging API."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GRAPH_API_BASE}/{self.settings.facebook_page_id}/messages",
                params=self._base_params,
                json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": message},
                },
            )
            if resp.is_error:
                _raise_meta_error(resp, f"Envio de DM para {recipient_id}")
            return resp.json()

    async def _wait_for_container(
        self, client: httpx.AsyncClient, container_id: str, max_retries: int = 10
    ):
        """Poll container status até estar pronto."""
        for i in range(max_retries):
            resp = await client.get(
                f"{GRAPH_API_BASE}/{container_id}",
                params={**self._base_params, "fields": "status_code"},
            )
            data = resp.json()
            status = data.get("status_code")

            if status == "FINISHED":
                return
            elif status == "ERROR":
                raise RuntimeError(f"Container {container_id} falhou: {data}")

            wait_time = min(2 ** i, 30)
            logger.debug(f"⏳ Container {container_id} status={status}, aguardando {wait_time}s...")
            time.sleep(wait_time)

        raise TimeoutError(f"Container {container_id} não ficou pronto em {max_retries} tentativas")
