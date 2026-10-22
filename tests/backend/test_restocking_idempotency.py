"""
Tests for idempotent restocking order submission (Idempotency-Key header).

A retry of the same submission must return the original order and create nothing new.
The restocking list and the key store are shared across the app, so each test starts
with both empty.
"""
import threading
from collections import OrderedDict

import pytest

import main


@pytest.fixture(autouse=True)
def fresh_restocking_state(monkeypatch):
    """Start each test with no restocking orders and no stored idempotency keys."""
    monkeypatch.setattr(main, "restocking_orders", [])
    monkeypatch.setattr(main, "_restock_idempotency", OrderedDict())


@pytest.fixture
def sku(client):
    """A SKU that has a recommended shortfall, so a one-unit order is valid."""
    recommendations = client.get("/api/restocking/recommendations", params={"budget": 1000000}).json()
    if not recommendations["items"]:
        pytest.skip("No restocking recommendations in the mock data")
    return recommendations["items"][0]["sku"]


def _post(client, sku, key=None, quantity=1):
    headers = {"Idempotency-Key": key} if key is not None else {}
    return client.post(
        "/api/restocking/orders",
        json={"items": [{"sku": sku, "quantity": quantity}]},
        headers=headers,
    )


def _restocking_audit_entries(client):
    return client.get("/api/audit-log", params={"entity_type": "restocking_order"}).json()


class TestIdempotentReplay:
    """Same key, same items: one order, original returned."""

    def test_same_key_twice_creates_one_order(self, client, sku):
        """The second request returns the first order and does not add another."""
        first = _post(client, sku, key="key-replay-1")
        second = _post(client, sku, key="key-replay-1")

        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["order_number"] == first.json()["order_number"]
        assert len(main.restocking_orders) == 1

    def test_replay_does_not_write_a_second_audit_entry(self, client, sku):
        """A replayed submission adds no audit entry."""
        _post(client, sku, key="key-replay-audit")
        before = len(_restocking_audit_entries(client))

        _post(client, sku, key="key-replay-audit")

        assert len(_restocking_audit_entries(client)) == before

    def test_different_keys_create_separate_orders(self, client, sku):
        """Two submissions with different keys are two orders with different order numbers."""
        first = _post(client, sku, key="key-a")
        second = _post(client, sku, key="key-b")

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["order_number"] != second.json()["order_number"]
        assert len(main.restocking_orders) == 2

    def test_no_key_is_not_deduplicated(self, client, sku):
        """Without a key the endpoint behaves as before: every request creates an order."""
        _post(client, sku)
        _post(client, sku)

        assert len(main.restocking_orders) == 2


class TestIdempotencyConflicts:
    """Key reuse with different items is rejected rather than silently replayed."""

    def test_same_key_different_items_returns_409(self, client, sku):
        """Re-using a key for a different order returns 409 and creates nothing."""
        _post(client, sku, key="key-conflict", quantity=1)

        response = _post(client, sku, key="key-conflict", quantity=2)

        assert response.status_code == 409
        assert len(main.restocking_orders) == 1

    def test_failed_request_is_not_cached(self, client, sku):
        """A rejected request does not store its key, so the same key can succeed on retry."""
        rejected = _post(client, sku, key="key-retry", quantity=10**9)
        assert rejected.status_code == 400

        retried = _post(client, sku, key="key-retry", quantity=1)

        assert retried.status_code == 201
        assert len(main.restocking_orders) == 1

    def test_key_longer_than_limit_is_rejected(self, client, sku):
        """Keys over 200 characters are refused by validation."""
        response = _post(client, sku, key="k" * 201)

        assert response.status_code == 422
        assert main.restocking_orders == []


class TestIdempotencyStore:
    """The key store is capped so it cannot grow without limit."""

    def test_oldest_keys_are_evicted(self, client, sku, monkeypatch):
        """Once the cap is reached, the oldest key is forgotten and its order is no longer replayed."""
        monkeypatch.setattr(main, "RESTOCK_IDEMPOTENCY_MAX_KEYS", 2)

        _post(client, sku, key="k1")
        _post(client, sku, key="k2")
        _post(client, sku, key="k3")

        assert list(main._restock_idempotency.keys()) == ["k2", "k3"]


class TestConcurrentSubmissions:
    """Identical requests arriving at the same time create one order."""

    def test_simultaneous_same_key_creates_one_order(self, sku):
        """Eight threads submit the same key at once; exactly one order is created."""
        from fastapi.testclient import TestClient

        results = []
        barrier = threading.Barrier(8)

        def submit():
            client = TestClient(main.app)
            barrier.wait()
            results.append(_post(client, sku, key="key-race").status_code)

        threads = [threading.Thread(target=submit) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(main.restocking_orders) == 1
        assert sorted(results) == [200] * 7 + [201]
