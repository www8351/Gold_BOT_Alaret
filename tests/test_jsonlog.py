"""Tests for jsonlog.py — structured JSON logging to stdout."""
import json
import logging

from jsonlog import JsonFormatter, setup_logging


def make_record(msg="hello %s", args=("world",), level=logging.INFO, name="x"):
    return logging.LogRecord(name=name, level=level, pathname="", lineno=0,
                             msg=msg, args=args, exc_info=None)


class TestJsonFormatter:
    def test_core_fields(self):
        out = JsonFormatter().format(make_record())
        d = json.loads(out)
        assert d["level"] == "INFO"
        assert d["logger"] == "x"
        assert d["msg"] == "hello world"   # args interpolated
        assert "ts" in d

    def test_extra_fields_surface(self):
        rec = make_record()
        rec.symbol = "XAUUSD"
        rec.lots = 0.1
        d = json.loads(JsonFormatter().format(rec))
        assert d["symbol"] == "XAUUSD"
        assert d["lots"] == 0.1

    def test_non_serializable_does_not_raise(self):
        rec = make_record()
        rec.weird = object()
        out = JsonFormatter().format(rec)   # must not raise
        json.loads(out)                      # still valid JSON

    def test_exception_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            rec = logging.LogRecord("x", logging.ERROR, "", 0, "failed", None, sys.exc_info())
        d = json.loads(JsonFormatter().format(rec))
        assert "boom" in d["exc"]


class TestSetupLogging:
    def test_installs_json_stream_handler(self):
        setup_logging(level="INFO")
        root = logging.getLogger()
        assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
