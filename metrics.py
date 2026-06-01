"""Fire-and-forget UDP StatsD metrics.

Non-blocking by construction: a single datagram socket, `sendto` wrapped so any
error (unresolved host, full buffer) is swallowed — emitting a metric must never
slow down or crash the trading loop. A statsd_exporter (Component 3) ingests
these on UDP 9125 and exposes them to Prometheus.

Wire format: ``<prefix>.<name>:<value>|<type>``  (c=counter, ms=timer, g=gauge).
"""
from __future__ import annotations

import os
import socket
import time
from contextlib import contextmanager

logger = __import__("logging").getLogger(__name__)


class StatsD:
    def __init__(self, host: str, port: int, enabled: bool = True, prefix: str = "xauusd"):
        self.addr = (host, port)
        self.enabled = enabled
        self.prefix = prefix
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _name(self, name: str) -> str:
        return f"{self.prefix}.{name}" if self.prefix else name

    def _send(self, line: str) -> None:
        if not self.enabled:
            return
        try:
            self._sock.sendto(line.encode("utf-8"), self.addr)
        except OSError:
            pass  # fire-and-forget: never propagate

    def incr(self, name: str, n: int = 1) -> None:
        self._send(f"{self._name(name)}:{n}|c")

    def timing(self, name: str, ms: float) -> None:
        self._send(f"{self._name(name)}:{ms}|ms")

    def gauge(self, name: str, value: float) -> None:
        self._send(f"{self._name(name)}:{value}|g")

    @contextmanager
    def timeit(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.timing(name, round((time.perf_counter() - start) * 1000, 2))


def _truthy(v: str) -> bool:
    return v.strip().lower() in {"1", "true", "yes", "on"}


# Process-wide default client, configured from the environment.
STATS = StatsD(
    host=os.getenv("STATSD_HOST", "127.0.0.1"),
    port=int(os.getenv("STATSD_PORT", "9125")),
    enabled=_truthy(os.getenv("METRICS_ENABLED", "true")),
    prefix=os.getenv("STATSD_PREFIX", "xauusd"),
)


def incr(name: str, n: int = 1) -> None:
    STATS.incr(name, n)


def timing(name: str, ms: float) -> None:
    STATS.timing(name, ms)


def gauge(name: str, value: float) -> None:
    STATS.gauge(name, value)


def timeit(name: str):
    return STATS.timeit(name)
