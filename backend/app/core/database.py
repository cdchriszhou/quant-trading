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


def _migrate_schema():
    """Add missing columns to existing tables (safe for SQLite / MySQL)."""
    from sqlalchemy import inspect

    # (table, column, SQL type fragment for ADD COLUMN)
    migrations = [
        ("orders", "broker_order_id", "VARCHAR(64) DEFAULT ''"),
    ]

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, column, col_type in migrations:
        if table not in existing_tables:
            continue
        columns = {c["name"] for c in inspector.get_columns(table)}
        if column in columns:
            continue
        ddl = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        with engine.begin() as conn:
            conn.execute(text(ddl))
        print(f"[DB] Migrated: added {table}.{column}")


def init_db():
    """Create all tables and apply lightweight schema migrations."""
    try:
        # Ensure all models are registered before create_all
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        _migrate_schema()
        # Verify connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB] Database initialization skipped: {e}")
        return False
