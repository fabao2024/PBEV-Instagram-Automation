"""Auto responder for Instagram DMs and comments."""

import logging

from google import genai
from google.genai import types

from config import get_settings
from database import ConversationLog, get_session
from ev_knowledge import PBEV_SYSTEM_CONTEXT
from publisher import InstagramPublisher

logger = logging.getLogger(__name__)

MAX_COMMENT_LENGTH = 300
MAX_DM_LENGTH = 500

SPAM_KEYWORDS = [
    "ganhe dinheiro",
    "renda extra",
    "clique no link",
    "sigam",
    "promocao imperdivel",
    "promoção imperdível",
    "curso gratis",
    "curso grátis",
    "dm pra saber",
]


class AutoResponder:
    """Generate and send automatic replies for DMs and comments."""

    def __init__(self):
        self.settings = get_settings()
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        self.publisher = InstagramPublisher()

    async def handle_comment(self, comment_id: str, text: str, user_id: str, media_id: str):
        """Process a comment and reply when relevant."""
        if self._is_spam(text):
            logger.info("Spam detectado de %s, ignorando.", user_id)
            return

        if not self._should_respond_to_comment(text):
            logger.info("Comentario de %s nao requer resposta automatica.", user_id)
            return

        response = self._generate_response(
            message=text,
            message_type="comment",
            max_length=MAX_COMMENT_LENGTH,
        )

        if not response:
            return

        try:
            await self.publisher.reply_to_comment(comment_id, response)
        except Exception as e:
            logger.error("Falha ao responder comentario de %s: %s", user_id, e)
            return

        self._log_conversation(
            ig_user_id=user_id,
            message_type="comment",
            incoming_text=text,
            response_text=response,
            media_id=media_id,
            responded=True,
        )
        logger.info("Respondido comentario de %s", user_id)

    async def handle_dm(self, sender_id: str, text: str):
        """Process a DM and try to reply."""
        if self._is_spam(text):
            logger.info("Spam DM de %s, ignorando.", sender_id)
            return

        history = self._get_recent_history(sender_id, limit=5)
        response = self._generate_response(
            message=text,
            message_type="dm",
            max_length=MAX_DM_LENGTH,
            conversation_history=history,
        )

        if not response:
            return

        try:
            await self.publisher.send_dm(sender_id, response)
        except Exception as e:
            logger.error("Falha ao responder DM de %s: %s", sender_id, e)
            self._log_conversation(
                ig_user_id=sender_id,
                message_type="dm",
                incoming_text=text,
                response_text=response,
                responded=False,
            )
            return

        self._log_conversation(
            ig_user_id=sender_id,
            message_type="dm",
            incoming_text=text,
            response_text=response,
            responded=True,
        )
        logger.info("Respondido DM de %s", sender_id)

    def _generate_response(
        self,
        message: str,
        message_type: str = "dm",
        max_length: int = 500,
        conversation_history: list[dict] | None = None,
    ) -> str | None:
        """Generate a reply with Gemini and truncate to the target length."""
        if self._is_dc_charging_map_request(message):
            return self._dc_charging_map_response(message_type=message_type, max_length=max_length)

        system = f"""{PBEV_SYSTEM_CONTEXT}

REGRAS ADICIONAIS PARA RESPOSTAS AUTOMATICAS:
- Tipo: {"comentario publico" if message_type == "comment" else "mensagem direta"}
- Maximo {max_length} caracteres
- Se for comentario, seja mais conciso e direto
- Se nao souber a resposta, direcione ao site ou ao Consultor EletriBrasil
- Nao responda a spam, propaganda ou mensagens ofensivas
- Se a mensagem for um simples emoji ou "👏", responda com agradecimento breve
"""

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7,
            max_output_tokens=512,
        )

        history = []
        if conversation_history:
            for entry in conversation_history:
                history.append(types.Content(
                    role="user", parts=[types.Part(text=entry["incoming"])]
                ))
                if entry.get("response"):
                    history.append(types.Content(
                        role="model", parts=[types.Part(text=entry["response"])]
                    ))

        try:
            chat = self.client.chats.create(
                model=self.settings.gemini_model,
                config=config,
                history=history,
            )
            response = chat.send_message(message)
            text = response.text.strip()

            if len(text) > max_length:
                text = self._truncate_response(text, max_length)

            return text
        except Exception as e:
            logger.error("Erro ao gerar resposta: %s", e)
            return None

    def _should_respond_to_comment(self, text: str) -> bool:
        """Determine whether a comment deserves an automatic reply."""
        text_lower = text.lower().strip()

        if "?" in text_lower:
            return True

        ev_keywords = [
            "elétrico",
            "eletrico",
            "bateria",
            "autonomia",
            "recarga",
            "carregador",
            "byd",
            "tesla",
            "gwm",
            "volvo",
            "nissan leaf",
            "preço",
            "preco",
            "custo",
            "economia",
            "tco",
            "quanto custa",
            "vale a pena",
            "compensa",
        ]
        return any(kw in text_lower for kw in ev_keywords)

    def _is_spam(self, text: str) -> bool:
        """Detect spammy messages."""
        normalized = self._normalize_text(text)
        return any(self._normalize_text(kw) in normalized for kw in SPAM_KEYWORDS)

    @staticmethod
    def _truncate_response(text: str, max_length: int) -> str:
        """Trim a reply without cutting words abruptly."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rsplit(" ", 1)[0] + "..."

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for simple keyword matching."""
        replacements = str.maketrans(
            {
                "á": "a",
                "à": "a",
                "â": "a",
                "ã": "a",
                "é": "e",
                "ê": "e",
                "í": "i",
                "ó": "o",
                "ô": "o",
                "õ": "o",
                "ú": "u",
                "ü": "u",
                "ç": "c",
            }
        )
        return text.lower().translate(replacements)

    def _is_dc_charging_map_request(self, text: str) -> bool:
        """Detect requests about DC fast charging locations."""
        normalized = f" {self._normalize_text(text)} "
        dc_signals = [
            " dc ",
            " carga rapida ",
            " carregamento rapido ",
            " recarga rapida ",
            " carregador rapido ",
            " carregadores rapidos ",
            " eletroposto dc ",
            " pontos dc ",
            " ponto dc ",
        ]
        locator_signals = [
            " onde ",
            " local ",
            " locais ",
            " mapa ",
            " mapas ",
            " encontrar ",
            " perto ",
            " proximo ",
            " proximos ",
            " brasil ",
        ]
        if any(signal in normalized for signal in dc_signals):
            return True
        return (
            (" carregador " in normalized or " recarga " in normalized or " carga " in normalized)
            and any(signal in normalized for signal in locator_signals)
            and " ac " not in normalized
        )

    def _dc_charging_map_response(self, message_type: str, max_length: int) -> str:
        """Return a deterministic reply for DC charging map requests."""
        if message_type == "comment":
            text = "O Guia PBEV tem um mapa do Brasil com varios pontos de recarga DC. Veja no Guia PBEV: guiapbev.cloud"
        else:
            text = "O Guia PBEV tem uma funcionalidade com mapa do Brasil e varios pontos de recarga DC. Veja no Guia PBEV: guiapbev.cloud"
        return self._truncate_response(text, max_length)

    def _get_recent_history(self, user_id: str, limit: int = 5) -> list[dict]:
        """Load recent DM history for context."""
        session = get_session()
        logs = (
            session.query(ConversationLog)
            .filter_by(ig_user_id=user_id, message_type="dm")
            .order_by(ConversationLog.created_at.desc())
            .limit(limit)
            .all()
        )
        session.close()

        return [
            {"incoming": log.incoming_text, "response": log.response_text}
            for log in reversed(logs)
        ]

    def _log_conversation(
        self,
        ig_user_id: str,
        message_type: str,
        incoming_text: str,
        response_text: str,
        media_id: str | None = None,
        responded: bool = True,
    ):
        """Persist a DM or comment interaction."""
        session = get_session()
        log = ConversationLog(
            ig_user_id=ig_user_id,
            message_type=message_type,
            incoming_text=incoming_text,
            response_text=response_text,
            media_id=media_id,
            responded=responded,
        )
        session.add(log)
        session.commit()
        session.close()
