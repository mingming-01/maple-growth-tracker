"""Bounded, process-local metrics for performance baselines.

The collector stores low-cardinality labels and bounded samples only.
It is intentionally process-local: each Gunicorn worker reports its own view.
"""
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import os
import threading


class PerformanceMetrics:
    def __init__(self, sample_capacity=2000):
        self._lock = threading.Lock()
        self._sample_capacity = max(100, int(sample_capacity))
        self._counters = Counter()
        self._samples = defaultdict(lambda: deque(maxlen=self._sample_capacity))
        self._started_at = self._now()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _key(name, labels):
        normalized = []
        for key, value in sorted(labels.items()):
            label = str(value).strip().replace("\\n", " ")[:80]
            normalized.append(f"{key}={label}")
        return str(name) + ("{" + ",".join(normalized) + "}" if normalized else "")

    def increment(self, name, amount=1, **labels):
        try:
            value = int(amount)
        except (TypeError, ValueError):
            value = 1
        if value <= 0:
            return
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def observe(self, name, value, **labels):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if number < 0:
            return
        key = self._key(name, labels)
        with self._lock:
            self._samples[key].append(number)

    @staticmethod
    def _percentile(values, percentile):
        if not values:
            return None
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
        return round(ordered[index], 3)

    def snapshot(self):
        with self._lock:
            counters = dict(self._counters)
            samples = {key: list(values) for key, values in self._samples.items()}
            started_at = self._started_at
        timings = {}
        for key, values in samples.items():
            if not values:
                continue
            timings[key] = {
                "count": len(values),
                "sampleCapacity": self._sample_capacity,
                "min": round(min(values), 3),
                "max": round(max(values), 3),
                "mean": round(sum(values) / len(values), 3),
                "p50": self._percentile(values, 0.50),
                "p95": self._percentile(values, 0.95),
            }
        return {
            "scope": "process-local",
            "workerPid": os.getpid(),
            "startedAt": started_at,
            "capturedAt": self._now(),
            "counters": counters,
            "timings": timings,
        }

    def reset(self):
        with self._lock:
            self._counters.clear()
            self._samples.clear()
            self._started_at = self._now()


_METRICS = PerformanceMetrics()


def get_performance_metrics():
    return _METRICS


def increment_metric(name, amount=1, **labels):
    _METRICS.increment(name, amount=amount, **labels)


def observe_metric(name, value, **labels):
    _METRICS.observe(name, value, **labels)


def performance_metrics_snapshot():
    return _METRICS.snapshot()
