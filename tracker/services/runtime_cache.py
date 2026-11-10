"""앱 인스턴스별 메모리 캐시를 담당한다."""
import hashlib
import time
from datetime import datetime
from threading import Lock

from tracker.services.performance_metrics import increment_metric

AI_RESPONSE_CACHE_TTL = 6 * 60 * 60
AI_RESPONSE_CACHE_MAX_ENTRIES = 100
RUNTIME_CACHE_MAX_ENTRIES = 1000


class RuntimeCache:
    """일반 API 캐시와 성공한 AI 응답 캐시를 앱 단위로 보유한다."""

    def __init__(self):
        self.cache = {}
        self.ai_response_cache = {}
        self.lock = Lock()

    def get_ai_response(self, prompt):
        cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        with self.lock:
            item = self.ai_response_cache.get(cache_key)
            if not item:
                return None
            now = time.time()
            if now - item["cached_at"] > AI_RESPONSE_CACHE_TTL:
                self.ai_response_cache.pop(cache_key, None)
                return None
            item["used_at"] = now
            return item["analysis"]

    def set_ai_response(self, prompt, analysis):
        if not analysis:
            return
        now = time.time()
        cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        with self.lock:
            self.ai_response_cache[cache_key] = {
                "analysis": analysis,
                "cached_at": now,
                "used_at": now,
            }
            while len(self.ai_response_cache) > AI_RESPONSE_CACHE_MAX_ENTRIES:
                oldest_key = min(
                    self.ai_response_cache,
                    key=lambda key: self.ai_response_cache[key]["used_at"],
                )
                self.ai_response_cache.pop(oldest_key, None)

    def get(self, key):
        namespace = str(key).split(":", 1)[0]
        with self.lock:
            item = self.cache.get(key)
            if not item:
                increment_metric("cache.lookups", cache=namespace, result="miss")
                return None
            now = time.time()
            if now - item["time"] > item["ttl"]:
                del self.cache[key]
                increment_metric("cache.lookups", cache=namespace, result="miss")
                return None
            item["used_at"] = now
            increment_metric("cache.lookups", cache=namespace, result="hit")
            return item["data"]

    def delete(self, key):
        with self.lock:
            return self.cache.pop(key, None) is not None

    def set(self, key, data, ttl):
        now = time.time()
        with self.lock:
            if len(self.cache) >= RUNTIME_CACHE_MAX_ENTRIES:
                for existing_key, item in list(self.cache.items()):
                    if now - item["time"] > item["ttl"]:
                        self.cache.pop(existing_key, None)
            self.cache[key] = {
                "time": now,
                "used_at": now,
                "data": data,
                "ttl": ttl,
                "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            while len(self.cache) > RUNTIME_CACHE_MAX_ENTRIES:
                oldest_key = min(
                    self.cache,
                    key=lambda cache_key: self.cache[cache_key]["used_at"],
                )
                self.cache.pop(oldest_key, None)
        increment_metric("cache.writes", cache=str(key).split(":", 1)[0])

    def get_timestamp(self, key):
        with self.lock:
            item = self.cache.get(key)
            if not item:
                return None
            if time.time() - item["time"] > item["ttl"]:
                self.cache.pop(key, None)
                return None
            return item.get("saved_at")
