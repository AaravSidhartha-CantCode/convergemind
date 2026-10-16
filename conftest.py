import os
import uuid

import pytest

os.environ.setdefault("FALKORDB_HOST", "localhost")
os.environ.setdefault("FALKORDB_PORT", "6379")

from backend.db import get_customer_graph  # noqa: E402


@pytest.fixture
def tenant():
    """A throwaway customer id whose graph key is dropped after the test."""
    customer_id = f"test_{uuid.uuid4().hex[:8]}"
    yield customer_id
    try:
        get_customer_graph(customer_id).delete()
    except Exception:
        pass


@pytest.fixture
def issue_type():
    """A unique issue type, so shared-graph counts are deterministic."""
    return f"test_issue_{uuid.uuid4().hex[:8]}"
