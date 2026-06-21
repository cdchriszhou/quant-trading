"""Data Engine: Market data fetching — supports simulated and real-time data sources."""

import random
import datetime
import time
from typing import Optional

import pandas as pd
import numpy as np

# httpx is optional — if not installed, simulated data is used as fallback
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class DataEngine:
    """Market data engine.
    - source = "simulated": generates fake data for demo/development.
    - source = "realtime": fetches real data from free Chinese stock APIs.
                         Falls back to simulated data on failure.
    """

    def __init__(self, source: str = "simulated"):
        self.source = source
        self._cache = {}
        self._cache_ttl = {
            "quote": 3,    # real-time quotes cached 3 seconds
            "kline": 60,   # kline data cached 60 seconds
            "index": 5,    # index data cached 5 seconds
        }
        self._last_request = 0.0
        self._min_interval = 0.3  # 300ms between API calls
        self._http_client = None

        self._symbols = self._build_symbol_list()
        self._prices = self._build_price_map()
        self._names = self._build_name_map()

    # ── HTTP client (lazy init) ────────────────────────────────────

    @property
    def http(self):
        if self._http_client is None and HAS_HTTPX:
            self._http_client = httpx.Client(timeout=8, verify=False)
        return self._http_client

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    # ── Symbol format conversion ───────────────────────────────────

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

    # ── Cache helpers ──────────────────────────────────────────────

    def _cache_get(self, key: str, ttl_key: str = "quote"):
        now = time.time()
        if key in self._cache:
            data, ts = self._cache[key]
            if now - ts < self._cache_ttl.get(ttl_key, 10):
                return data
        return None

    def _cache_set(self, key: str, data):
        self._cache[key] = (data, time.time())

    # ── Public API ─────────────────────────────────────────────────

    def get_realtime_quote(self, symbol: str) -> dict:
        """Get real-time quote. Tries real API first if source=realtime."""
        if self.source == "realtime":
            q = self._fetch_tencent_quote(symbol)
            if q:
                return q
        return self._simulate_quote(symbol)

    def get_kline_data(self, symbol: str, period: str = "1d", count: int = 100) -> list:
        """Get K-line data for charting."""
        if self.source == "realtime":
            kl = self._fetch_em_kline(symbol, period, count)
            if kl:
                return kl
        return self._simulate_kline(symbol, period, count)

    def get_history_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical price data for backtesting."""
        if self.source == "realtime":
            df = self._fetch_em_history(symbol, start_date, end_date)
            if not df.empty:
                return df
        return self._simulate_history(symbol, start_date, end_date)

    def get_market_overview(self) -> dict:
        """Get market overview with index data."""
        if self.source == "realtime":
            indices = self._fetch_real_indices()
            if indices:
                return {"indices": indices, "updated_at": datetime.datetime.now().isoformat()}
        return self._simulate_market_overview()

    def search_symbols(self, query: str = "") -> list:
        """Search tradeable symbols from built-in catalog."""
        if not query:
            return self._symbols
        q = query.upper().strip()
        return [s for s in self._symbols
                if q in s["code"].upper() or q in s["name"]
                or q in s["code"].upper().replace(".SZ", "").replace(".SH", "")]

    # ── Real-time: Tencent Finance API ─────────────────────────────

    def _fetch_tencent_quote(self, symbol: str) -> Optional[dict]:
        """Fetch real-time quote from Tencent Finance (qt.gtimg.cn)."""
        cache_key = f"qt_{symbol}"
        cached = self._cache_get(cache_key, "quote")
        if cached:
            return cached

        if not self.http:
            return None

        try:
            tcode = self._to_tencent(symbol)
            url = f"http://qt.gtimg.cn/q={tcode}"
            self._rate_limit()
            resp = self.http.get(url)
            text = resp.text.strip()

            # Parse: v_sh600519="1~name~code~price~...";
            if "=" not in text:
                return None
            raw = text.split("=", 1)[1].strip().strip('"').strip(';')
            fields = raw.split("~")
            if len(fields) < 35:
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

    def _fetch_real_indices(self) -> Optional[list]:
        """Fetch real market indices from Tencent."""
        if not self.http:
            return None
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
                url = f"http://qt.gtimg.cn/q={tcode}"
                self._rate_limit()
                resp = self.http.get(url)
                text = resp.text.strip()
                raw = text.split("=", 1)[1].strip().strip('"').strip(';')
                fields = raw.split("~")
                price = float(fields[3]) if len(fields) > 3 and fields[3] else 0
                pre_close = float(fields[4]) if len(fields) > 4 and fields[4] else 0
                change_pct = round((price - pre_close) / pre_close * 100, 2) if pre_close else 0
                results.append({"name": name, "code": code, "price": price, "change_pct": change_pct})
                ok = True
            except Exception:
                results.append(self._fallback_index(name, code))
        return results if ok else None

    def _fallback_index(self, name, code):
        return {"name": name, "code": code,
                "price": round(random.uniform(2000, 3500), 2),
                "change_pct": round(random.uniform(-2, 2), 2)}

    # ── Real-time: East Money K-line API ───────────────────────────

    def _fetch_em_kline(self, symbol: str, period: str, count: int) -> Optional[list]:
        """Fetch K-line from East Money API."""
        cache_key = f"kl_{symbol}_{period}_{count}"
        cached = self._cache_get(cache_key, "kline")
        if cached:
            return cached

        if not self.http:
            return None

        try:
            secid = self._to_em_secid(symbol)
            klt_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
                       "60m": "60", "1d": "101", "1w": "102"}
            klt = klt_map.get(period, "101")

            url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                   f"?secid={secid}&fields1=f1,f2,f3"
                   f"&fields2=f51,f52,f53,f54,f55,f56,f57"
                   f"&klt={klt}&fqt=1&end=20500101&lmt={count}")
            self._rate_limit()
            resp = self.http.get(url)
            data = resp.json()

            klines_raw = data.get("data", {}).get("klines", [])
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

            self._cache_set(cache_key, klines)
            return klines
        except Exception as e:
            print(f"[DataEngine] EM kline error for {symbol}: {e}")
            return None

    def _fetch_em_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch historical daily data from East Money."""
        if not self.http:
            return pd.DataFrame()
        try:
            secid = self._to_em_secid(symbol)
            url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                   f"?secid={secid}&fields1=f1,f2,f3"
                   f"&fields2=f51,f52,f53,f54,f55,f56,f57"
                   f"&klt=101&fqt=1&end=20500101&lmt=1000")
            self._rate_limit()
            resp = self.http.get(url)
            data = resp.json()
            klines_raw = data.get("data", {}).get("klines", [])
            rows = []
            for line in klines_raw:
                parts = line.split(",")
                if len(parts) >= 6:
                    ds = parts[0][:10]  # normalize date
                    if start_date <= ds <= end_date:
                        rows.append({
                            "date": ds,
                            "open": round(float(parts[1]), 2),
                            "close": round(float(parts[2]), 2),
                            "high": round(float(parts[3]), 2),
                            "low": round(float(parts[4]), 2),
                            "volume": int(float(parts[5])),
                        })
            return pd.DataFrame(rows)
        except Exception as e:
            print(f"[DataEngine] EM history error for {symbol}: {e}")
            return pd.DataFrame()

    # ── Simulated data methods (fallback / demo) ───────────────────

    def _simulate_market_overview(self):
        indices = [
            {"name": "上证指数", "code": "000001.SH", "price": round(3150 + random.uniform(-30, 30), 2),
             "change_pct": round(random.uniform(-1.5, 1.5), 2)},
            {"name": "深证成指", "code": "399001.SZ", "price": round(10500 + random.uniform(-100, 100), 2),
             "change_pct": round(random.uniform(-2, 2), 2)},
            {"name": "创业板指", "code": "399006.SZ", "price": round(2100 + random.uniform(-25, 25), 2),
             "change_pct": round(random.uniform(-2.5, 2.5), 2)},
            {"name": "科创50", "code": "000688.SH", "price": round(950 + random.uniform(-15, 15), 2),
             "change_pct": round(random.uniform(-2, 2), 2)},
        ]
        return {"indices": indices, "updated_at": datetime.datetime.now().isoformat()}

    def _simulate_quote(self, symbol: str) -> dict:
        base_price = self._get_base_price(symbol)
        change_pct = round(random.uniform(-3.0, 3.0), 2)
        current_price = round(base_price * (1 + change_pct / 100), 2)
        open_price = round(base_price * (1 + random.uniform(-0.5, 0.5) / 100), 2)
        high = round(max(current_price, open_price) * (1 + random.uniform(0, 1.0) / 100), 2)
        low = round(min(current_price, open_price) * (1 - random.uniform(0, 1.0) / 100), 2)
        volume = int(random.uniform(1000000, 50000000))
        amount = round(volume * current_price / 100000000, 2)
        return {
            "symbol": symbol,
            "name": self._get_symbol_name(symbol),
            "current_price": current_price, "open": open_price,
            "high": high, "low": low, "pre_close": base_price,
            "change": round(current_price - base_price, 2),
            "change_pct": change_pct, "volume": volume, "amount": amount,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def _simulate_kline(self, symbol: str, period: str, count: int) -> list:
        base_price = self._get_base_price(symbol)
        data = []
        price = base_price * 0.9
        now = datetime.datetime.now()
        for i in range(count):
            dt = now - datetime.timedelta(days=count - i)
            volatility = base_price * random.uniform(0.005, 0.03)
            open_p = price
            close_p = price + random.uniform(-volatility, volatility)
            high_p = max(open_p, close_p) + abs(random.uniform(0, volatility * 0.5))
            low_p = min(open_p, close_p) - abs(random.uniform(0, volatility * 0.5))
            volume = int(random.uniform(500000, 30000000))
            price = close_p
            data.append({
                "date": dt.strftime("%Y-%m-%d"), "open": round(open_p, 2),
                "high": round(high_p, 2), "low": round(low_p, 2),
                "close": round(close_p, 2), "volume": volume,
            })
        return data

    def _simulate_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        base_price = self._get_base_price(symbol)
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        dates = pd.date_range(start=start, end=end, freq="B")
        price = base_price * 0.85
        rows = []
        for dt in dates:
            volatility = base_price * random.uniform(0.003, 0.025)
            open_p = price
            close_p = price + random.uniform(-volatility, volatility)
            high_p = max(open_p, close_p) + abs(random.uniform(0, volatility * 0.5))
            low_p = min(open_p, close_p) - abs(random.uniform(0, volatility * 0.5))
            volume = int(random.uniform(500000, 30000000))
            price = close_p
            rows.append({
                "date": dt.strftime("%Y-%m-%d"), "open": round(open_p, 2),
                "high": round(high_p, 2), "low": round(low_p, 2),
                "close": round(close_p, 2), "volume": volume,
            })
        return pd.DataFrame(rows)

    def _get_base_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 30.0)

    def _get_symbol_name(self, symbol: str) -> str:
        return self._names.get(symbol, symbol)

    # ── Static data ────────────────────────────────────────────────

    def _build_symbol_list(self) -> list:
        return [
            {"code": "000001.SZ", "name": "平安银行", "type": "stock"},
            {"code": "000002.SZ", "name": "万科A", "type": "stock"},
            {"code": "000333.SZ", "name": "美的集团", "type": "stock"},
            {"code": "000538.SZ", "name": "云南白药", "type": "stock"},
            {"code": "000568.SZ", "name": "泸州老窖", "type": "stock"},
            {"code": "000651.SZ", "name": "格力电器", "type": "stock"},
            {"code": "000661.SZ", "name": "长春高新", "type": "stock"},
            {"code": "000858.SZ", "name": "五粮液", "type": "stock"},
            {"code": "000063.SZ", "name": "中兴通讯", "type": "stock"},
            {"code": "001979.SZ", "name": "招商蛇口", "type": "stock"},
            {"code": "002049.SZ", "name": "紫光国微", "type": "stock"},
            {"code": "002230.SZ", "name": "科大讯飞", "type": "stock"},
            {"code": "002352.SZ", "name": "顺丰控股", "type": "stock"},
            {"code": "002415.SZ", "name": "海康威视", "type": "stock"},
            {"code": "002460.SZ", "name": "赣锋锂业", "type": "stock"},
            {"code": "002466.SZ", "name": "天齐锂业", "type": "stock"},
            {"code": "002475.SZ", "name": "立讯精密", "type": "stock"},
            {"code": "002594.SZ", "name": "比亚迪", "type": "stock"},
            {"code": "002714.SZ", "name": "牧原股份", "type": "stock"},
            {"code": "300014.SZ", "name": "亿纬锂能", "type": "stock"},
            {"code": "300015.SZ", "name": "爱尔眼科", "type": "stock"},
            {"code": "300059.SZ", "name": "东方财富", "type": "stock"},
            {"code": "300124.SZ", "name": "汇川技术", "type": "stock"},
            {"code": "300274.SZ", "name": "阳光电源", "type": "stock"},
            {"code": "300750.SZ", "name": "宁德时代", "type": "stock"},
            {"code": "300760.SZ", "name": "迈瑞医疗", "type": "stock"},
            {"code": "600025.SH", "name": "华能水电", "type": "stock"},
            {"code": "600028.SH", "name": "中国石化", "type": "stock"},
            {"code": "600030.SH", "name": "中信证券", "type": "stock"},
            {"code": "600031.SH", "name": "三一重工", "type": "stock"},
            {"code": "600036.SH", "name": "招商银行", "type": "stock"},
            {"code": "600048.SH", "name": "保利发展", "type": "stock"},
            {"code": "600050.SH", "name": "中国联通", "type": "stock"},
            {"code": "600104.SH", "name": "上汽集团", "type": "stock"},
            {"code": "600196.SH", "name": "复星医药", "type": "stock"},
            {"code": "600276.SH", "name": "恒瑞医药", "type": "stock"},
            {"code": "600362.SH", "name": "江西铜业", "type": "stock"},
            {"code": "600436.SH", "name": "片仔癀", "type": "stock"},
            {"code": "600519.SH", "name": "贵州茅台", "type": "stock"},
            {"code": "600760.SH", "name": "中航沈飞", "type": "stock"},
            {"code": "600809.SH", "name": "山西汾酒", "type": "stock"},
            {"code": "600886.SH", "name": "国投电力", "type": "stock"},
            {"code": "600887.SH", "name": "伊利股份", "type": "stock"},
            {"code": "600893.SH", "name": "航发动力", "type": "stock"},
            {"code": "600900.SH", "name": "长江电力", "type": "stock"},
            {"code": "600941.SH", "name": "中国移动", "type": "stock"},
            {"code": "601012.SH", "name": "隆基绿能", "type": "stock"},
            {"code": "601127.SH", "name": "赛力斯", "type": "stock"},
            {"code": "601166.SH", "name": "兴业银行", "type": "stock"},
            {"code": "601318.SH", "name": "中国平安", "type": "stock"},
            {"code": "601390.SH", "name": "中国中铁", "type": "stock"},
            {"code": "601398.SH", "name": "工商银行", "type": "stock"},
            {"code": "601600.SH", "name": "中国铝业", "type": "stock"},
            {"code": "601628.SH", "name": "中国人寿", "type": "stock"},
            {"code": "601633.SH", "name": "长城汽车", "type": "stock"},
            {"code": "601668.SH", "name": "中国建筑", "type": "stock"},
            {"code": "601688.SH", "name": "华泰证券", "type": "stock"},
            {"code": "601728.SH", "name": "中国电信", "type": "stock"},
            {"code": "601857.SH", "name": "中国石油", "type": "stock"},
            {"code": "601888.SH", "name": "中国中免", "type": "stock"},
            {"code": "601899.SH", "name": "紫金矿业", "type": "stock"},
            {"code": "601939.SH", "name": "建设银行", "type": "stock"},
            {"code": "603259.SH", "name": "药明康德", "type": "stock"},
            {"code": "603288.SH", "name": "海天味业", "type": "stock"},
            {"code": "603501.SH", "name": "韦尔股份", "type": "stock"},
            {"code": "603993.SH", "name": "洛阳钼业", "type": "stock"},
            {"code": "688981.SH", "name": "中芯国际", "type": "stock"},
        ]

    def _build_price_map(self) -> dict:
        return {
            "000001.SZ": 12.5, "000002.SZ": 10.2, "000333.SZ": 65.8,
            "000538.SZ": 55.0, "000568.SZ": 185.0, "000651.SZ": 42.3,
            "000661.SZ": 125.0, "000858.SZ": 135.0, "000063.SZ": 32.0,
            "001979.SZ": 10.5, "002049.SZ": 95.0, "002230.SZ": 48.0,
            "002352.SZ": 42.0, "002415.SZ": 35.6, "002460.SZ": 52.0,
            "002466.SZ": 68.0, "002475.SZ": 28.9, "002594.SZ": 245.0,
            "002714.SZ": 48.0, "300014.SZ": 42.0, "300015.SZ": 15.5,
            "300059.SZ": 22.3, "300124.SZ": 62.0, "300274.SZ": 88.0,
            "300750.SZ": 180.0, "300760.SZ": 280.0, "600025.SH": 8.5,
            "600028.SH": 6.3, "600030.SH": 20.5, "600031.SH": 16.8,
            "600036.SH": 36.8, "600048.SH": 11.5, "600050.SH": 5.2,
            "600104.SH": 16.0, "600196.SH": 32.0, "600276.SH": 42.5,
            "600362.SH": 22.0, "600436.SH": 250.0, "600519.SH": 1680.0,
            "600760.SH": 42.0, "600809.SH": 260.0, "600886.SH": 14.5,
            "600887.SH": 28.6, "600893.SH": 38.0, "600900.SH": 25.4,
            "600941.SH": 105.0, "601012.SH": 18.7, "601127.SH": 82.0,
            "601166.SH": 18.2, "601318.SH": 42.8, "601390.SH": 6.5,
            "601398.SH": 5.6, "601600.SH": 8.2, "601628.SH": 35.0,
            "601633.SH": 28.0, "601668.SH": 5.5, "601688.SH": 16.0,
            "601728.SH": 6.0, "601857.SH": 8.5, "601888.SH": 75.0,
            "601899.SH": 16.5, "601939.SH": 7.5, "603259.SH": 55.0,
            "603288.SH": 38.0, "603501.SH": 88.0, "603993.SH": 7.5,
            "688981.SH": 55.0,
        }

    def _build_name_map(self) -> dict:
        return {
            "000001.SZ": "平安银行", "000002.SZ": "万科A", "000333.SZ": "美的集团",
            "000538.SZ": "云南白药", "000568.SZ": "泸州老窖", "000651.SZ": "格力电器",
            "000661.SZ": "长春高新", "000858.SZ": "五粮液", "000063.SZ": "中兴通讯",
            "001979.SZ": "招商蛇口", "002049.SZ": "紫光国微", "002230.SZ": "科大讯飞",
            "002352.SZ": "顺丰控股", "002415.SZ": "海康威视", "002460.SZ": "赣锋锂业",
            "002466.SZ": "天齐锂业", "002475.SZ": "立讯精密", "002594.SZ": "比亚迪",
            "002714.SZ": "牧原股份", "300014.SZ": "亿纬锂能", "300015.SZ": "爱尔眼科",
            "300059.SZ": "东方财富", "300124.SZ": "汇川技术", "300274.SZ": "阳光电源",
            "300750.SZ": "宁德时代", "300760.SZ": "迈瑞医疗", "600025.SH": "华能水电",
            "600028.SH": "中国石化", "600030.SH": "中信证券", "600031.SH": "三一重工",
            "600036.SH": "招商银行", "600048.SH": "保利发展", "600050.SH": "中国联通",
            "600104.SH": "上汽集团", "600196.SH": "复星医药", "600276.SH": "恒瑞医药",
            "600362.SH": "江西铜业", "600436.SH": "片仔癀", "600519.SH": "贵州茅台",
            "600760.SH": "中航沈飞", "600809.SH": "山西汾酒", "600886.SH": "国投电力",
            "600887.SH": "伊利股份", "600893.SH": "航发动力", "600900.SH": "长江电力",
            "600941.SH": "中国移动", "601012.SH": "隆基绿能", "601127.SH": "赛力斯",
            "601166.SH": "兴业银行", "601318.SH": "中国平安", "601390.SH": "中国中铁",
            "601398.SH": "工商银行", "601600.SH": "中国铝业", "601628.SH": "中国人寿",
            "601633.SH": "长城汽车", "601668.SH": "中国建筑", "601688.SH": "华泰证券",
            "601728.SH": "中国电信", "601857.SH": "中国石油", "601888.SH": "中国中免",
            "601899.SH": "紫金矿业", "601939.SH": "建设银行", "603259.SH": "药明康德",
            "603288.SH": "海天味业", "603501.SH": "韦尔股份", "603993.SH": "洛阳钼业",
            "688981.SH": "中芯国际",
        }


data_engine = DataEngine()
