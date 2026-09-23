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
<<<<<<< HEAD
    """Create all tables and apply lightweight schema migrations."""
=======
    """Create all tables. Safe to call when DB is unavailable."""
    # Ensure all models are registered on Base.metadata
    import app.models  # noqa: F401

>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    try:
        # Ensure all models are registered before create_all
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)
<<<<<<< HEAD
        _migrate_schema()
        # Verify connection
=======
        _migrate_sqlite_columns()
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB] Database initialization skipped: {e}")
        return False


def _table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    cols = _table_columns(conn, table)
    if column in cols:
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    print(f"[DB] Migrated {table}.{column}")


def _migrate_sqlite_columns():
    """Add newly introduced columns on existing SQLite DBs."""
    if settings.DB_DRIVER != "sqlite":
        return
    try:
        with engine.begin() as conn:
            # users
            if "users" in {r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).fetchall()}:
                _add_column_if_missing(
                    conn, "users", "account_mode",
                    "account_mode VARCHAR(16) DEFAULT 'paper'",
                )

            # orders / trades / positions — trade_mode
            for table in ("orders", "trades", "positions"):
                try:
                    _add_column_if_missing(
                        conn, table, "trade_mode",
                        "trade_mode VARCHAR(16) DEFAULT 'paper'",
                    )
                except Exception as e:
                    print(f"[DB] Skip {table}.trade_mode: {e}")

            # positions.available_quantity
            try:
                _add_column_if_missing(
                    conn, "positions", "available_quantity",
                    "available_quantity FLOAT DEFAULT 0",
                )
            except Exception as e:
                print(f"[DB] Skip positions.available_quantity: {e}")

            # symbol_name columns (display)
            for table in ("orders", "trades", "positions"):
                try:
                    _add_column_if_missing(
                        conn, table, "symbol_name",
                        "symbol_name VARCHAR(64) DEFAULT ''",
                    )
                except Exception as e:
                    print(f"[DB] Skip {table}.symbol_name: {e}")
    except Exception as e:
        print(f"[DB] Column migration skipped: {e}")
