from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def init_db() -> None:
    """
    Crée les tables si elles n'existent pas.
    """
    import app.services.job_store  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db_session():
    """
    Session DB simple à utiliser dans les services.
    """
    db = SessionLocal()

    try:
        return db
    except Exception:
        db.close()
        raise