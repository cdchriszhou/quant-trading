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
    MARKET_DATA_SOURCE: str = "realtime"  # "realtime" or "simulated"
    TUSHARE_TOKEN: str = ""

    # Market Environment (Core 1)
    AVG_PRICE_SYMBOL: str = "880003"  # 通达信平均股价指数
    MARKET_ENV_MA_PERIOD: int = 20  # 20日均线
    MARKET_ENV_VOL_LOOKBACK: int = 20  # 成交量回溯周期
    MARKET_ENV_MIN_VOL_RATIO: float = 0.7  # 成交量不创新低的最小比例

    # Sector Filter (Core 2)
    SECTOR_TOP_N: int = 10  # 只保留前N个多头趋势板块
    SECTOR_MA_PERIODS: list = [5, 10, 20, 60]  # 行业指数均线周期
    SECTOR_STRENGTH_LOOKBACK: int = 20  # 板块20日涨跌幅比较周期
    SECTOR_CACHE_TTL: int = 300  # 板块排名缓存秒数

    # Stock Screener (Core 3)
    MIN_DAILY_AMOUNT: float = 50_000_000  # 日均成交额最低5000万（流动性门槛）
    STOCK_SCREENER_MA_PERIODS: list = [5, 10, 20, 60]  # 个股均线周期
    PULLBACK_NEAR_MA_PCT: float = 2.0  # 回踩接近均线的容忍度(%)

    # Trading
    TRADING_MODE: str = "paper"
    DEFAULT_CASH: float = 1000000.0
    COMMISSION_RATE: float = 0.00025
    MIN_COMMISSION: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
