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

    # Auth / ops
    ALLOW_REGISTER: bool = True           # set false in production
    SEED_DEMO_USERS: bool = True          # set false in production (skips demo user only)
    REQUIRE_STRONG_SECRET: bool = False   # set true in production to refuse default SECRET_KEY
    # Empty DB bootstrap: always create first admin when user table is empty
    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin123"  # change after first login

    # CORS
    CORS_ORIGINS: list = ["http://localhost:8888", "http://localhost:80",
                          "http://127.0.0.1:8888", "http://localhost:8000"]

    # Market data
    MARKET_DATA_SOURCE: str = "realtime"  # always real market APIs
    TUSHARE_TOKEN: str = ""

    # Market Environment (Core 1)
    # Leave empty to use real cross-section avg; only set exchange codes like 000001.SH
    AVG_PRICE_SYMBOL: str = ""
    MARKET_ENV_MA_PERIOD: int = 20  # 20日均线
    MARKET_ENV_VOL_LOOKBACK: int = 20  # 成交量回溯周期
    MARKET_ENV_MIN_VOL_RATIO: float = 0.7  # 成交量不创新低的最小比例
    MARKET_ENV_SLOPE_LOOKBACK: int = 5  # MA20 斜率回溯天数（避免单日噪声）
    MARKET_ENV_CAUTION_EXTENSION_PCT: float = 5.0  # 偏离 MA20 超过该%开始谨慎
    MARKET_ENV_MAX_EXTENSION_PCT: float = 8.0  # 偏离 MA20 超过该%视为过热，禁止新开仓

    # Sector Filter (Core 2)
    SECTOR_TOP_N: int = 10  # 只保留前N个多头趋势板块
    SECTOR_MA_PERIODS: list = [5, 10, 20, 60]  # 行业指数均线周期
    SECTOR_STRENGTH_LOOKBACK: int = 20  # 板块20日涨跌幅比较周期
    SECTOR_CACHE_TTL: int = 300  # 板块排名新鲜缓存秒数
    SECTOR_STALE_TTL: int = 1800  # 过期后仍可返回旧排名并后台刷新（秒）

    # Stock Screener (Core 3)
    MIN_DAILY_AMOUNT: float = 10_000_000  # 日均成交额最低1000万（元，剔除僵尸股）
    STOCK_SCREENER_MA_PERIODS: list = [5, 10, 20, 60]  # 个股均线周期
    PULLBACK_NEAR_MA_PCT: float = 2.0  # 回踩接近均线的容忍度(%)

    # Trading
    TRADING_MODE: str = "paper"  # default account mode for new sessions
    DEFAULT_CASH: float = 1000000.0
    # A-share fee schedule (真实费率)
    COMMISSION_RATE: float = 0.00025      # 佣金 万2.5
    MIN_COMMISSION: float = 5.0           # 佣金最低 5 元
    STAMP_DUTY_RATE: float = 0.0005       # 印花税 卖出 0.05%
    TRANSFER_FEE_RATE: float = 0.00001    # 过户费 双向 0.001%
    # Live broker (MiniQMT) — default paper; set to qmt/xtp/... for live
    BROKER_TYPE: str = "paper"            # "paper", "qmt", "xtp", "ptrade", "ctp", "custom"
    ALLOW_LIVE_TRADING: bool = False      # safety switch — must enable explicitly
    QMT_MINI_PATH: str = ""               # e.g. D:/国金证券QMT交易端/userdata_mini
    QMT_ACCOUNT_ID: str = ""              # 资金账号

    # LLM providers (OpenAI-compatible chat/completions)
    LLM_DEFAULT_PROVIDER: str = "deepseek"  # deepseek | glm | kimi | qwen
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4-flash"
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "moonshot-v1-8k"
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    class Config:
        env_file = ".env"
        case_sensitive = False


def env_file_path() -> str:
    """Absolute path to backend/.env (created on first save if missing)."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(backend_dir, ".env")


def update_env_values(updates: dict[str, str]) -> str:
    """Upsert key=value pairs into .env and return the file path."""
    path = env_file_path()
    lines: list[str] = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    keys = {k.upper(): str(v) for k, v in updates.items()}
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        key_u = key.upper()
        if key_u in keys:
            out.append(f"{key_u}={keys[key_u]}")
            seen.add(key_u)
        else:
            out.append(line)

    for key_u, val in keys.items():
        if key_u not in seen:
            out.append(f"{key_u}={val}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
    return path


def apply_live_broker_settings(
    *,
    allow_live_trading: bool | None = None,
    broker_type: str | None = None,
    qmt_mini_path: str | None = None,
    qmt_account_id: str | None = None,
) -> dict:
    """Persist live-broker settings to .env and update in-memory settings."""
    payload: dict[str, str] = {}
    if allow_live_trading is not None:
        settings.ALLOW_LIVE_TRADING = bool(allow_live_trading)
        payload["ALLOW_LIVE_TRADING"] = "true" if allow_live_trading else "false"
    if broker_type is not None:
        settings.BROKER_TYPE = (broker_type or "qmt").strip() or "qmt"
        payload["BROKER_TYPE"] = settings.BROKER_TYPE
    if qmt_mini_path is not None:
        settings.QMT_MINI_PATH = (qmt_mini_path or "").strip()
        payload["QMT_MINI_PATH"] = settings.QMT_MINI_PATH
    if qmt_account_id is not None:
        settings.QMT_ACCOUNT_ID = (qmt_account_id or "").strip()
        payload["QMT_ACCOUNT_ID"] = settings.QMT_ACCOUNT_ID

    path = update_env_values(payload) if payload else env_file_path()
    return {
        "env_file": path,
        "allow_live_trading": settings.ALLOW_LIVE_TRADING,
        "broker_type": settings.BROKER_TYPE,
        "qmt_mini_path": settings.QMT_MINI_PATH,
        "qmt_account_id": settings.QMT_ACCOUNT_ID,
    }


def _mask_secret(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:3]}…{s[-4:]}"


def llm_provider_snapshot(*, mask_keys: bool = True) -> dict:
    """Public-safe snapshot of LLM provider settings."""
    providers = {
        "deepseek": {
            "id": "deepseek",
            "name": "DeepSeek",
            "api_key": settings.DEEPSEEK_API_KEY or "",
            "base_url": settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com",
            "model": settings.DEEPSEEK_MODEL or "deepseek-chat",
        },
        "glm": {
            "id": "glm",
            "name": "智谱 GLM",
            "api_key": settings.GLM_API_KEY or "",
            "base_url": settings.GLM_BASE_URL or "https://open.bigmodel.cn/api/paas/v4",
            "model": settings.GLM_MODEL or "glm-4-flash",
        },
        "kimi": {
            "id": "kimi",
            "name": "Kimi",
            "api_key": settings.KIMI_API_KEY or "",
            "base_url": settings.KIMI_BASE_URL or "https://api.moonshot.cn/v1",
            "model": settings.KIMI_MODEL or "moonshot-v1-8k",
        },
        "qwen": {
            "id": "qwen",
            "name": "通义千问",
            "api_key": settings.QWEN_API_KEY or "",
            "base_url": settings.QWEN_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": settings.QWEN_MODEL or "qwen-plus",
        },
    }
    out = []
    for p in providers.values():
        key = p["api_key"]
        out.append({
            "id": p["id"],
            "name": p["name"],
            "configured": bool(key.strip()),
            "api_key": _mask_secret(key) if mask_keys else key,
            "api_key_set": bool(key.strip()),
            "base_url": p["base_url"],
            "model": p["model"],
        })
    default = (settings.LLM_DEFAULT_PROVIDER or "deepseek").strip().lower()
    if default not in providers:
        default = "deepseek"
    return {
        "default_provider": default,
        "providers": out,
    }


def apply_llm_settings(payload: dict) -> dict:
    """Persist LLM settings to .env and update in-memory settings.

    Empty api_key string means "leave unchanged". Pass clear_api_key=true to wipe.
    """
    env_payload: dict[str, str] = {}
    default = payload.get("default_provider")
    if default is not None:
        d = str(default).strip().lower() or "deepseek"
        if d not in ("deepseek", "glm", "kimi", "qwen"):
            d = "deepseek"
        settings.LLM_DEFAULT_PROVIDER = d
        env_payload["LLM_DEFAULT_PROVIDER"] = d

    mapping = {
        "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"),
        "glm": ("GLM_API_KEY", "GLM_BASE_URL", "GLM_MODEL"),
        "kimi": ("KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL"),
        "qwen": ("QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_MODEL"),
    }
    providers = payload.get("providers") or []
    for item in providers:
        pid = str(item.get("id") or "").strip().lower()
        if pid not in mapping:
            continue
        key_attr, url_attr, model_attr = mapping[pid]
        if item.get("clear_api_key"):
            setattr(settings, key_attr, "")
            env_payload[key_attr] = ""
        elif "api_key" in item and item.get("api_key") not in (None, ""):
            # Ignore masked placeholders from UI round-trip
            raw = str(item.get("api_key") or "").strip()
            if "…" not in raw and "*" not in raw:
                setattr(settings, key_attr, raw)
                env_payload[key_attr] = raw
        if item.get("base_url") is not None:
            url = str(item.get("base_url") or "").strip()
            setattr(settings, url_attr, url)
            env_payload[url_attr] = url
        if item.get("model") is not None:
            model = str(item.get("model") or "").strip()
            setattr(settings, model_attr, model)
            env_payload[model_attr] = model

    path = update_env_values(env_payload) if env_payload else env_file_path()
    snap = llm_provider_snapshot(mask_keys=True)
    snap["env_file"] = path
    return snap


settings = Settings()
