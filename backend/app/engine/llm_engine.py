"""LLM client for DeepSeek / GLM / Kimi / Qwen (OpenAI-compatible chat APIs).

Used as an optional multi-model fusion layer on quantitative short-hold screening.
Never replaces hard K-line gates.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import httpx

from app.core.config import settings


_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "key_attr": "DEEPSEEK_API_KEY",
        "url_attr": "DEEPSEEK_BASE_URL",
        "model_attr": "DEEPSEEK_MODEL",
        "default_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "glm": {
        "name": "智谱 GLM",
        "key_attr": "GLM_API_KEY",
        "url_attr": "GLM_BASE_URL",
        "model_attr": "GLM_MODEL",
        "default_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "kimi": {
        "name": "Kimi",
        "key_attr": "KIMI_API_KEY",
        "url_attr": "KIMI_BASE_URL",
        "model_attr": "KIMI_MODEL",
        "default_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "qwen": {
        "name": "通义千问",
        "key_attr": "QWEN_API_KEY",
        "url_attr": "QWEN_BASE_URL",
        "model_attr": "QWEN_MODEL",
        "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
}

_BIAS_RANK = {"偏多": 0, "中性": 1, "谨慎": 2}


class LlmEngine:
    def resolve_provider(self, provider: Optional[str] = None) -> str:
        p = (provider or settings.LLM_DEFAULT_PROVIDER or "deepseek").strip().lower()
        return p if p in _PROVIDERS else "deepseek"

    def get_credentials(self, provider: Optional[str] = None) -> dict:
        pid = self.resolve_provider(provider)
        meta = _PROVIDERS[pid]
        api_key = (getattr(settings, meta["key_attr"], "") or "").strip()
        base_url = (getattr(settings, meta["url_attr"], "") or meta["default_url"]).rstrip("/")
        model = (getattr(settings, meta["model_attr"], "") or meta["default_model"]).strip()
        return {
            "id": pid,
            "name": meta["name"],
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "configured": bool(api_key),
        }

    def configured_providers(self) -> list[str]:
        return [pid for pid in _PROVIDERS if self.get_credentials(pid)["configured"]]

    def list_status(self) -> dict:
        from app.core.config import llm_provider_snapshot
        return llm_provider_snapshot(mask_keys=True)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider: Optional[str] = None,
        temperature: float = 0.3,
        timeout: float = 45.0,
    ) -> str:
        cred = self.get_credentials(provider)
        if not cred["configured"]:
            raise RuntimeError(f"{cred['name']} 未配置 API Key，请在系统管理 → 大模型接入 中填写")

        url = f"{cred['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {cred['api_key']}",
            "Content-Type": "application/json",
        }
        body = {
            "model": cred["model"],
            "messages": messages,
            "temperature": temperature,
        }
        with httpx.Client(timeout=timeout, verify=True) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("大模型未返回内容")
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        if not str(content).strip():
            raise RuntimeError("大模型返回空内容")
        return str(content).strip()

    def test_connection(self, provider: Optional[str] = None) -> dict:
        cred = self.get_credentials(provider)
        if not cred["configured"]:
            return {
                "ok": False,
                "provider": cred["id"],
                "name": cred["name"],
                "message": "未配置 API Key",
            }
        try:
            text = self.chat(
                [{"role": "user", "content": "请只回复：ok"}],
                provider=cred["id"],
                temperature=0,
                timeout=30.0,
            )
            return {
                "ok": True,
                "provider": cred["id"],
                "name": cred["name"],
                "model": cred["model"],
                "message": f"连接成功：{text[:80]}",
            }
        except Exception as e:
            return {
                "ok": False,
                "provider": cred["id"],
                "name": cred["name"],
                "model": cred["model"],
                "message": f"连接失败：{e}",
            }

    def enrich_recommendations(
        self,
        data: dict,
        *,
        provider: Optional[str] = None,
        providers: Optional[list[str]] = None,
    ) -> dict:
        """Multi-model fusion notes on quantitative recommendations.

        Calls selected configured providers in parallel, then majority-votes bias
        and merges notes. Does not change hard K-line filters.
        """
        rows = list(data.get("recommendations") or [])

        selected = self._normalize_provider_list(providers, provider)
        configured = [p for p in selected if self.get_credentials(p)["configured"]]
        missing = [p for p in selected if p not in configured]

        data["llm"] = {
            "enabled": True,
            "mode": "fusion",
            "requested": selected,
            "used": configured,
            "missing": missing,
            "provider_names": [self.get_credentials(p)["name"] for p in configured],
        }

        if not rows:
            data["llm"]["skipped"] = "无候选可参考"
            return data
        if not configured:
            data["llm"]["error"] = "未配置可用的大模型 API Key（请在系统管理 → 大模型接入）"
            return data

        payload = []
        for r in rows[:10]:
            payload.append({
                "symbol": r.get("symbol"),
                "name": r.get("name"),
                "score": r.get("score"),
                "price": r.get("price"),
                "stop_loss": r.get("stop_loss"),
                "take_profit": r.get("take_profit"),
                "risk_reward": r.get("risk_reward"),
                "ret_5d_pct": r.get("ret_5d_pct"),
                "strategy": (r.get("suggested_strategy") or {}).get("name"),
                "reasons": (r.get("reasons") or [])[:4],
            })

        system = (
            "你是A股短线辅助分析助手。下面是量化系统已筛选的候选（已通过趋势/回踩/量能/盈亏比门槛）。"
            "请仅作参考点评，不要编造未给出的财务数据，不要承诺收益。"
            "输出严格 JSON 对象，格式："
            '{"summary":"一句话总评","items":[{"symbol":"代码","note":"不超过40字点评","bias":"偏多|中性|谨慎"}]}'
            "items 必须覆盖输入的每一只股票。"
        )
        user = (
            f"大盘环境：{(data.get('market_env') or {}).get('env_state')}\n"
            f"持有天数提示：{data.get('hold_days_hint')}\n"
            f"候选列表：\n{json.dumps(payload, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        results_by_provider: dict[str, dict] = {}
        errors: list[str] = []

        def _run_one(pid: str) -> tuple[str, dict | None, str | None]:
            try:
                raw = self.chat(messages, provider=pid, temperature=0.2, timeout=55.0)
                return pid, self._parse_json_object(raw), None
            except Exception as e:
                return pid, None, str(e)

        with ThreadPoolExecutor(max_workers=min(4, len(configured))) as pool:
            futs = [pool.submit(_run_one, pid) for pid in configured]
            for fut in as_completed(futs):
                pid, parsed, err = fut.result()
                name = self.get_credentials(pid)["name"]
                if err or not parsed:
                    errors.append(f"{name}: {err or '空结果'}")
                else:
                    results_by_provider[pid] = parsed

        data["llm"]["errors"] = errors
        data["llm"]["ok_count"] = len(results_by_provider)
        if not results_by_provider:
            data["llm"]["error"] = "；".join(errors) or "全部大模型调用失败"
            return data

        # Fuse per-symbol votes
        for r in rows:
            sym = str(r.get("symbol") or "").upper()
            bare = sym.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            votes: list[str] = []
            notes: list[str] = []
            detail = []
            for pid, parsed in results_by_provider.items():
                hit = self._find_item(parsed.get("items") or [], sym, bare)
                if not hit:
                    continue
                bias = str(hit.get("bias") or "中性").strip()
                if bias not in _BIAS_RANK:
                    bias = "中性"
                note = str(hit.get("note") or "").strip()
                pname = self.get_credentials(pid)["name"]
                votes.append(bias)
                if note:
                    notes.append(f"{pname}:{note}")
                detail.append({"provider": pid, "name": pname, "bias": bias, "note": note})

            consensus = self._majority_bias(votes) if votes else "中性"
            fused_note = "；".join(notes[:4]) if notes else ""
            agree = votes.count(consensus)
            r["llm_bias"] = consensus
            r["llm_note"] = fused_note
            r["llm_votes"] = detail
            r["llm_agree"] = f"{agree}/{len(votes)}" if votes else "0/0"
            if fused_note:
                reasons = list(r.get("reasons") or [])
                reasons.insert(0, f"LLM融合（{consensus} {r['llm_agree']}）：{fused_note[:80]}")
                r["reasons"] = reasons[:6]

        rows.sort(
            key=lambda x: (
                -float(x.get("score") or 0),
                _BIAS_RANK.get(x.get("llm_bias") or "中性", 1),
            )
        )
        for i, r in enumerate(rows, 1):
            r["rank"] = i

        data["recommendations"] = rows
        summaries = []
        for pid, parsed in results_by_provider.items():
            s = str(parsed.get("summary") or "").strip()
            if s:
                summaries.append(f"{self.get_credentials(pid)['name']}：{s}")
        data["llm"]["summary"] = " ｜ ".join(summaries) if summaries else ""
        data["llm"]["provider"] = ",".join(results_by_provider.keys())
        data["llm"]["provider_name"] = " + ".join(
            self.get_credentials(p)["name"] for p in results_by_provider
        )
        if errors:
            data["llm"]["partial_error"] = "；".join(errors)
        data["disclaimer"] = (
            (data.get("disclaimer") or "")
            + " 多模型融合点评仅供参考，不改变量化硬过滤，不构成投资建议。"
        )
        return data

    def _normalize_provider_list(
        self,
        providers: Optional[list[str]],
        provider: Optional[str],
    ) -> list[str]:
        ids: list[str] = []
        if providers:
            for p in providers:
                pid = str(p or "").strip().lower()
                if pid in _PROVIDERS and pid not in ids:
                    ids.append(pid)
        elif provider:
            # comma-separated single query param still supported
            for part in str(provider).split(","):
                pid = part.strip().lower()
                if pid in _PROVIDERS and pid not in ids:
                    ids.append(pid)
        if not ids:
            ids = self.configured_providers()
        return ids

    @staticmethod
    def _find_item(items: list, sym: str, bare: str) -> dict:
        for item in items:
            s = str(item.get("symbol") or "").upper()
            b = s.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            if s == sym or b == bare or s == bare or b == sym:
                return item
        return {}

    @staticmethod
    def _majority_bias(votes: list[str]) -> str:
        if not votes:
            return "中性"
        counts = {k: 0 for k in _BIAS_RANK}
        for v in votes:
            counts[v] = counts.get(v, 0) + 1
        # Prefer cautious when tied between 偏多 and 谨慎
        ordered = sorted(
            counts.items(),
            key=lambda kv: (-kv[1], {"谨慎": 0, "中性": 1, "偏多": 2}.get(kv[0], 9)),
        )
        return ordered[0][0]

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise RuntimeError("无法解析大模型 JSON")
        obj = json.loads(m.group(0))
        if not isinstance(obj, dict):
            raise RuntimeError("大模型 JSON 格式不正确")
        return obj


llm_engine = LlmEngine()
