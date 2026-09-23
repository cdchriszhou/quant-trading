"""Data Engine: Market data fetching from real Chinese stock APIs."""

import collections
import datetime
import json
import os
import re
import threading
import time
from typing import Optional

import pandas as pd
import httpx

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

_EM_HOSTS = (
    "https://push2delay.eastmoney.com",
    "https://82.push2.eastmoney.com",
    "https://80.push2.eastmoney.com",
    "https://79.push2.eastmoney.com",
    "https://88.push2.eastmoney.com",
    "https://push2.eastmoney.com",
)

# History K-line hosts (push2his often drops connections; delay host is more stable)
_EM_HIS_HOSTS = (
    "https://push2delay.eastmoney.com",
    "https://push2his.eastmoney.com",
    "https://82.push2his.eastmoney.com",
    "https://79.push2his.eastmoney.com",
)

# web.ifzq.gtimg.cn/fqkline returns 501 — do not use
_TX_KLINE_ENDPOINTS = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get",
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get",
)

# Liquid A-share seed for avg-price / search when upstream lists are down
_LIQUID_SEED_CODES = (
    "600519.SH", "601318.SH", "600036.SH", "601166.SH", "600000.SH",
    "601398.SH", "601288.SH", "601988.SH", "600030.SH", "601688.SH",
    "000001.SZ", "000002.SZ", "000858.SZ", "000333.SZ", "000651.SZ",
    "002415.SZ", "002594.SZ", "002304.SZ", "002142.SZ", "000568.SZ",
    "300750.SZ", "300059.SZ", "300015.SZ", "300124.SZ", "300014.SZ",
    "688981.SH", "688041.SH", "688256.SH", "688008.SH", "688111.SH",
    "601012.SH", "600900.SH", "600276.SH", "600887.SH", "601888.SH",
    "002475.SZ", "002371.SZ", "002230.SZ", "002460.SZ", "003816.SZ",
)


class _LRUCache:
    """Simple LRU cache with TTL support and max size eviction. Thread-safe."""

    def __init__(self, max_size: int = 500):
        self._cache: dict = {}
        self._access: collections.OrderedDict = collections.OrderedDict()
        self._max_size = max_size
        self._lock = __import__('threading').Lock()

    def get(self, key: str, ttl: float) -> object | None:
        now = time.time()
        with self._lock:
            if key in self._cache:
                data, ts = self._cache[key]
                if now - ts < ttl:
                    # Move to end (most recently used)
                    self._access.move_to_end(key)
                    return data
                # Expired — remove
                del self._cache[key]
                del self._access[key]
            return None

    def set(self, key: str, data):
        now = time.time()
        with self._lock:
            if key in self._cache:
                # Update existing
                self._cache[key] = (data, now)
                self._access.move_to_end(key)
            else:
                # Evict oldest if at capacity
                while len(self._cache) >= self._max_size:
                    oldest = next(iter(self._access))
                    del self._cache[oldest]
                    del self._access[oldest]
                self._cache[key] = (data, now)
                self._access[key] = None

    def size(self) -> int:
        with self._lock:
            return len(self._cache)


class DataEngine:
    """Market data engine — fetches real data from Tencent & East Money APIs.

    Data sources:
      - Tencent Finance (qt.gtimg.cn)  — real-time quotes, market indices
      - East Money (push2his.eastmoney.com) — K-line, historical data
    """

    def __init__(self, source: str = "realtime"):
        self.source = source  # kept for compatibility; always uses real APIs
        self._cache = _LRUCache(max_size=500)
        self._cache_ttl = {
            "quote": 3,
            "kline": 60,
            "index": 5,
            "history": 120,
            "sector": 60,
            "top_movers": 45,
            "insight": 90,
            "company": 3600,
            "news": 300,
        }
        self._last_request = 0.0
        self._min_interval = 0.3
        self._rate_lock = __import__('threading').Lock()
        self._http_client: Optional[httpx.Client] = None
        self._industry_map: dict[str, list[str]] | None = None
        self._industry_map_lock = threading.Lock()

        # Boot: disk cache first so EM outages don't break search / avg-price
        self._symbols: list = []
        self._symbols_source: str = "empty"
        self._symbols_lock = threading.Lock()
        self._symbol_cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "ashare_symbols.json",
        )
        cached = self._load_symbol_disk_cache()
        if cached:
            self._symbols = cached
            self._symbols_source = "disk_cache"
            print(f"[DataEngine] Loaded {len(cached)} symbols from disk cache")
        print("[DataEngine] Initialized; refreshing A-share list in background…")
        threading.Thread(target=self._async_load_symbols, name="em-stock-list", daemon=True).start()

    def _async_load_symbols(self) -> None:
        """Background load of full A-share list from East Money / Sina."""
        try:
            self.ensure_symbol_list(min_count=100)
        except Exception as e:
            print(f"[DataEngine] Async stock list failed: {e}")

    def _async_full_sina_refresh(self) -> None:
        """Fill remaining Sina pages after a partial ensure()."""
        try:
            full = self._fetch_sina_stock_list(max_pages=80)
            if full and len(full) > len(self._symbols):
                self._set_symbols(full, "sina")
                print(f"[DataEngine] Sina full list ready: {len(full)}")
        except Exception as e:
            print(f"[DataEngine] Sina full refresh failed: {e}")

    # ── HTTP client ──────────────────────────────────────────────

    @property
    def http(self) -> httpx.Client:
        if self._http_client is None:
<<<<<<< HEAD
            # Use connection pooling with keep-alive for better performance
            # limits: max 20 total connections, max 5 per host
            limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
            self._http_client = httpx.Client(
                timeout=15,
                verify=False,
                trust_env=False,
                follow_redirects=True,
                limits=limits,
                http2=False,  # Tencent/EastMoney APIs don't support HTTP/2
=======
            self._http_client = httpx.Client(
                timeout=httpx.Timeout(8.0, connect=3.0),
                verify=False,
                follow_redirects=True,
                headers=_DEFAULT_HEADERS,
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
            )
        return self._http_client

    def _rate_limit(self, min_interval: float = None):
        """Enforce minimum interval between API requests. Accepts override for bulk ops.

        Thread-safe: uses a lock only to compute the wait time, not during sleep,
        so parallel callers (e.g. sector K-line fetch) can overlap HTTP I/O while
        still maintaining a minimum gap between request starts.
        """
        interval = min_interval if min_interval is not None else self._min_interval
        with self._rate_lock:
            elapsed = time.time() - self._last_request
            wait = max(0.0, interval - elapsed)
            self._last_request = time.time() + wait
        if wait > 0:
            time.sleep(wait)

    def _reset_http_client(self) -> None:
        """Drop pooled connections after upstream disconnects."""
        client = self._http_client
        self._http_client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def _http_get(self, url: str, headers: dict | None = None, retries: int = 3) -> httpx.Response:
        """GET with retry and backoff. Do not retry hard client/upstream rejections."""
        merged = {**_DEFAULT_HEADERS, **(headers or {})}
        last_error = None
        for attempt in range(retries):
            try:
                self._rate_limit()
                resp = self.http.get(url, headers=merged)
                # 501 on dead Tencent hosts — fail immediately so caller can try next URL
                if resp.status_code in (400, 401, 403, 404, 501):
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_error = e
                # Don't burn retries on permanent upstream rejections
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in (400, 401, 403, 404, 501):
                    break
                # Connection drops poison the pool — recreate client before retry
                err_name = type(e).__name__
                err_msg = str(e).lower()
                if "disconnect" in err_msg or "RemoteProtocol" in err_name or "Connection" in err_name:
                    self._reset_http_client()
                if attempt < retries - 1:
                    time.sleep((attempt + 1) * 0.8)
        raise last_error  # type: ignore[misc]

    def _http_get_json(self, url: str, headers: dict | None = None, retries: int = 3) -> dict:
        return self._http_get(url, headers=headers, retries=retries).json()

    @staticmethod
    def _parse_tencent_payload(text: str) -> dict:
        """Parse Tencent K-line JSON or JSONP (`kline_dayqfq={...}`)."""
        text = (text or "").strip()
        if not text:
            raise ValueError("empty tencent payload")
        if text[0] in "{[":
            return json.loads(text)
        eq = text.find("={")
        if eq >= 0:
            return json.loads(text[eq + 1 :])
        m = re.search(r"(\{.*\})\s*$", text, re.S)
        if m:
            return json.loads(m.group(1))
        raise ValueError("unrecognized tencent payload")

    def _em_his_get_json(self, path_query: str, retries: int = 2) -> dict:
        """East Money history API with host failover."""
        em_headers = {"Referer": "https://quote.eastmoney.com/"}
        last_error = None
        for host in _EM_HIS_HOSTS:
            url = f"{host}{path_query}"
            try:
                return self._http_get_json(url, headers=em_headers, retries=retries)
            except Exception as e:
                last_error = e
        raise last_error  # type: ignore[misc]

    def _em_get_json(self, path_query: str, retries: int = 3) -> dict:
        """East Money API with host failover."""
        em_headers = {"Referer": "https://quote.eastmoney.com/"}
        last_error = None
        for host in _EM_HOSTS:
            url = f"{host}{path_query}"
            try:
                return self._http_get_json(url, headers=em_headers, retries=retries)
            except Exception as e:
                last_error = e
        raise last_error  # type: ignore[misc]

    # ── Symbol format conversion ─────────────────────────────────

    @staticmethod
    def _to_tencent(symbol: str) -> str:
        """600519.SH → sh600519 | 000001.SZ → sz000001"""
        parts = symbol.split(".")
        if len(parts) != 2:
            return symbol.lower()
        return f"{parts[1].lower()}{parts[0]}"

    @staticmethod
    def _to_em_secid(symbol: str) -> str:
        """600519.SH → 1.600519 | 000001.SZ → 0.000001"""
        parts = symbol.split(".")
        if len(parts) != 2:
            return symbol
        mid = "1" if parts[1].upper() == "SH" else "0"
        return f"{mid}.{parts[0]}"

    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """Normalize user input to CODE.EXCHANGE (e.g. 301399 → 301399.SZ)."""
        s = (symbol or "").strip().upper()
        if not s:
            return s
        if "." in s:
            code, exch = s.split(".", 1)
            if exch in ("SH", "SZ", "BJ") and code.isdigit():
                return f"{code}.{exch}"
            return s
        if s.isdigit() and len(s) == 6:
            return cls._em_code_to_symbol(s)
        return s

    # ── Cache helpers ────────────────────────────────────────────

    def _cache_get(self, key: str, ttl_key: str = "quote"):
        return self._cache.get(key, self._cache_ttl.get(ttl_key, 10))

    def _cache_set(self, key: str, data):
        self._cache.set(key, data)

    # ── Public API ───────────────────────────────────────────────

    def get_realtime_quote(self, symbol: str) -> dict:
        """Get real-time quote — Tencent first, East Money fallback."""
        q = self._fetch_tencent_quote(symbol)
        if q is None:
            q = self._fetch_em_quote(symbol)
        if q is None:
            raise RuntimeError(f"Failed to fetch real-time quote for {symbol}")
        q["data_source"] = "realtime"
        return q

<<<<<<< HEAD
    def batch_get_quotes(self, symbols: list, max_batch: int = 50) -> dict:
        """Batch-fetch real-time quotes for multiple symbols.

        Uses Tencent's batch API (supports ~50 symbols per request).
        Returns a dict mapping symbol -> quote dict (or empty dict on failure).

        This avoids N sequential HTTP requests when fetching quotes for
        multiple positions/symbols at once.
        """
        if not symbols:
            return {}

        all_quotes = {}
        batch_size = max_batch

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            tcodes = [self._to_tencent(s) for s in batch]
            url = f"http://qt.gtimg.cn/q={','.join(tcodes)}"
            try:
                self._rate_limit()
                resp = self.http.get(url)
                for line in resp.text.strip().split("\n"):
                    if "=" not in line or "pv_none" in line:
                        continue
                    # Extract the tcode from the line (format: v_tcode="...")
                    eq_pos = line.index("=")
                    v_prefix = line[:eq_pos]
                    tcode = v_prefix[2:] if v_prefix.startswith("v_") else v_prefix
                    raw = line[eq_pos + 1:].strip().strip('"').strip(";")
=======
    def get_realtime_quotes_batch(self, symbols: list) -> dict:
        """Batch realtime quotes via Tencent (up to ~50/request).

        Returns {symbol: quote_dict}. Missing symbols are omitted.
        """
        out: dict = {}
        clean = []
        seen = set()
        for s in symbols or []:
            if not s or s in seen:
                continue
            seen.add(s)
            clean.append(s)
        if not clean:
            return out

        batch_size = 50
        for i in range(0, len(clean), batch_size):
            batch = clean[i : i + batch_size]
            tcodes = [self._to_tencent(c) for c in batch]
            url = f"https://qt.gtimg.cn/q={','.join(tcodes)}"
            try:
                resp = self._http_get(url)
                text = resp.text or ""
                for line in text.strip().split("\n"):
                    if "=" not in line or "pv_none" in line:
                        continue
                    left, right = line.split("=", 1)
                    tcode = left.strip().lstrip("v_")  # sz000001 / sh600519
                    sym = self._tencent_code_to_symbol(tcode)
                    if "." not in sym:
                        # Fallback: map by bare code against requested batch
                        bare = sym
                        for req in batch:
                            if req.split(".")[0] == bare:
                                sym = req
                                break
                    raw = right.strip().strip('"').strip(";")
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
                    fields = raw.split("~")
                    if len(fields) < 35:
                        continue
                    try:
                        name = fields[1]
<<<<<<< HEAD
                        raw_code = fields[2]
                        price = float(fields[3]) if fields[3] else 0
                        pre_close = float(fields[4]) if fields[4] else 0
                        open_price = float(fields[5]) if fields[5] else 0
                        volume = int(float(fields[6])) if fields[6] else 0
                        high = float(fields[33]) if len(fields) > 33 and fields[33] else price
                        low = float(fields[34]) if len(fields) > 34 and fields[34] else price
                        change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close else 0
                        amount = round(volume * price / 1e8, 2)

                        # Map back to standard symbol format
                        if raw_code.startswith(("6", "68")):
                            sym = f"{raw_code}.SH"
                        else:
                            sym = f"{raw_code}.SZ"

                        all_quotes[sym] = {
                            "symbol": sym,
                            "name": name,
                            "current_price": price,
                            "open": round(open_price, 2),
                            "high": round(high, 2),
                            "low": round(low, 2),
                            "pre_close": round(pre_close, 2),
                            "change": round(price - pre_close, 2),
                            "change_pct": change_pct,
                            "volume": volume,
                            "amount": amount,
                            "data_source": "realtime",
                        }
                    except (ValueError, IndexError):
                        continue
            except Exception as e:
                print(f"[DataEngine] Batch quote error: {e}")
                # Continue to next batch on error

        return all_quotes
=======
                        price = float(fields[3]) if fields[3] else 0.0
                        pre_close = float(fields[4]) if fields[4] else 0.0
                        open_p = float(fields[5]) if fields[5] else 0.0
                        volume = int(float(fields[6])) if fields[6] else 0
                        change_pct = (
                            round((price - pre_close) / pre_close * 100, 2)
                            if pre_close
                            else 0.0
                        )
                        quote = {
                            "symbol": sym,
                            "name": name,
                            "current_price": price,
                            "open": open_p,
                            "pre_close": pre_close,
                            "change_pct": change_pct,
                            "volume": volume,
                            "data_source": "realtime",
                        }
                        out[sym] = quote
                        self._cache_set(f"qt_{sym}", quote)
                    except (ValueError, TypeError, IndexError):
                        continue
            except Exception as e:
                print(f"[DataEngine] batch quote error: {e}")
            if i + batch_size < len(clean):
                time.sleep(0.05)
        return out
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

    def get_kline_data(self, symbol: str, period: str = "1d", count: int = 100) -> list:
        """Get K-line data from East Money."""
        kl = self._fetch_em_kline(symbol, period, count)
        if kl is None:
            raise RuntimeError(f"Failed to fetch K-line for {symbol}")
        return kl

    def get_history_data(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get historical daily data from real market APIs. Never synthesizes OHLC."""
        df = self._fetch_em_history(symbol, start_date, end_date)
        if df is not None and not df.empty:
            return df
<<<<<<< HEAD
        # API failed — generate mock data so backtesting still works
        print(f"[DataEngine] Falling back to mock data for {symbol} ({start_date} ~ {end_date})")
        return self._generate_mock_history(symbol, start_date, end_date)

    def generate_fallback_quote(self, symbol: str) -> dict | None:
        """Generate simulated real-time quote when external APIs are unreachable."""
        import random
        # Use a local Random instance to avoid corrupting the global random state
        rng = random.Random(hash(symbol) % (2**31))
        # Look up the stock name from cache
        name = symbol
        for s in self._symbols:
            if s["code"] == symbol:
                name = s["name"]
                break

        base_price = 10.0 + rng.random() * 90  # 10-100
        volatility = 0.02
        change_pct = round((rng.random() - 0.48) * 6, 2)  # -3% ~ +3%
        current_price = round(base_price * (1 + change_pct / 100), 2)
        pre_close = round(current_price / (1 + change_pct / 100), 2)
        high = round(max(current_price, pre_close) * (1 + rng.random() * 0.02), 2)
        low = round(min(current_price, pre_close) * (1 - rng.random() * 0.02), 2)
        volume = int(5_000_000 + rng.random() * 45_000_000)

        return {
            "symbol": symbol,
            "name": name,
            "current_price": current_price,
            "open": round(pre_close * (1 + (random.random() - 0.5) * 0.01), 2),
            "high": high,
            "low": low,
            "pre_close": pre_close,
            "change": round(current_price - pre_close, 2),
            "change_pct": change_pct,
            "volume": volume,
            "amount": round(volume * current_price / 1e8, 2),
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def generate_fallback_kline(self, symbol: str, period: str = "1d", count: int = 100) -> list | None:
        """Generate simulated K-line data when external APIs are unreachable."""
        import random
        # Use a local Random instance to avoid corrupting the global random state
        rng = random.Random(hash(symbol) % (2**31))

        base_price = 10.0 + rng.random() * 90
        drift = 0.0002 + rng.random() * 0.0003
        volatility = 0.015 + rng.random() * 0.015

        prices = [base_price]
        for _ in range(count):
            prices.append(prices[-1] * (1 + drift + volatility * (rng.random() * 2 - 1)))

        klines = []
        today = datetime.datetime.now()
        for i in range(count):
            close = round(prices[i + 1], 2)
            if period == "1d":
                delta = datetime.timedelta(days=count - i)
                date_str = (today - delta).strftime("%Y-%m-%d")
            elif period == "1w":
                delta = datetime.timedelta(weeks=count - i)
                date_str = (today - delta).strftime("%Y-%m-%d")
            else:
                # For minute periods, space evenly and include time
                delta = datetime.timedelta(minutes=(count - i) * 30)
                date_str = (today - delta).strftime("%Y-%m-%d %H:%M")
            vol_factor = 1.0 + (rng.random() - 0.5) * 3
            open_p = round(close * (1 + (rng.random() - 0.5) * 0.02), 2)
            high = round(max(open_p, close) * (1 + rng.random() * 0.015), 2)
            low = round(min(open_p, close) * (1 - rng.random() * 0.015), 2)
            volume = int(5_000_000 + rng.random() * 45_000_000 * vol_factor)
            klines.append({
                "date": date_str,
                "open": open_p,
                "close": close,
                "high": high,
                "low": low,
                "volume": volume,
            })
        # Sort chronologically (oldest first) for K-line chart
        klines.sort(key=lambda x: x["date"])
        return klines

    @staticmethod
    def _generate_mock_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Generate simulated historical data when real API is unavailable."""
        import random
        # Use a local Random instance to avoid corrupting the global random state
        rng = random.Random(hash(symbol) % (2**31))

        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        if end > datetime.datetime.now():
            end = datetime.datetime.now()

        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # skip weekends
                dates.append(current.strftime("%Y-%m-%d"))
            current += datetime.timedelta(days=1)

        n = len(dates)
        if n == 0:
            return pd.DataFrame()

        # Generate a realistic random-walk price series
        base_price = 10.0 + rng.random() * 90  # 10-100 initial
        drift = 0.0002 + rng.random() * 0.0003  # slight upward bias
        volatility = 0.015 + rng.random() * 0.015  # 1.5%-3% daily vol

        returns = [drift + volatility * (rng.random() * 2 - 1) for _ in range(n)]
        prices = [base_price]
        for r in returns[1:]:
            prices.append(prices[-1] * (1 + r))

        rows = []
        for i, d in enumerate(dates):
            close = round(prices[i], 2)
            vol_factor = 1.0 + (rng.random() - 0.5) * 3
            open_p = round(close * (1 + (rng.random() - 0.5) * 0.02), 2)
            high = round(max(open_p, close) * (1 + rng.random() * 0.015), 2)
            low = round(min(open_p, close) * (1 - rng.random() * 0.015), 2)
            volume = int(5_000_000 + rng.random() * 45_000_000 * vol_factor)
            rows.append({
                "date": d, "open": open_p, "close": close,
                "high": high, "low": low, "volume": volume,
            })
        return pd.DataFrame(rows)
=======
        print(f"[DataEngine] No history for {symbol} ({start_date} ~ {end_date}); returning empty")
        return pd.DataFrame()
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

    def get_market_overview(self) -> dict:
        """Get market index overview from Tencent Finance."""
        indices = self._fetch_real_indices()
        if indices is None:
            raise RuntimeError("Failed to fetch market indices")
        # Append calculated average stock price as a reference indicator
        avg_price = self._calculate_avg_stock_price()
        if avg_price:
            indices.append(avg_price)
        return {
            "indices": indices,
            "updated_at": datetime.datetime.now().isoformat(),
            "data_source": "realtime",
        }

    def _calculate_avg_stock_price(self) -> dict | None:
        """Calculate the average stock price of a representative A-share sample.

        Samples ~100 stocks spread across boards, batch-queries their quotes,
        and returns the simple average price + average change percentage.
        """
        cache_key = "avg_stock_price"
        cached = self._cache_get(cache_key, "index")
        if cached:
            return cached

        try:
            self.ensure_symbol_list()
        except Exception as e:
            print(f"[DataEngine] Avg price skipped (no real list): {e}")
            return None

        # Build a representative sample: pick stocks spread across boards
        boards = {"main": [], "star": [], "chinext": [], "bse": []}
        for s in self._symbols:
            b = self._market_board(s["code"])
            if b in boards and len(boards[b]) < 30:
                boards[b].append(s)
        sample = boards["main"] + boards["star"] + boards["chinext"] + boards["bse"]
        if len(sample) < 20:
            # Fallback: just use first 100 symbols from real list
            sample = self._symbols[:100]
        if not sample:
            return None

        # Batch query via Tencent (max ~50 symbols per request)
        all_prices = []
        all_changes = []
        batch_size = 50

        for i in range(0, min(len(sample), 120), batch_size):
            batch = sample[i:i + batch_size]
            tcodes = [self._to_tencent(s["code"]) for s in batch]
            url = f"https://qt.gtimg.cn/q={','.join(tcodes)}"
            try:
                resp = self._http_get(url)
                # Parse each v_tcode="..." line
                for line in resp.text.strip().split("\n"):
                    if "=" not in line or "pv_none" in line:
                        continue
                    raw = line.split("=", 1)[1].strip().strip('"').strip(";")
                    fields = raw.split("~")
                    if len(fields) < 35:
                        continue
                    try:
                        price = float(fields[3]) if fields[3] else 0
                        pre_close = float(fields[4]) if fields[4] else 0
                        if price > 0 and pre_close > 0:
                            all_prices.append(price)
                            all_changes.append(round((price - pre_close) / pre_close * 100, 2))
                    except (ValueError, IndexError):
                        continue
            except Exception as e:
                print(f"[DataEngine] Avg price batch error: {e}")
                continue
            # _http_get already rate-limits; no extra sleep between batches

        if len(all_prices) < 10:
            return None

        avg_price = round(sum(all_prices) / len(all_prices), 2)
        avg_change = round(sum(all_changes) / len(all_changes), 2)

        result = {
            "name": "平均股价",
            "code": "AVG.SZ",
            "price": avg_price,
            "change_pct": avg_change,
        }
        self._cache_set(cache_key, result)
        return result

    def search_symbols(self, query: str = "") -> list:
        """Search tradeable symbols — cached list + live Tencent for exact codes."""
        try:
            self.ensure_symbol_list(min_count=40)
        except Exception as e:
            print(f"[DataEngine] search_symbols list unavailable: {e}")

        if not query:
            if self._symbols:
                return self._symbols[:200]
            return self._liquid_seed_symbols()[:80]

        q = query.upper().strip()
        results = [
            s for s in self._symbols
            if q in s["code"].upper()
            or q in s.get("name", "")
            or q in s["code"].upper().replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
        ]

        # If query looks like a 6-digit stock code and not in cache, try live Tencent lookup
        if not results and q.isdigit() and len(q) == 6:
            live = self._lookup_tencent_stock(q)
            if live:
                results = [live]

        return results[:200]

    def _lookup_tencent_stock(self, code: str) -> dict | None:
        """Verify a 6-digit stock code via live Tencent quote. Returns {code, name, type} or None."""
        # Determine tentative exchange suffix for Tencent format
        if code.startswith(("6", "68")):
            tcode = f"sh{code}"
            symbol = f"{code}.SH"
        else:
            tcode = f"sz{code}"
            symbol = f"{code}.SZ"

        try:
            resp = self._http_get(f"https://qt.gtimg.cn/q={tcode}")
            text = resp.text.strip()
            if "=" not in text or "pv_none" in text:
                # Try the other exchange
                alt_tcode = f"sz{code}" if tcode.startswith("sh") else f"sh{code}"
                alt_symbol = f"{code}.SZ" if symbol.endswith(".SH") else f"{code}.SH"
                resp2 = self._http_get(f"https://qt.gtimg.cn/q={alt_tcode}")
                text2 = resp2.text.strip()
                if "=" in text2 and "pv_none" not in text2:
                    tcode, symbol = alt_tcode, alt_symbol
                    text = text2
                else:
                    return None

            raw = text.split("=", 1)[1].strip().strip('"').strip(";")
            fields = raw.split("~")
            if len(fields) < 2:
                return None
            name = fields[1]
            if not name or name == " ":
                return None
            return {"code": symbol, "name": name, "type": "stock"}
        except Exception:
            return None

    def lookup_stock_name(self, symbol: str) -> str:
        """Get stock Chinese name. Checks cache first, then live Tencent quote."""
        # Check cached symbol list
        for s in self._symbols:
            if s["code"] == symbol:
                return s["name"]
        # Check builtin name cache
        bare = symbol.replace(".SZ", "").replace(".SH", "")
        for s in self._symbols:
            if s["code"].replace(".SZ", "").replace(".SH", "") == bare:
                return s["name"]
        # Live Tencent lookup
        live = self._lookup_tencent_stock(bare)
        if live:
            return live.get("name", symbol)
        return symbol

    def get_sectors(self, count: int = 30) -> list:
        """Fetch mainstream industry sector data.

        Prefer Tencent board flow; fall back to Sina industry nodes when Tencent
        returns too few / empty (common when bk payload shrinks).
        """
        cache_key = f"sectors_{count}"
        cached = self._cache_get(cache_key, "sector")
        if cached:
            return cached

        combined = self._fetch_tencent_sectors(count)
        if len(combined) < 10:
            print(
                f"[DataEngine] Tencent sectors thin ({len(combined)}); "
                "falling back to Sina industries"
            )
            sina = self._fetch_sina_sectors(count)
            if len(sina) > len(combined):
                combined = sina

        if combined:
            self._cache_set(cache_key, combined)
        return combined

    def _fetch_tencent_sectors(self, count: int = 30) -> list:
        """Tencent fund-flow plate list (may only return a handful of boards)."""
        urls = (
            f"https://proxy.finance.qq.com/ifzqgtimg/appstock/app/board/index?board=bk&p=1&ps={max(count, 30)}",
            f"https://web.ifzq.gtimg.cn/appstock/app/board/index?board=bk&p=1&ps={max(count, 30)}",
        )
        last_err = None
        for url in urls:
            try:
                resp = self._http_get(url, headers={"Referer": "https://gu.qq.com/"}, retries=2)
                data = resp.json()
                if data.get("code") != 0:
                    print(f"[DataEngine] Sectors API error: code={data.get('code')}")
                    continue

                plate = data.get("data", {}).get("fundflow", {}).get("plate", {})
                top_list = plate.get("top", []) or []
                bottom_list = plate.get("bottom", []) or []

                seen = set()
                combined = []
                for item in top_list + bottom_list:
                    code = item.get("code", "")
                    if not code or code in seen:
                        continue
                    seen.add(code)

                    lzg = item.get("lzg", {}) or {}
                    zgb = item.get("zgb", "/")
                    parts = zgb.split("/") if zgb else ["0", "0"]
                    up_count = int(parts[0]) if parts[0].isdigit() else 0
                    total_count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    lead_code = str(lzg.get("code") or "")
                    if lead_code and "." not in lead_code:
                        lead_code = self._from_tencent_code(lead_code)

                    combined.append({
                        "code": code,
                        "name": item.get("name", ""),
                        "change_pct": round(float(item.get("zdf", 0) or 0), 2),
                        "leading_stock": lzg.get("name", ""),
                        "leading_stock_code": lead_code,
                        "leading_stock_change_pct": round(float(lzg.get("zdf", 0) or 0), 2),
                        "up_count": up_count,
                        "total_count": total_count,
                        "source": "tencent",
                    })

                combined.sort(key=lambda x: x["change_pct"], reverse=True)
                return combined[:count]
            except Exception as e:
                last_err = e
                continue
        if last_err:
            print(f"[DataEngine] Tencent sectors fetch error: {last_err}")
        return []

    def _sina_industry_nodes(self) -> list[tuple[str, str]]:
        """Return [(name, node_code), ...] from Sina Market_Center.getHQNodes."""
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "Market_Center.getHQNodes"
        )
        try:
            resp = self._http_get(
                url,
                headers={**_DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"},
                retries=2,
            )
            nodes = resp.json()
        except Exception as e:
            print(f"[DataEngine] Sina industry nodes failed: {e}")
            return []

        out: list[tuple[str, str]] = []

        def walk(node):
            if isinstance(node, list):
                if (
                    len(node) >= 3
                    and isinstance(node[0], str)
                    and isinstance(node[2], str)
                    and str(node[2]).startswith("new_")
                ):
                    out.append((node[0], node[2]))
                for child in node:
                    walk(child)

        walk(nodes)
        return out

    def _fetch_sina_sector_snapshot(self, name: str, node: str) -> dict | None:
        """One Sina industry: avg change of top page + leading gainer."""
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "Market_Center.getHQNodeData"
            f"?page=1&num=40&sort=changepercent&asc=0&node={node}"
        )
        try:
            resp = self._http_get(
                url,
                headers={**_DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"},
                retries=2,
            )
            rows = resp.json()
        except Exception:
            return None
        if not isinstance(rows, list) or not rows:
            return None

        changes = []
        up = 0
        for row in rows:
            try:
                chg = float(row.get("changepercent") or 0)
            except (TypeError, ValueError):
                continue
            changes.append(chg)
            if chg > 0:
                up += 1
        if not changes:
            return None

        lead = rows[0]
        lead_code = str(lead.get("code") or "")
        lead_sym = str(lead.get("symbol") or "").lower()
        if lead_sym.startswith("sh"):
            lead_full = f"{lead_code}.SH"
        elif lead_sym.startswith("sz"):
            lead_full = f"{lead_code}.SZ"
        elif lead_sym.startswith("bj"):
            lead_full = f"{lead_code}.BJ"
        else:
            lead_full = self._em_code_to_symbol(lead_code) if lead_code else ""

        avg = sum(changes) / len(changes)
        return {
            "code": node,
            "name": name,
            "change_pct": round(avg, 2),
            "leading_stock": lead.get("name") or "",
            "leading_stock_code": lead_full,
            "leading_stock_change_pct": round(float(lead.get("changepercent") or 0), 2),
            "up_count": up,
            "total_count": len(rows),
            "source": "sina",
        }

    def _fetch_sina_sectors(self, count: int = 30) -> list:
        """Build sector list from Sina 新浪行业 nodes (parallel snapshots)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        nodes = self._sina_industry_nodes()
        if not nodes:
            return []

        results: list = []
        # Cap workers to avoid hammering Sina
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {
                pool.submit(self._fetch_sina_sector_snapshot, name, node): node
                for name, node in nodes
            }
            for fut in as_completed(futs):
                try:
                    snap = fut.result()
                except Exception:
                    snap = None
                if snap:
                    results.append(snap)

        results.sort(key=lambda x: x["change_pct"], reverse=True)
        return results[:count]

    # ── Industry / Sector Stocks ────────────────────────────────────

    def _build_industry_map(self) -> dict[str, list[str]]:
        """Build a mapping from East Money industry name → list of stock codes.

        Fetches all A-share stocks with their industry classification (f100 field)
        from East Money and caches the result in memory for the session lifetime.
        Returns dict like:
        {"化学制药": ["000001.SZ", "000002.SZ", ...], ...}
        """
        if self._industry_map:
            return self._industry_map

<<<<<<< HEAD
        industry_map: dict[str, list[str]] = {}
        page_size = 500  # Larger page size → fewer HTTP requests (~11 vs ~28)
        max_pages = 15
=======
        with self._industry_map_lock:
            if self._industry_map:
                return self._industry_map

            industry_map: dict[str, list[str]] = {}
            page_size = 100  # smaller pages = less disconnect risk
            max_pages = 60
            failed_pages: list[int] = []
            prev_interval = self._min_interval
            self._min_interval = 0.45  # gentler on East Money during bulk crawl
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

            try:
<<<<<<< HEAD
                # East Money is more generous with rate limits — use 0.1s for bulk ops
                self._rate_limit(min_interval=0.1)
                resp = self.http.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://quote.eastmoney.com/",
                }, timeout=10)
                data = resp.json()
                items = data.get("data", {}).get("diff", [])
                if not items:
                    break
=======
                for page in range(1, max_pages + 1):
                    path = (
                        f"/api/qt/clist/get"
                        f"?pn={page}&pz={page_size}&po=1&np=1&fltt=2&invt=2"
                        f"&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
                        f"&fields=f12,f100"
                    )
                    data = None
                    last_err = None
                    for attempt in range(3):
                        try:
                            data = self._em_get_json(path, retries=2)
                            break
                        except Exception as e:
                            last_err = e
                            time.sleep(0.6 * (attempt + 1))
                    if data is None:
                        print(f"[DataEngine] Industry map page {page} failed: {last_err}")
                        failed_pages.append(page)
                        continue
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

                    items = data.get("data", {}).get("diff", [])
                    if not items:
                        break

                    for item in items:
                        code = str(item.get("f12", ""))
                        industry = str(item.get("f100", "")).strip()
                        if code and industry and len(code) == 6:
                            symbol = self._em_code_to_symbol(code)
                            industry_map.setdefault(industry, []).append(symbol)

                    total = data.get("data", {}).get("total", 0)
                    if page * page_size >= total:
                        break
            finally:
                self._min_interval = prev_interval

            stock_count = sum(len(v) for v in industry_map.values())
            # Only cache when reasonably complete; otherwise next call will rebuild
            if stock_count >= 2000 and len(failed_pages) <= 3:
                self._industry_map = industry_map
                print(
                    f"[DataEngine] Industry map built: {len(industry_map)} industries, "
                    f"{stock_count} stocks"
                    + (f" (skipped pages: {failed_pages})" if failed_pages else "")
                )
            elif industry_map:
                print(
                    f"[DataEngine] Industry map incomplete "
                    f"({stock_count} stocks, failed pages {failed_pages}); not caching"
                )
            else:
                print("[DataEngine] Industry map empty after crawl")
            return industry_map

    @staticmethod
    def _match_industry(sector_name: str, industry_names: list[str]) -> str | None:
        """Match a Tencent sector name to an East Money industry name.

        Uses exact match first, then substring matching.
        Returns the best-matching industry name or None.
        """
        if not sector_name:
            return None

        # Remove common suffixes for better matching
        clean_name = sector_name.strip()
        for suffix in ["Ⅱ", "Ⅲ", "2", "3"]:
            if clean_name.endswith(suffix):
                clean_name = clean_name[:-len(suffix)].strip()

        # Exact match
        if clean_name in industry_names:
            return clean_name

        # Substring match: sector name contained in industry name or vice versa
        for ind in industry_names:
            if clean_name in ind or ind in clean_name:
                return ind

        # Partial word matching: check if any 2-char segment matches
        if len(clean_name) >= 2:
            for ind in industry_names:
                for i in range(len(clean_name) - 1):
                    seg = clean_name[i:i+2]
                    if seg in ind:
                        return ind

        return None

<<<<<<< HEAD
    def _build_sina_industry_map(self) -> dict[str, str]:
        """Build Sina Finance industry name → node code map (fallback data source)."""
        if hasattr(self, "_sina_industry_map") and self._sina_industry_map:
            return self._sina_industry_map

        import json

        industry_map: dict[str, str] = {}
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "Market_Center.getHQNodes"
        )
        try:
            self._rate_limit(min_interval=0.2)
            resp = self.http.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://finance.sina.com.cn/",
            }, timeout=15)
            data = json.loads(resp.text)

            def walk(node):
                if not isinstance(node, list):
                    return
                if (
                    len(node) >= 3
                    and isinstance(node[0], str)
                    and isinstance(node[2], str)
                    and node[2].startswith("new_")
                ):
                    industry_map[node[0]] = node[2]
                for child in node:
                    walk(child)

            walk(data)
            if industry_map:
                self._sina_industry_map = industry_map
                print(f"[DataEngine] Sina industry map built: {len(industry_map)} industries")
        except Exception as e:
            print(f"[DataEngine] Sina industry map failed: {e}")

        return industry_map

    @staticmethod
    def _sina_symbol_to_code(sina_symbol: str) -> str:
        """Convert Sina symbol (e.g. sh600519) to 600519.SH."""
        sym = (sina_symbol or "").lower()
        if sym.startswith("sh") and len(sym) >= 8:
            return f"{sym[2:]}.SH"
        if sym.startswith("sz") and len(sym) >= 8:
            return f"{sym[2:]}.SZ"
        if sym.startswith("bj") and len(sym) >= 8:
            return f"{sym[2:]}.BJ"
        return sina_symbol

    def _fetch_sina_industry_stocks(self, node: str, count: int = 100) -> list:
        """Fetch constituent stocks for a Sina industry node with basic quote fields."""
        stocks: list[dict] = []
        page = 1
        page_size = 80

        while len(stocks) < count:
            url = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                f"Market_Center.getHQNodeData?page={page}&num={page_size}"
                f"&sort=changepercent&asc=0&node={node}"
            )
            try:
                self._rate_limit(min_interval=0.2)
                resp = self.http.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://finance.sina.com.cn/",
                }, timeout=15)
                items = resp.json()
                if not items:
=======
    @staticmethod
    def _from_tencent_code(tcode: str) -> str:
        """sh600519 → 600519.SH | sz000001 → 000001.SZ"""
        t = (tcode or "").strip().lower()
        if t.startswith("sh") and len(t) >= 8:
            return f"{t[2:]}.SH"
        if t.startswith("sz") and len(t) >= 8:
            return f"{t[2:]}.SZ"
        if t.startswith("bj") and len(t) >= 8:
            return f"{t[2:]}.BJ"
        return tcode

    def _fetch_tencent_board_stocks(self, board_code: str, count: int = 100) -> list:
        """Fetch sector constituents from Tencent board rank API (stable)."""
        code = (board_code or "").strip()
        if code.startswith("bkpt"):
            code = code[2:]
        if not code:
            return []

        page_size = min(max(int(count), 1), 100)
        url = (
            "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"
            f"?board_code={code}&_appver=11.17.0&offset=0&count={page_size}"
            f"&sort_type=volume&direct=down"
        )
        try:
            resp = self._http_get(url, headers={"Referer": "https://gu.qq.com/"}, retries=2)
            payload = resp.json()
            if payload.get("code") != 0:
                print(f"[DataEngine] Board stocks API error: {payload.get('msg')}")
                return []
            rows = (payload.get("data") or {}).get("rank_list") or []
            stocks = []
            for item in rows:
                symbol = self._from_tencent_code(str(item.get("code") or ""))
                if not symbol or "." not in symbol:
                    continue
                try:
                    price = float(item.get("zxj") or 0)
                    change_pct = float(item.get("zdf") or 0)
                    volume = int(float(item.get("volume") or 0))
                    amount_raw = float(item.get("turnover") or 0)
                except (TypeError, ValueError):
                    continue
                pre_close = round(price / (1 + change_pct / 100), 2) if change_pct != -100 else price
                stocks.append({
                    "code": symbol,
                    "name": item.get("name") or "",
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                    "amount": round(amount_raw / 10000.0, 2) if amount_raw > 10000 else amount_raw,
                    "high": round(price, 2),
                    "low": round(price, 2),
                    "open": round(price, 2),
                    "pre_close": pre_close,
                })
            stocks.sort(key=lambda x: x["change_pct"], reverse=True)
            return stocks[:count]
        except Exception as e:
            print(f"[DataEngine] Board stocks fetch error ({code}): {e}")
            return []

    def _fetch_sina_board_stocks(self, node: str, count: int = 100) -> list:
        """Fetch constituents for a Sina industry node (new_xxx)."""
        node = (node or "").strip()
        if not node.startswith("new_"):
            return []
        stocks = []
        page = 1
        page_size = 80
        while len(stocks) < count and page <= 5:
            url = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                "Market_Center.getHQNodeData"
                f"?page={page}&num={page_size}&sort=changepercent&asc=0&node={node}"
            )
            try:
                resp = self._http_get(
                    url,
                    headers={**_DEFAULT_HEADERS, "Referer": "https://finance.sina.com.cn/"},
                    retries=2,
                )
                rows = resp.json()
            except Exception as e:
                print(f"[DataEngine] Sina board stocks page {page} failed: {e}")
                break
            if not isinstance(rows, list) or not rows:
                break
            for row in rows:
                code = str(row.get("code") or "").strip()
                name = str(row.get("name") or "").strip()
                sym_raw = str(row.get("symbol") or "").strip().lower()
                if not code or len(code) != 6:
                    continue
                if sym_raw.startswith("sh"):
                    symbol = f"{code}.SH"
                elif sym_raw.startswith("sz"):
                    symbol = f"{code}.SZ"
                elif sym_raw.startswith("bj"):
                    symbol = f"{code}.BJ"
                else:
                    symbol = self._em_code_to_symbol(code)
                try:
                    price = float(row.get("trade") or 0)
                    change_pct = float(row.get("changepercent") or 0)
                    volume = int(float(row.get("volume") or 0))
                    amount = float(row.get("amount") or 0)
                    high = float(row.get("high") or price)
                    low = float(row.get("low") or price)
                    open_p = float(row.get("open") or price)
                    pre_close = float(row.get("settlement") or 0)
                except (TypeError, ValueError):
                    continue
                stocks.append({
                    "code": symbol,
                    "name": name,
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                    "amount": round(amount / 1e8, 2) if amount > 1e6 else round(amount, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "open": round(open_p, 2),
                    "pre_close": round(pre_close, 2),
                })
                if len(stocks) >= count:
                    break
            page += 1
            time.sleep(0.08)
        stocks.sort(key=lambda x: x["change_pct"], reverse=True)
        return stocks[:count]

    def get_sector_stocks(self, board_code: str, count: int = 100) -> list:
        """Fetch constituent stocks for a given sector/board code.

        Primary: Tencent board rank / Sina industry node.
        Fallback: East Money industry-name map + batch quotes.
        """
        cache_key = f"sector_stocks_{board_code}_{count}"
        cached = self._cache_get(cache_key, "sector")
        if cached:
            return cached

        code = (board_code or "").strip()
        if code.startswith("new_"):
            stocks = self._fetch_sina_board_stocks(code, count)
        else:
            stocks = self._fetch_tencent_board_stocks(code, count)
        if stocks:
            self._cache_set(cache_key, stocks)
            return stocks

        # Fallback — sector name → East Money industry map
        sector_name = None
        try:
            for s in self.get_sectors(100):
                if s.get("code") == board_code:
                    sector_name = s.get("name", "")
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
                    break

                for item in items:
                    code = self._sina_symbol_to_code(str(item.get("symbol", "")))
                    if not code or len(code) < 9:
                        continue
                    try:
                        price = float(item.get("trade") or 0)
                    except (TypeError, ValueError):
                        price = 0.0
                    try:
                        change_pct = float(item.get("changepercent") or 0)
                    except (TypeError, ValueError):
                        change_pct = 0.0
                    pre_close = round(price / (1 + change_pct / 100), 2) if price and change_pct else price

<<<<<<< HEAD
                    stocks.append({
                        "code": code,
                        "name": str(item.get("name", "")),
                        "price": round(price, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": 0,
                        "amount": 0.0,
                        "high": round(price, 2),
                        "low": round(price, 2),
                        "open": round(price, 2),
                        "pre_close": pre_close,
                    })
                    if len(stocks) >= count:
                        break
=======
        industry_map = self._build_industry_map()
        if not industry_map:
            print("[DataEngine] Industry map is empty, cannot get sector stocks")
            return []
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

                if len(items) < page_size:
                    break
                page += 1
            except Exception as e:
                print(f"[DataEngine] Sina node stocks page {page} failed: {e}")
                break

        stocks.sort(key=lambda x: x["change_pct"], reverse=True)
        return stocks[:count]

<<<<<<< HEAD
    def _batch_tencent_quotes(self, stock_codes: list) -> list:
        """Batch-fetch real-time quotes from Tencent for a list of stock codes."""
        stocks = []
        batch_size = 50
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]
            tcodes = [self._to_tencent(c) for c in batch]
            url = f"http://qt.gtimg.cn/q={','.join(tcodes)}"
            try:
                self._rate_limit()
                resp = self.http.get(url)
                for line in resp.text.strip().split("\n"):
                    if "=" not in line or "pv_none" in line:
                        continue
                    raw = line.split("=", 1)[1].strip().strip('"').strip(";")
                    fields = raw.split("~")
                    if len(fields) < 35:
                        continue
                    try:
                        name = fields[1]
                        raw_code = fields[2]
                        price = float(fields[3]) if fields[3] else 0
                        pre_close = float(fields[4]) if fields[4] else 0
                        open_price = float(fields[5]) if fields[5] else 0
                        volume = int(float(fields[6])) if fields[6] else 0
                        high = float(fields[33]) if len(fields) > 33 and fields[33] else price
                        low = float(fields[34]) if len(fields) > 34 and fields[34] else price
                        change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close else 0
                        amount = round(volume * price / 1e8, 2)

                        if raw_code.startswith(("6", "68")):
                            symbol = f"{raw_code}.SH"
                        else:
                            symbol = f"{raw_code}.SZ"

                        stocks.append({
                            "code": symbol,
                            "name": name,
                            "price": round(price, 2),
                            "change_pct": change_pct,
                            "volume": volume,
                            "amount": amount,
                            "high": round(high, 2),
                            "low": round(low, 2),
                            "open": round(open_price, 2),
                            "pre_close": round(pre_close, 2),
                        })
                    except (ValueError, IndexError, TypeError):
                        continue
            except Exception as e:
                print(f"[DataEngine] Batch quote error for sector stocks: {e}")
                continue
            time.sleep(0.3)

        stocks.sort(key=lambda x: x["change_pct"], reverse=True)
        return stocks

    def _fetch_sector_stocks_by_name(self, sector_name: str, count: int) -> list:
        """Fetch sector constituent stocks via East Money, with Sina fallback."""
        industry_map = self._build_industry_map()
        if industry_map:
            matched = self._match_industry(sector_name, list(industry_map.keys()))
            if matched:
                codes = industry_map.get(matched, [])[:count]
                if codes:
                    stocks = self._batch_tencent_quotes(codes)
                    if stocks:
                        return stocks

        sina_map = self._build_sina_industry_map()
        if sina_map:
            matched = self._match_industry(sector_name, list(sina_map.keys()))
            if matched:
                stocks = self._fetch_sina_industry_stocks(sina_map[matched], count)
                if stocks:
                    print(f"[DataEngine] Sector stocks via Sina: {sector_name} → {matched}")
                    return stocks

        print(f"[DataEngine] No stocks resolved for sector: {sector_name}")
        return []

    def get_sector_stocks(
        self, board_code: str, count: int = 100, sector_name: str | None = None
    ) -> list:
        """Fetch constituent stocks for a given sector/board code.

        Uses East Money industry classification (Sina Finance as fallback) to find
        stocks in the sector, then batches real-time quotes from Tencent when possible.

        Args:
            board_code: The board code (e.g. "pt01801084").
            count: Max stocks to return (default 100).
            sector_name: Optional sector display name (avoids extra lookup).

        Returns a list of stocks sorted by change_pct descending, each containing:
        {code, name, price, change_pct, volume, amount, high, low, open, pre_close}
        """
        cache_key = f"sector_stocks_{board_code}_{count}"
        cached = self._cache_get(cache_key, "index")
        if cached:
            return cached

        # Step 1: Resolve sector name
        if not sector_name:
            try:
                sectors = self.get_sectors(100)
                for s in sectors:
                    if s.get("code") == board_code:
                        sector_name = s.get("name", "")
                        break
            except Exception:
                pass

        if not sector_name:
            print(f"[DataEngine] Sector not found for board_code: {board_code}")
            return []

        stocks = self._fetch_sector_stocks_by_name(sector_name, count)
        self._cache_set(cache_key, stocks)
=======
        quotes = self.get_realtime_quotes_batch(stock_codes) or {}
        stocks = []
        for sym in stock_codes:
            q = quotes.get(sym)
            if not q:
                continue
            price = float(q.get("current_price") or 0)
            stocks.append({
                "code": sym,
                "name": q.get("name") or "",
                "price": round(price, 2),
                "change_pct": round(float(q.get("change_pct") or 0), 2),
                "volume": int(q.get("volume") or 0),
                "amount": float(q.get("amount") or 0),
                "high": round(float(q.get("high") or price), 2),
                "low": round(float(q.get("low") or price), 2),
                "open": round(float(q.get("open") or price), 2),
                "pre_close": round(float(q.get("pre_close") or 0), 2),
            })
        stocks.sort(key=lambda x: x["change_pct"], reverse=True)
        if stocks:
            self._cache_set(cache_key, stocks)
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
        return stocks

    # ═══════════════════════════════════════════════════════════════
    # Top Movers
    # ═══════════════════════════════════════════════════════════════

    def get_top_movers(self, count: int = 10, market: str = "all") -> dict:
        """Fetch top gainers and losers by batch-querying Tencent quotes and sorting.

        Args:
            count: Number of gainers/losers to return.
            market: Board filter — 'all', 'main', 'star', 'chinext', 'bse'.

        Returns dict with 'gainers' and 'losers' lists, each containing:
        {code, name, price, change_pct, market}
        """
        cache_key = f"top_movers_{market}_{count}"
        cached = self._cache_get(cache_key, "top_movers")
        if cached:
            return cached

        result = {"gainers": [], "losers": []}
        # Build pool: filter by market; expand to 500 for 'all' for better coverage
        pool = self._symbols[:500] if market == "all" else self._symbols
        if market != "all":
            pool = [s for s in pool if self._market_board(s["code"]) == market]
        if not pool:
            return result

        all_quotes = []
        batch_size = 50  # Tencent batch API handles ~50 symbols at once

        for i in range(0, min(len(pool), 300), batch_size):
            batch = pool[i:i + batch_size]
            tcodes = [self._to_tencent(s["code"]) for s in batch]
            url = f"https://qt.gtimg.cn/q={','.join(tcodes)}"
            try:
                resp = self._http_get(url)
                text = resp.text
                # Parse each line: v_tcode="...fields..."
                for line in text.strip().split("\n"):
                    if "=" not in line or line.startswith("v_pv_none"):
                        continue
                    raw = line.split("=", 1)[1].strip().strip('"').strip(";")
                    fields = raw.split("~")
                    if len(fields) < 33:
                        continue
                    try:
                        name = fields[1]
                        code_raw = fields[2]
                        price = float(fields[3]) if fields[3] else 0
                        pre_close = float(fields[4]) if fields[4] else 0
                        if price <= 0 or pre_close <= 0:
                            continue
                        change_pct = round((price - pre_close) / pre_close * 100, 2)
                        # Map back to standard code format
                        code = self._tencent_code_to_symbol(code_raw)
                        all_quotes.append({
                            "code": code, "name": name, "price": price,
                            "change_pct": change_pct,
                            "market": self._market_board(code),
                        })
                    except (ValueError, IndexError):
                        continue
            except Exception as e:
                print(f"[DataEngine] Top movers batch error: {e}")
                continue
            # _http_get already rate-limits; no extra sleep between batches

        if not all_quotes:
            return result

        # Filter outliers per board's daily limit
        valid_quotes = [q for q in all_quotes
                        if abs(q["change_pct"]) <= self._daily_limit(q["code"])]

        if not valid_quotes:
            valid_quotes = all_quotes  # fallback if all filtered

        sorted_quotes = sorted(valid_quotes, key=lambda x: x["change_pct"], reverse=True)
        gainers = [q for q in sorted_quotes if q["change_pct"] > 0]
        losers = [q for q in sorted_quotes if q["change_pct"] < 0]
        if len(losers) < count:
            losers = sorted([q for q in valid_quotes if q["change_pct"] <= 0],
                            key=lambda x: x["change_pct"])[:count]
        result["gainers"] = gainers[:count]
        result["losers"] = losers[:count] if losers else []

        self._cache_set(cache_key, result)
        return result

    @staticmethod
    def _market_board(code: str) -> str:
        """Classify stock by exchange board. Returns 'main'|'star'|'chinext'|'bse'|'other'."""
        raw = code.replace('.SZ', '').replace('.SH', '')
        if raw.startswith('688'): return 'star'
        if raw.startswith(('300', '301')): return 'chinext'
        if raw.startswith(('8', '4')) and len(raw) == 6: return 'bse'
        if raw.startswith(('60', '00', '001', '002', '003')): return 'main'
        return 'other'

    @staticmethod
    def _daily_limit(code: str) -> int:
        """Daily price limit: 主板=10%, 科创/创业=20%, 北交=30%."""
        board = DataEngine._market_board(code)
        return {'main': 10, 'star': 20, 'chinext': 20, 'bse': 30}.get(board, 10)

    @staticmethod
    def _tencent_code_to_symbol(code: str) -> str:
        """sh600519 → 600519.SH | sz000001 → 000001.SZ"""
        if code.startswith("sh"):
            return f"{code[2:]}.SH"
        elif code.startswith("sz"):
            return f"{code[2:]}.SZ"
        return code

    # ── Tencent Finance API ──────────────────────────────────────

    def _fetch_tencent_quote(self, symbol: str) -> Optional[dict]:
        """Fetch real-time quote from Tencent (qt.gtimg.cn)."""
        cache_key = f"qt_{symbol}"
        cached = self._cache_get(cache_key, "quote")
        if cached:
            return cached

        try:
            tcode = self._to_tencent(symbol)
            resp = self._http_get(f"https://qt.gtimg.cn/q={tcode}")
            text = resp.text.strip()

            if "=" not in text:
                print(f"[DataEngine] Unexpected Tencent response for {symbol}: {text[:100]}")
                return None
            raw = text.split("=", 1)[1].strip().strip('"').strip(';')
            fields = raw.split("~")
            if len(fields) < 35:
                print(f"[DataEngine] Insufficient fields for {symbol}: {len(fields)}")
                return None

            def f(i):
                return fields[i] if i < len(fields) else "0"

            name = f(1)
            current_price = float(f(3)) or 0
            pre_close = float(f(4)) or 0
            open_price = float(f(5)) or 0
            volume = int(float(f(6))) if f(6) else 0
            high = float(f(33)) or current_price
            low = float(f(34)) or current_price
            amount = round(volume * current_price / 1e8, 2)
            change = round(current_price - pre_close, 2)
            change_pct = round((current_price - pre_close) / pre_close * 100, 2) if pre_close else 0

            quote = {
                "symbol": symbol,
                "name": name,
                "current_price": current_price,
                "open": open_price,
                "high": high,
                "low": low,
                "pre_close": pre_close,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "amount": amount,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self._cache_set(cache_key, quote)
            return quote
        except Exception as e:
            print(f"[DataEngine] Tencent API error for {symbol}: {e}")
            return None

    def _fetch_em_quote(self, symbol: str) -> Optional[dict]:
        """East Money single-stock quote fallback (push2delay)."""
        cache_key = f"em_qt_{symbol}"
        cached = self._cache_get(cache_key, "quote")
        if cached:
            return cached
        bare = symbol.split(".")[0]
        market = "1" if symbol.endswith(".SH") or bare.startswith(("5", "6", "9")) else "0"
        path = (
            f"/api/qt/stock/get?secid={market}.{bare}"
            f"&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170"
        )
        try:
            data = self._em_get_json(path, retries=2)
            d = (data or {}).get("data") or {}
            if not d:
                return None
            # EM prices are often ×100 integers
            def px(key, default=0):
                v = d.get(key, default)
                try:
                    n = float(v)
                except (TypeError, ValueError):
                    return 0.0
                return n / 100.0 if abs(n) > 1000 or (n == int(n) and abs(n) >= 100) else n

            current = px("f43")
            pre_close = px("f60") or px("f46")
            if current <= 0 and pre_close <= 0:
                return None
            if current <= 0:
                current = pre_close
            open_p = px("f46") or current
            high = px("f44") or current
            low = px("f45") or current
            volume = int(float(d.get("f47") or 0))
            change = round(current - pre_close, 2) if pre_close else 0
            change_pct = round((current - pre_close) / pre_close * 100, 2) if pre_close else 0
            quote = {
                "symbol": symbol,
                "name": str(d.get("f58") or ""),
                "current_price": current,
                "open": open_p,
                "high": high,
                "low": low,
                "pre_close": pre_close,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "amount": round(float(d.get("f48") or 0) / 1e8, 2) if d.get("f48") else 0,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self._cache_set(cache_key, quote)
            return quote
        except Exception as e:
            print(f"[DataEngine] EM quote fallback error for {symbol}: {e}")
            return None

    def _fetch_real_indices(self) -> Optional[list]:
        """Fetch real market indices from Tencent."""
        targets = [
            ("sh000001", "上证指数", "000001.SH"),
            ("sz399001", "深证成指", "399001.SZ"),
            ("sz399006", "创业板指", "399006.SZ"),
            ("sh000688", "科创50", "000688.SH"),
        ]
        results = []
        ok = False
        for tcode, name, code in targets:
            try:
                resp = self._http_get(f"https://qt.gtimg.cn/q={tcode}")
                text = resp.text.strip()
                if "=" not in text:
                    print(f"[DataEngine] Unexpected index response for {tcode}: {text[:100]}")
                    continue
                raw = text.split("=", 1)[1].strip().strip('"').strip(';')
                fields = raw.split("~")
                price = float(fields[3]) if len(fields) > 3 and fields[3] else 0
                pre_close = float(fields[4]) if len(fields) > 4 and fields[4] else 0
                change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close else 0
                results.append({"name": name, "code": code, "price": price, "change_pct": change_pct})
                ok = True
            except Exception as e:
                print(f"[DataEngine] Index fetch error for {tcode} ({name}): {e}")
        return results if ok else None

    # ── Tencent K-line API (primary) ───────────────────────────────

    @staticmethod
    def _to_tencent_kline_code(symbol: str) -> str:
        """600519.SH → sh600519 | 000001.SZ → sz000001"""
        parts = symbol.split(".")
        if len(parts) != 2:
            return symbol.lower()
        return f"{parts[1].lower()}{parts[0]}"

    def _fetch_tencent_kline_payload(
        self, tcode: str, tperiod: str, count: int, adjust: str = "qfq"
    ) -> Optional[dict]:
        """Hit working Tencent K-line endpoints; return parsed stock/board node or None."""
        count = max(1, min(int(count), 640))
        # Board indices (pt*/bk*) often reject qfq — try plain day as well
        is_board = tcode.startswith(("pt", "bk"))
        adjust_opts = [adjust, ""] if is_board and adjust else [adjust]
        headers = {"Referer": "https://finance.qq.com/"}
        last_error = None

        for adj in adjust_opts:
            adj_part = adj if adj is not None else ""
            param = f"{tcode},{tperiod},,,{count},{adj_part}"
            for base in _TX_KLINE_ENDPOINTS:
                url = f"{base}?_var=kline_{tperiod}{adj_part or 'raw'}&param={param}"
                try:
                    resp = self._http_get(url, headers=headers, retries=1)
                    data = self._parse_tencent_payload(resp.text)
                    if not isinstance(data, dict):
                        raise RuntimeError("tencent payload not dict")
                    if data.get("code") != 0:
                        raise RuntimeError(f"tencent code={data.get('code')}")
                    raw_data = data.get("data")
                    if isinstance(raw_data, list) or not raw_data:
                        # param error / empty — try next adjust/endpoint
                        raise RuntimeError(data.get("msg") or "empty data")
                    stock = raw_data.get(tcode)
                    if isinstance(stock, dict) and (
                        stock.get(f"qfq{tperiod}")
                        or stock.get(tperiod)
                        or stock.get("qfqday")
                        or stock.get("day")
                    ):
                        return stock
                    raise RuntimeError("empty kline node")
                except Exception as e:
                    last_error = e
                    continue
        # Board misses are common with wrong codes — keep log short
        if last_error and not tcode.startswith(("pt", "bk")):
            print(f"[DataEngine] Tencent kline failed for {tcode}: {last_error}")
        return None

    def _fetch_tencent_kline(self, symbol: str, period: str, count: int) -> Optional[list]:
        """Fetch K-line data from Tencent Finance (primary source).

        Period mapping:
          '1d' → day, '1w' → week, '1m' → month
          '1m' minute not supported well; falls through to default
        """
        cache_key = f"kl_{symbol}_{period}_{count}"
        cached = self._cache_get(cache_key, "kline")
        if cached:
            return cached

        tcode = self._to_tencent_kline_code(symbol)
        period_map = {"1d": "day", "1w": "week", "1m": "month",
                      "30m": "m30", "60m": "m60", "5m": "m5", "15m": "m15"}
        tperiod = period_map.get(period, "day")

        stock_data = self._fetch_tencent_kline_payload(tcode, tperiod, count)
        if not stock_data:
            return None

        ktype = f"qfq{tperiod}"  # 前复权日K
        klines_raw = stock_data.get(ktype, [])
        if not klines_raw:
            klines_raw = stock_data.get(tperiod, [])
        if not klines_raw:
            print(f"[DataEngine] Tencent empty kline for {symbol}")
            return None

        klines = []
        for row in klines_raw:
            if len(row) >= 6:
                klines.append({
                    "date": str(row[0])[:10],
                    "open": round(float(row[1]), 2),
                    "close": round(float(row[2]), 2),
                    "high": round(float(row[3]), 2),
                    "low": round(float(row[4]), 2),
                    "volume": int(float(row[5])),
                })

        self._cache_set(cache_key, klines)
        return klines

    def _fetch_em_kline(self, symbol: str, period: str, count: int) -> Optional[list]:
        """Fetch K-line data — Tencent first, East Money fallback."""
        # Try Tencent first
        result = self._fetch_tencent_kline(symbol, period, count)
        if result:
            return result
        # Fallback: try East Money
        return self._fetch_em_kline_raw(symbol, period, count)

    def _fetch_em_kline_raw(self, symbol: str, period: str, count: int) -> Optional[list]:
        """East Money K-line fallback (with retry)."""
        # Reuse existing cache key (already checked by _fetch_tencent_kline)
        secid = self._to_em_secid(symbol)
        klt_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
                   "60m": "60", "1d": "101", "1w": "102"}
        klt = klt_map.get(period, "101")
        today_str = datetime.datetime.now().strftime("%Y%m%d")

        try:
            data = self._em_his_get_json(
                f"/api/qt/stock/kline/get"
                f"?secid={secid}&fields1=f1,f2,f3"
                f"&fields2=f51,f52,f53,f54,f55,f56,f57"
                f"&klt={klt}&fqt=1&end={today_str}&lmt={count}",
                retries=2,
            )
            klines_raw = (data.get("data") or {}).get("klines", [])
            if not klines_raw:
                return None
            klines = []
            for line in klines_raw:
                parts = line.split(",")
                if len(parts) >= 6:
                    klines.append({
                        "date": parts[0],
                        "open": round(float(parts[1]), 2),
                        "close": round(float(parts[2]), 2),
                        "high": round(float(parts[3]), 2),
                        "low": round(float(parts[4]), 2),
                        "volume": int(float(parts[5])),
                    })
            return klines
        except Exception as e:
            print(f"[DataEngine] EM kline failed for {symbol}: {e}")
            return None

    def _fetch_em_history(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch historical daily data — Tencent (proxy) first, East Money fallback."""
        cache_key = f"hist_{symbol}_{start_date}_{end_date}"
        cached = self._cache_get(cache_key, "history")
        if cached is not None:
            return cached if isinstance(cached, pd.DataFrame) else pd.DataFrame(cached)

        tcode = self._to_tencent_kline_code(symbol)
        try:
            sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            # Tencent returns the most recent N bars (not a calendar window).
            # Request enough bars to cover from start_date through today.
            days_back = max((datetime.datetime.now() - sd).days, (ed - sd).days, 1)
            count = min(640, max(120, int(days_back * 0.75) + 40))
        except Exception:
            count = 320

        stock_data = self._fetch_tencent_kline_payload(tcode, "day", count)
        if stock_data:
            klines_raw = stock_data.get("qfqday") or stock_data.get("day") or []
            rows = []
            for row in klines_raw:
                if len(row) >= 6:
                    ds = str(row[0])[:10]
                    if start_date <= ds <= end_date:
                        rows.append({
                            "date": ds,
                            "open": round(float(row[1]), 2),
                            "close": round(float(row[2]), 2),
                            "high": round(float(row[3]), 2),
                            "low": round(float(row[4]), 2),
                            "volume": int(float(row[5])),
                        })
            # Do NOT fall back to unfiltered recent bars — that silently
            # returns data outside [start_date, end_date] and breaks backtests.
            if rows:
                df = pd.DataFrame(rows)
                self._cache_set(cache_key, df.to_dict(orient="records"))
                return df

        # Fallback: East Money history hosts
        return self._fetch_em_history_raw(symbol, start_date, end_date)

    def _fetch_em_history_raw(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """East Money history fallback (multi-host)."""
        secid = self._to_em_secid(symbol)
        try:
            ed = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            end_str = ed.strftime("%Y%m%d")
            sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            days_back = max((ed - sd).days, 1)
            limit = min(640, max(120, int(days_back * 0.75) + 40))
        except Exception:
            end_str = datetime.datetime.now().strftime("%Y%m%d")
            limit = 640
        path = (
            f"/api/qt/stock/kline/get"
            f"?secid={secid}&fields1=f1,f2,f3"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57"
            f"&klt=101&fqt=1&end={end_str}&lmt={limit}"
        )

        try:
            data = self._em_his_get_json(path, retries=2)
            klines_raw = (data.get("data") or {}).get("klines", [])
            if not klines_raw:
                return None
            rows = []
            for line in klines_raw:
                parts = line.split(",")
                if len(parts) >= 6:
                    ds = parts[0][:10]
                    if start_date <= ds <= end_date:
                        rows.append({
                            "date": ds,
                            "open": round(float(parts[1]), 2),
                            "close": round(float(parts[2]), 2),
                            "high": round(float(parts[3]), 2),
                            "low": round(float(parts[4]), 2),
                            "volume": int(float(parts[5])),
                        })
            return pd.DataFrame(rows) if rows else None
        except Exception as e:
            print(f"[DataEngine] EM history failed for {symbol}: {e}")
            return None

    # ── Static symbol catalog ────────────────────────────────────

    # ── Stock symbol catalog ──────────────────────────────────────

    @staticmethod
    def _em_code_to_symbol(code: str) -> str:
        """Convert 6-digit East Money code to standard format.

        600519 → 600519.SH
        000001 → 000001.SZ
        300750 → 300750.SZ
        688981 → 688981.SH
        """
        code = code.strip()
        if len(code) != 6:
            return code
        if code.startswith(("6", "68")):
            return f"{code}.SH"
        return f"{code}.SZ"

    def _fetch_em_stock_list(self) -> list:
        """Fetch ALL A-share stocks from East Money API.

        Returns list of {"code": "000001.SZ", "name": "平安银行", "type": "stock"}
        """
        all_stocks = []
<<<<<<< HEAD
        page_size = 500  # Larger page → fewer HTTP requests
        max_pages = 15   # 500 * 15 = 7500, covers all ~5500 A-shares
=======
        page_size = 200
        max_pages = 30  # 200 * 30 = 6000, covers all ~5500 A-shares
        consecutive_failures = 0
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

        for page in range(1, max_pages + 1):
            path = (
                f"/api/qt/clist/get"
                f"?pn={page}&pz={page_size}&po=1&np=1&fltt=2&invt=2"
                f"&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
                f"&fields=f12,f14"
            )
            try:
<<<<<<< HEAD
                # East Money bulk loading — use faster rate limit
                self._rate_limit(min_interval=0.1)
                resp = self.http.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "http://quote.eastmoney.com/",
                }, timeout=10)
                data = resp.json()
=======
                data = self._em_get_json(path, retries=2)
                consecutive_failures = 0
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
                items = data.get("data", {}).get("diff", [])
                if not items:
                    break

                for item in items:
                    code = str(item.get("f12", ""))
                    name = str(item.get("f14", ""))
                    if code and name and len(code) == 6:
                        all_stocks.append({
                            "code": self._em_code_to_symbol(code),
                            "name": name,
                            "type": "stock",
                        })

                total = data.get("data", {}).get("total", 0)
                if page * page_size >= total:
                    break
            except Exception as e:
                consecutive_failures += 1
                print(f"[DataEngine] Stock list page {page} failed: {e}")
                if consecutive_failures >= 3 or page == 1:
                    break
                time.sleep(0.8 * consecutive_failures)
                continue

        return all_stocks

    def _fetch_sina_stock_list(
        self, max_pages: int = 80, stop_at: int | None = None
    ) -> list:
        """Fallback: Sina hs_a node pages (works when East Money clist disconnects)."""
        all_stocks: list = []
        seen: set[str] = set()
        headers = {
            **_DEFAULT_HEADERS,
            "Referer": "https://finance.sina.com.cn/",
        }
        for page in range(1, max_pages + 1):
            url = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                "Market_Center.getHQNodeData"
                f"?page={page}&num=80&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=page"
            )
            try:
                resp = self._http_get(url, headers=headers, retries=2)
                rows = resp.json()
            except Exception as e:
                print(f"[DataEngine] Sina stock list page {page} failed: {e}")
                if page == 1:
                    break
                time.sleep(0.5)
                continue
            if not isinstance(rows, list) or not rows:
                break
            for item in rows:
                code = str(item.get("code") or "").strip()
                name = str(item.get("name") or "").strip()
                sym_raw = str(item.get("symbol") or "").strip().lower()
                if not code or len(code) != 6 or not name:
                    continue
                if sym_raw.startswith("sh"):
                    symbol = f"{code}.SH"
                elif sym_raw.startswith("sz"):
                    symbol = f"{code}.SZ"
                elif sym_raw.startswith("bj"):
                    symbol = f"{code}.BJ"
                else:
                    symbol = self._em_code_to_symbol(code)
                if symbol in seen:
                    continue
                seen.add(symbol)
                all_stocks.append({"code": symbol, "name": name, "type": "stock"})
            if stop_at and len(all_stocks) >= stop_at:
                break
            time.sleep(0.12)
        return all_stocks

    def _liquid_seed_symbols(self) -> list:
        """Real liquid codes as last-resort sample (names filled via Tencent batch)."""
        quotes = {}
        try:
            quotes = self.get_realtime_quotes_batch(list(_LIQUID_SEED_CODES)) or {}
        except Exception:
            quotes = {}
        out = []
        for code in _LIQUID_SEED_CODES:
            q = quotes.get(code) or {}
            name = q.get("name") or code
            out.append({"code": code, "name": name, "type": "stock"})
        return out

    def _load_symbol_disk_cache(self) -> list:
        path = getattr(self, "_symbol_cache_path", "") or ""
        if not path or not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            rows = payload.get("symbols") if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                return []
            cleaned = []
            for s in rows:
                if not isinstance(s, dict):
                    continue
                code = s.get("code")
                name = s.get("name")
                if code and name:
                    cleaned.append({"code": code, "name": name, "type": "stock"})
            return cleaned
        except Exception as e:
            print(f"[DataEngine] disk symbol cache load failed: {e}")
            return []

    def _save_symbol_disk_cache(self, stocks: list) -> None:
        path = getattr(self, "_symbol_cache_path", "") or ""
        if not path or not stocks:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {
                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "count": len(stocks),
                "symbols": stocks,
            }
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[DataEngine] disk symbol cache save failed: {e}")

    def _set_symbols(self, stocks: list, source: str) -> list:
        with self._symbols_lock:
            self._symbols = list(stocks)
            self._symbols_source = source
        if source in ("eastmoney", "sina") and len(stocks) >= 100:
            self._save_symbol_disk_cache(stocks)
        return self._symbols

    def refresh_symbol_list(self) -> list:
        """Force refresh the symbol list (East Money → Sina → keep cache)."""
        stocks = self._fetch_em_stock_list()
        if stocks and len(stocks) > 100:
            print(f"[DataEngine] Symbol list refreshed: {len(stocks)} from East Money")
            return self._set_symbols(stocks, "eastmoney")

        sina = self._fetch_sina_stock_list()
        if sina and len(sina) > 100:
            print(f"[DataEngine] Symbol list refreshed: {len(sina)} from Sina")
            return self._set_symbols(sina, "sina")

        if self._symbols and len(self._symbols) >= 40:
            print(
                f"[DataEngine] Upstream list failed; keeping {len(self._symbols)} "
                f"cached symbols ({self._symbols_source})"
            )
            return self._symbols

        raise RuntimeError(
            f"股票列表刷新失败（东财 {len(stocks)} / 新浪 {len(sina)}），"
            "且无可用本地缓存"
        )

    def ensure_symbol_list(self, *, min_count: int = 100) -> list:
        """Ensure an A-share list is available (live or disk cache).

        Prefer East Money; fall back to Sina, then disk cache, then liquid seed.
        """
        if self._symbols and len(self._symbols) >= min_count:
            return self._symbols

        # Fresh fetch
        try:
            stocks = self._fetch_em_stock_list()
            if stocks and len(stocks) >= min_count:
                print(f"[DataEngine] Loaded {len(stocks)} A-share stocks from East Money")
                return self._set_symbols(stocks, "eastmoney")
        except Exception as e:
            print(f"[DataEngine] East Money stock list error: {e}")

        try:
            # Fast path: enough pages for search/avg-price; full refresh in background later
            sina = self._fetch_sina_stock_list(max_pages=20, stop_at=max(min_count, 800))
            if sina and len(sina) >= min_count:
                print(f"[DataEngine] Loaded {len(sina)} A-share stocks from Sina")
                result = self._set_symbols(sina, "sina")
                # Complete full list asynchronously when we only got a partial page set
                if len(sina) < 3000:
                    threading.Thread(
                        target=self._async_full_sina_refresh,
                        name="sina-full-list",
                        daemon=True,
                    ).start()
                return result
        except Exception as e:
            print(f"[DataEngine] Sina stock list error: {e}")

        disk = self._load_symbol_disk_cache()
        if disk and len(disk) >= min(min_count, 40):
            print(f"[DataEngine] Using disk cache: {len(disk)} symbols")
            return self._set_symbols(disk, "disk_cache")

        if self._symbols and len(self._symbols) >= 20:
            return self._symbols

        seed = self._liquid_seed_symbols()
        print(f"[DataEngine] Using liquid seed sample: {len(seed)} symbols")
        return self._set_symbols(seed, "liquid_seed")


    # ═══════════════════════════════════════════════════════════════
    # Average Stock Price K-line (for market environment analysis)
    # ═══════════════════════════════════════════════════════════════

    def get_avg_price_kline(self, count: int = 120) -> dict:
        """Real average-price K-line for market environment analysis.

        Prefer configured AVG_PRICE_SYMBOL (e.g. 通达信 880003) if the API returns it.
        Otherwise build a true cross-sectional average from a basket of real stock K-lines.
        Never scales an index with a fake default price.
        """
        cache_key = f"avg_price_kline_{count}"
        cached = self._cache_get(cache_key, "kline")
        if cached and isinstance(cached, dict) and cached.get("data"):
            return cached

        # 1) Try configured average-price index only when it is a real exchange code.
        # 通达信 880003 不是腾讯/东财个股代码，直接请求会报 param error。
        avg_sym = (settings.AVG_PRICE_SYMBOL or "").strip().upper()
        if "." in avg_sym and avg_sym.split(".", 1)[1] in ("SH", "SZ", "BJ"):
            try:
                kl = self._fetch_em_kline(avg_sym, "1d", count)
                if kl and len(kl) >= 20:
                    payload = {
                        "data": kl,
                        "data_source": "realtime",
                        "symbol": avg_sym,
                    }
                    self._cache_set(cache_key, payload)
                    return payload
            except Exception as e:
                print(f"[DataEngine] AVG_PRICE_SYMBOL {avg_sym} unavailable: {e}")
        elif avg_sym and not getattr(self, "_avg_price_skip_logged", False):
            print(
                f"[DataEngine] {avg_sym} 不是交易所代码，跳过行情接口，"
                "改用真实个股截面均价"
            )
            self._avg_price_skip_logged = True

        # 2) Cross-sectional mean of real stock OHLC (no index scaling)
        payload = self._build_cross_section_avg_kline(count)
        self._cache_set(cache_key, payload)
        return payload

    def _build_cross_section_avg_kline(self, count: int) -> dict:
        """Average OHLC across a board-balanced sample of real A-share K-lines."""
        sample: list[str] = []
        try:
            self.ensure_symbol_list(min_count=40)
            boards = {"main": [], "star": [], "chinext": [], "bse": []}
            for s in self._symbols:
                b = self._market_board(s["code"])
                if b in boards and len(boards[b]) < 12:
                    boards[b].append(s["code"])
            sample = boards["main"] + boards["star"] + boards["chinext"] + boards["bse"]
            if len(sample) < 20:
                sample = [s["code"] for s in self._symbols[:48]]
        except Exception as e:
            print(f"[DataEngine] symbol list for avg-price unavailable: {e}")

        if len(sample) < 10:
            sample = list(_LIQUID_SEED_CODES)
            print(f"[DataEngine] avg-price using liquid seed ({len(sample)} codes)")

        # date -> accumulators
        acc: dict[str, dict] = {}
        used = 0
        for code in sample[:48]:
            try:
                kl = self._fetch_em_kline(code, "1d", count)
            except Exception:
                kl = None
            if not kl:
                continue
            used += 1
            for bar in kl:
                d = bar.get("date")
                if not d:
                    continue
                bucket = acc.setdefault(
                    d,
                    {"open": 0.0, "close": 0.0, "high": 0.0, "low": 0.0, "volume": 0.0, "n": 0},
                )
                bucket["open"] += float(bar["open"])
                bucket["close"] += float(bar["close"])
                bucket["high"] += float(bar["high"])
                bucket["low"] += float(bar["low"])
                bucket["volume"] += float(bar.get("volume") or 0)
                bucket["n"] += 1
            time.sleep(0.15)

        if used < 8:
            raise RuntimeError(f"真实K线样本过少（{used}），拒绝生成平均股价序列")

        result = []
        for d in sorted(acc.keys()):
            b = acc[d]
            n = b["n"]
            if n < max(5, used // 4):
                continue
            result.append({
                "date": d,
                "open": round(b["open"] / n, 2),
                "close": round(b["close"] / n, 2),
                "high": round(b["high"] / n, 2),
                "low": round(b["low"] / n, 2),
                "volume": int(b["volume"] / n),
                "n": n,
            })

        if len(result) < 20:
            raise RuntimeError("截面平均股价交易日不足")

        # Drop incomplete tip bar: thin sample or absurd day move
        if len(result) >= 2:
            tip = result[-1]
            prev = result[-2]
            tip_n = int(tip.get("n") or 0)
            med_n = sorted(int(r.get("n") or 0) for r in result[:-1])[len(result) // 2]
            day_move = (
                tip["close"] / prev["close"] - 1.0
                if prev.get("close")
                else 0.0
            )
            if tip_n < max(5, int(med_n * 0.6)) or abs(day_move) > 0.05:
                result = result[:-1]

        # Strip helper field before return
        for r in result:
            r.pop("n", None)

        return {
            "data": result[-count:],
            "data_source": "realtime_cross_section",
            "sample_size": used,
        }

    # ── Stock insight (company + market + news) ─────────────────

    @staticmethod
    def _to_em_f10_code(symbol: str) -> str:
        """600519.SH → SH600519 | 000001.SZ → SZ000001"""
        parts = (symbol or "").upper().split(".")
        if len(parts) != 2:
            return (symbol or "").upper()
        return f"{parts[1]}{parts[0]}"

    def get_stock_insight(self, symbol: str) -> dict:
        """Aggregate company profile, enriched quote, and related news."""
        symbol = self.normalize_symbol(symbol)
        if not symbol:
            raise ValueError("股票代码无效")

        cache_key = f"insight_{symbol}"
        cached = self._cache_get(cache_key, "insight")
        if cached:
            return cached

        quote = {}
        try:
            quote = self.get_realtime_quote(symbol) or {}
        except Exception as e:
            print(f"[DataEngine] insight quote failed {symbol}: {e}")

        # Enrich with extra Tencent fields when possible
        market = self._enrich_market_snapshot(symbol, quote)

        company = self.get_company_profile(symbol)
        news = self.get_stock_news(symbol, limit=8)

        payload = {
            "symbol": symbol,
            "name": (
                company.get("name")
                or market.get("name")
                or quote.get("name")
                or self.lookup_stock_name(symbol)
            ),
            "company": company,
            "market": market,
            "news": news,
            "data_source": "realtime",
        }
        self._cache_set(cache_key, payload)
        return payload

    def _enrich_market_snapshot(self, symbol: str, quote: dict) -> dict:
        """Build market card from quote + optional extra Tencent fields."""
        base = {
            "symbol": symbol,
            "name": quote.get("name") or "",
            "current_price": float(quote.get("current_price") or 0),
            "open": float(quote.get("open") or 0),
            "high": float(quote.get("high") or 0),
            "low": float(quote.get("low") or 0),
            "pre_close": float(quote.get("pre_close") or 0),
            "change": float(quote.get("change") or 0),
            "change_pct": float(quote.get("change_pct") or 0),
            "volume": int(quote.get("volume") or 0),
            "amount": float(quote.get("amount") or 0),
            "pe": None,
            "pb": None,
            "turnover_rate": None,
            "amplitude": None,
            "limit_up": None,
            "limit_down": None,
            "total_market_cap": None,
            "circ_market_cap": None,
            "avg_price": None,
            "volume_ratio": None,
        }
        try:
            tcode = self._to_tencent(symbol)
            resp = self._http_get(f"https://qt.gtimg.cn/q={tcode}")
            text = resp.text.strip()
            if "=" not in text:
                return base
            raw = text.split("=", 1)[1].strip().strip('"').strip(";")
            fields = raw.split("~")

            def f(i, cast=float):
                if i >= len(fields) or fields[i] in ("", "-", None):
                    return None
                try:
                    return cast(fields[i])
                except (TypeError, ValueError):
                    return None

            if fields[1]:
                base["name"] = fields[1]
            # Common Tencent field map (best-effort; indexes vary by board)
            base["pe"] = f(39) or f(53)
            base["pb"] = f(46)
            base["turnover_rate"] = f(38)
            base["amplitude"] = f(43)
            base["limit_up"] = f(47)
            base["limit_down"] = f(48)
            base["total_market_cap"] = f(45)  # 亿元
            base["circ_market_cap"] = f(44)
            base["avg_price"] = f(51)
            base["volume_ratio"] = f(49)
        except Exception as e:
            print(f"[DataEngine] market enrich failed {symbol}: {e}")
        return base

    def get_company_profile(self, symbol: str) -> dict:
        """Company profile from East Money F10 CompanySurvey."""
        symbol = self.normalize_symbol(symbol)
        cache_key = f"company_{symbol}"
        cached = self._cache_get(cache_key, "company")
        if cached:
            return cached

        code = self._to_em_f10_code(symbol)
        url = (
            "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/"
            f"CompanySurveyAjax?code={code}"
        )
        profile = {
            "name": self.lookup_stock_name(symbol),
            "code": symbol,
            "industry": "",
            "region": "",
            "chairman": "",
            "secretary": "",
            "website": "",
            "employees": "",
            "list_date": "",
            "found_date": "",
            "main_business": "",
            "intro": "",
            "office": "",
        }
        try:
            resp = self.http.get(
                url,
                headers={
                    **_DEFAULT_HEADERS,
                    "Referer": "https://emweb.securities.eastmoney.com/",
                },
                timeout=12.0,
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            jb = data.get("jbzl") or data.get("Jbzl") or {}
            if isinstance(jb, dict) and jb:
                profile.update({
                    "name": jb.get("agjc") or jb.get("gsmc") or profile["name"],
                    "industry": jb.get("sshy") or jb.get("sshyName") or "",
                    "region": jb.get("ssdq") or jb.get("dq") or "",
                    "chairman": jb.get("fddbr") or jb.get("dsz") or "",
                    "secretary": jb.get("dm") or jb.get("ms") or "",
                    "website": jb.get("gswz") or jb.get("wz") or "",
                    "employees": str(jb.get("gyrs") or jb.get("zgrs") or ""),
                    "list_date": jb.get("ssrq") or "",
                    "found_date": jb.get("clrq") or "",
                    "main_business": jb.get("jyfw") or jb.get("zygcyw") or "",
                    "intro": jb.get("gsjj") or "",
                    "office": jb.get("bgdz") or jb.get("zcdz") or "",
                })
            self._cache_set(cache_key, profile)
        except Exception as e:
            print(f"[DataEngine] company profile failed {symbol}: {e}")
        return profile

    def get_stock_news(self, symbol: str, limit: int = 8) -> list:
        """Related news / notices for a stock (Tencent → East Money ann)."""
        symbol = self.normalize_symbol(symbol)
        cache_key = f"news_{symbol}_{limit}"
        cached = self._cache_get(cache_key, "news")
        if cached:
            return cached

        items = self._fetch_tencent_news(symbol, limit) or []
        if len(items) < 3:
            anns = self._fetch_em_announcements(symbol, limit)
            # Merge by title, prefer news first
            seen = {x.get("title") for x in items}
            for a in anns:
                if a.get("title") and a["title"] not in seen:
                    items.append(a)
                    seen.add(a["title"])
                if len(items) >= limit:
                    break

        items = items[:limit]
        self._cache_set(cache_key, items)
        return items

    def _fetch_tencent_news(self, symbol: str, limit: int = 8) -> list:
        tcode = self._to_tencent(symbol)
        urls = (
            f"https://proxy.finance.qq.com/ifzqgtimg/appstock/news/info/search"
            f"?symbol={tcode}&page=1&n={limit}&type=1",
            f"https://proxy.finance.qq.com/ifzqgtimg/appstock/news/info/search"
            f"?symbol={tcode}&page=1&n={limit}",
        )
        for url in urls:
            try:
                resp = self._http_get(url)
                data = resp.json()
                rows = (
                    (data.get("data") or {}).get("data")
                    or (data.get("data") or {}).get("news")
                    or data.get("data")
                    or []
                )
                if isinstance(rows, dict):
                    rows = rows.get("data") or rows.get("list") or []
                out = []
                for row in rows or []:
                    if not isinstance(row, dict):
                        continue
                    title = (row.get("title") or row.get("u_title") or "").strip()
                    if not title:
                        continue
                    out.append({
                        "title": re.sub(r"<[^>]+>", "", title),
                        "time": row.get("time") or row.get("u_time") or row.get("datetime") or "",
                        "source": row.get("source") or row.get("u_source") or "腾讯财经",
                        "url": row.get("url") or row.get("u_url") or row.get("jump_url") or "",
                        "type": "news",
                    })
                if out:
                    return out[:limit]
            except Exception as e:
                print(f"[DataEngine] tencent news failed {symbol}: {e}")
        return []

    def _fetch_em_announcements(self, symbol: str, limit: int = 8) -> list:
        bare = symbol.split(".")[0]
        url = (
            "https://np-anotice-stock.eastmoney.com/api/security/ann"
            f"?sr=-1&page_size={limit}&page_index=1&ann_type=A"
            f"&client_source=web&stock_list={bare}&f_node=0"
        )
        try:
            resp = self.http.get(
                url,
                headers={
                    **_DEFAULT_HEADERS,
                    "Referer": "https://data.eastmoney.com/",
                },
                timeout=12.0,
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            rows = (data.get("data") or {}).get("list") or data.get("list") or []
            out = []
            for row in rows:
                title = (row.get("title") or row.get("notice_title") or "").strip()
                if not title:
                    continue
                art_code = row.get("art_code") or row.get("info_code") or ""
                link = ""
                if art_code:
                    link = f"https://data.eastmoney.com/notices/detail/{bare}/{art_code}.html"
                out.append({
                    "title": title,
                    "time": row.get("notice_date") or row.get("display_time") or "",
                    "source": "东财公告",
                    "url": link,
                    "type": "announcement",
                })
            return out[:limit]
        except Exception as e:
            print(f"[DataEngine] em ann failed {symbol}: {e}")
            return []


from app.core.config import settings
data_engine = DataEngine(source=settings.MARKET_DATA_SOURCE)
