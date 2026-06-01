"""Tests for metrics.py — fire-and-forget UDP StatsD client."""
import socket

import pytest

from metrics import StatsD


@pytest.fixture
def listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    s.settimeout(1.0)
    yield s, s.getsockname()[1]
    s.close()


class TestStatsD:
    def test_incr_wire_format(self, listener):
        sock, port = listener
        StatsD("127.0.0.1", port, prefix="app").incr("orders")
        data, _ = sock.recvfrom(1024)
        assert data.decode() == "app.orders:1|c"

    def test_incr_with_count(self, listener):
        sock, port = listener
        StatsD("127.0.0.1", port, prefix="app").incr("orders", 5)
        assert sock.recvfrom(1024)[0].decode() == "app.orders:5|c"

    def test_timing_wire_format(self, listener):
        sock, port = listener
        StatsD("127.0.0.1", port, prefix="app").timing("feed.fetch_ms", 42.5)
        assert sock.recvfrom(1024)[0].decode() == "app.feed.fetch_ms:42.5|ms"

    def test_gauge_wire_format(self, listener):
        sock, port = listener
        StatsD("127.0.0.1", port, prefix="app").gauge("proc.cpu", 12.3)
        assert sock.recvfrom(1024)[0].decode() == "app.proc.cpu:12.3|g"

    def test_no_prefix(self, listener):
        sock, port = listener
        StatsD("127.0.0.1", port, prefix="").incr("x")
        assert sock.recvfrom(1024)[0].decode() == "x:1|c"

    def test_disabled_sends_nothing(self, listener):
        sock, port = listener
        StatsD("127.0.0.1", port, enabled=False).incr("x")
        with pytest.raises(socket.timeout):
            sock.recvfrom(1024)

    def test_bad_host_never_raises(self):
        # unresolvable host must not crash the caller (fire-and-forget)
        StatsD("no.such.host.invalid", 9125).incr("x")

    def test_timeit_emits_timing(self, listener):
        sock, port = listener
        c = StatsD("127.0.0.1", port, prefix="app")
        with c.timeit("block_ms"):
            pass
        payload = sock.recvfrom(1024)[0].decode()
        assert payload.startswith("app.block_ms:")
        assert payload.endswith("|ms")
