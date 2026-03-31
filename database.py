"""SQLite database models for post queue and conversation tracking."""

import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Enum
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

Base = declarative_base()


class ScheduledPost(Base):
    """Posts agendados para publicação."""
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    caption = Column(Text, nullable=False)
    hashtags = Column(Text, default="")
    image_url = Column(String(500), nullable=True)  # URL pública da imagem
    image_path = Column(String(500), nullable=True)  # Path local (backup)
    scheduled_at = Column(DateTime, nullable=False)
    published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    ig_media_id = Column(String(100), nullable=True)  # ID retornado pela API
    post_type = Column(String(50), default="image")  # image, carousel, reel
    category = Column(String(100), default="geral")  # modelo, comparativo, dica, tco, noticia
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        status = "✅" if self.published else "⏳"
        return f"<Post {self.id} {status} [{self.category}] {self.scheduled_at}>"


class ConversationLog(Base):
    """Log de conversas (DMs e comentários) para contexto."""
    __tablename__ = "conversation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ig_user_id = Column(String(100), nullable=False)
    ig_username = Column(String(100), nullable=True)
    message_type = Column(String(20), default="dm")  # dm, comment
    incoming_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=True)
    media_id = Column(String(100), nullable=True)  # p/ comentários
    responded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ContentIdea(Base):
    """Ideias de conteúdo geradas pelo Claude."""
    __tablename__ = "content_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(200), nullable=False)
    caption = Column(Text, nullable=False)
    hashtags = Column(Text, default="")
    category = Column(String(100), default="geral")
    image_prompt = Column(Text, nullable=True)  # Prompt p/ gerar imagem
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# --- Database setup ---

def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, echo=False)


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db():
    """Create all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ Database initialized.")


if __name__ == "__main__":
    init_db()
