"""Application configuration."""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    APP_NAME: str = "Quant Trading System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database — default SQLite for development; set DB_DRIVER=mysql for production
    DB_DRIVER: str = "sqlite"  # "sqlite" or "mysql"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "quant123"
    DB_NAME: str = "quant_trading"
    DATABASE_URL: Optional[str] = None  # Override auto-build

    @property
    def db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if self.DB_DRIVER == "mysql":
            return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        # SQLite
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", f"{self.DB_NAME}.db")
        return f"sqlite:///{db_path}"

    @property
    def db_connect_args(self) -> dict:
        if self.DB_DRIVER == "mysql":
            return {}
        return {"check_same_thread": False}

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = ""
    REDIS_URL: str = ""

    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        pw = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{pw}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # JWT
    SECRET_KEY: str = "quant-trading-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS
    CORS_ORIGINS: list = ["http://localhost:8888", "http://localhost:80",
                          "http://127.0.0.1:8888", "http://localhost:8000"]

    # Market data
    MARKET_DATA_SOURCE: str = "realtime"
    TUSHARE_TOKEN: str = ""

    # Trading
    TRADING_MODE: str = "paper"
    DEFAULT_CASH: float = 1000000.0
    COMMISSION_RATE: float = 0.00025
    MIN_COMMISSION: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
