"""Shared test fixtures.

The runtime live-arm flag in execution.py is process-global (a successful MT5
connect arms order placement for the whole process). Reset it before every test
so one test arming live can never leak into another's assertions.
"""
import pytest

import execution


@pytest.fixture(autouse=True)
def _reset_live_arm():
    execution.disarm_live()
    yield
    execution.disarm_live()
