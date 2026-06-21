"""Database session management — supports both SQLite and MySQL."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text

from app.core.config import settings

engine = create_engine(
    settings.db_url,
    connect_args=settings.db_connect_args,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Enable WAL mode for SQLite for better concurrent access
if settings.DB_DRIVER == "sqlite":
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call when DB is unavailable."""
    try:
        Base.metadata.create_all(bind=engine)
        # Verify connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB] Database initialization skipped: {e}")
        return False
