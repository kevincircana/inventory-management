"""
Tests for the audit log: recording purchase order and restocking order creates,
and querying the log.

The app holds one in-memory log, shared across tests, so each test identifies its
own entries by entity id or by a unique actor name.
"""
from collections import deque
from types import SimpleNamespace
from urllib.parse import quote

import pytest

import main


@pytest.fixture(autouse=True)
def empty_purchase_orders(monkeypatch):
    """Start each test with no purchase orders. The mock data has only four backlog items,
    and each one can hold a single PO, so without this the tests would run out of items."""
    monkeypatch.setattr(main, "purchase_orders", [])


def _create_purchase_order(client, actor_name=None):
    """Create a purchase order for a backlog item that does not have one yet."""
    backlog = client.get("/api/backlog").json()
    unused = next((item for item in backlog if not item.get("has_purchase_order")), None)
    if unused is None:
        pytest.skip("No backlog item without a purchase order is left in the mock data")

    headers = {"X-Actor-Name": quote(actor_name)} if actor_name else {}
    response = client.post(
        "/api/purchase-orders",
        json={
            "backlog_item_id": unused["id"],
            "supplier_name": "Test Supplier",
            "quantity": 5,
            "unit_cost": 10.0,
            "expected_delivery_date": "2026-12-01",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _place_restocking_order(client, actor_name=None):
    """Submit a one-unit restocking order for the first recommended SKU."""
    recommendations = client.get("/api/restocking/recommendations", params={"budget": 1000000}).json()
    if not recommendations["items"]:
        pytest.skip("No restocking recommendations in the mock data")

    headers = {"X-Actor-Name": quote(actor_name)} if actor_name else {}
    response = client.post(
        "/api/restocking/orders",
        json={"items": [{"sku": recommendations["items"][0]["sku"], "quantity": 1}]},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


class TestAuditLogRecording:
    """Creates are recorded with who, what, and when."""

    def test_purchase_order_create_is_logged(self, client):
        """A purchase order create produces an entry with the actor and the new record."""
        po = _create_purchase_order(client, actor_name="Audit Test PO")

        entries = client.get("/api/audit-log", params={"entity_type": "purchase_order"}).json()
        entry = next(e for e in entries if e["entity_id"] == po["id"])

        assert entry["entity_type"] == "purchase_order"
        assert entry["action"] == "create"
        assert entry["actor_name"] == "Audit Test PO"
        assert entry["before"] is None
        assert entry["after"]["id"] == po["id"]
        assert entry["after"]["supplier_name"] == "Test Supplier"
        assert entry["timestamp"]

    def test_restocking_order_create_is_logged(self, client):
        """A restocking order create produces an entry with the actor and the submitted order."""
        order = _place_restocking_order(client, actor_name="Audit Test Restock")

        entries = client.get("/api/audit-log", params={"entity_type": "restocking_order"}).json()
        # The entity id is the order number users see (RST-YYYY-NNNN), not the internal id
        entry = next(e for e in entries if e["entity_id"] == order["order_number"])

        assert entry["action"] == "create"
        assert entry["actor_name"] == "Audit Test Restock"
        assert entry["before"] is None
        assert entry["after"]["order_number"] == order["order_number"]
        assert entry["after"]["status"] == "Submitted"

    def test_failed_create_is_not_logged(self, client):
        """A rejected request does not add an audit entry."""
        before = len(client.get("/api/audit-log").json())

        response = client.post(
            "/api/purchase-orders",
            json={
                "backlog_item_id": "does-not-exist",
                "supplier_name": "Nobody",
                "quantity": 1,
                "unit_cost": 1.0,
                "expected_delivery_date": "2026-12-01",
            },
            headers={"X-Actor-Name": quote("Audit Test Rejected")},
        )

        assert response.status_code == 404
        assert len(client.get("/api/audit-log").json()) == before

    def test_japanese_actor_name_round_trips(self, client):
        """Non-ASCII actor names survive the URL-encoded header."""
        po = _create_purchase_order(client, actor_name="田中 太郎")

        entries = client.get("/api/audit-log", params={"entity_type": "purchase_order"}).json()
        entry = next(e for e in entries if e["entity_id"] == po["id"])

        assert entry["actor_name"] == "田中 太郎"

    def test_missing_actor_header_records_null_actor(self, client):
        """Writes without the header are still logged, with actor_name set to null."""
        po = _create_purchase_order(client, actor_name=None)

        entries = client.get("/api/audit-log", params={"entity_type": "purchase_order"}).json()
        entry = next(e for e in entries if e["entity_id"] == po["id"])

        assert entry["actor_name"] is None

    def test_actor_name_is_truncated(self, client):
        """Overlong actor names are cut to the maximum length."""
        po = _create_purchase_order(client, actor_name="x" * 150)

        entries = client.get("/api/audit-log", params={"entity_type": "purchase_order"}).json()
        entry = next(e for e in entries if e["entity_id"] == po["id"])

        assert len(entry["actor_name"]) == main.AUDIT_ACTOR_MAX_LENGTH


class TestAuditLogQuery:
    """Filtering, ordering, and validation of GET /api/audit-log."""

    def test_entity_type_filter(self, client):
        """Filtering by entity type returns only that type."""
        _create_purchase_order(client, actor_name="Audit Test Filter PO")
        _place_restocking_order(client, actor_name="Audit Test Filter Restock")

        entries = client.get("/api/audit-log", params={"entity_type": "restocking_order"}).json()

        assert len(entries) > 0
        assert {e["entity_type"] for e in entries} == {"restocking_order"}

    def test_all_values_mean_no_filter(self, client):
        """'all' for entity type and action matches an unfiltered query."""
        unfiltered = client.get("/api/audit-log").json()
        with_all = client.get(
            "/api/audit-log", params={"entity_type": "all", "action": "all"}
        ).json()

        assert with_all == unfiltered

    def test_action_filter(self, client):
        """Filtering by action returns only entries with that action."""
        entries = client.get("/api/audit-log", params={"action": "create"}).json()

        assert {e["action"] for e in entries} <= {"create"}

    def test_results_are_newest_first(self, client):
        """Entries come back with the highest id first."""
        _create_purchase_order(client, actor_name="Audit Test Order A")
        _create_purchase_order(client, actor_name="Audit Test Order B")

        ids = [e["id"] for e in client.get("/api/audit-log").json()]

        assert ids == sorted(ids, reverse=True)

    def test_date_range_is_inclusive(self, client):
        """An entry is included when its date equals start_date or end_date."""
        po = _create_purchase_order(client, actor_name="Audit Test Dates")
        entry = next(
            e for e in client.get("/api/audit-log", params={"entity_type": "purchase_order"}).json()
            if e["entity_id"] == po["id"]
        )
        day = entry["timestamp"][:10]

        same_day = client.get("/api/audit-log", params={"start_date": day, "end_date": day}).json()
        assert any(e["id"] == entry["id"] for e in same_day)

    def test_date_range_excludes_other_days(self, client):
        """An entry is excluded when the range ends before its date."""
        po = _create_purchase_order(client, actor_name="Audit Test Excluded")
        entry = next(
            e for e in client.get("/api/audit-log", params={"entity_type": "purchase_order"}).json()
            if e["entity_id"] == po["id"]
        )

        results = client.get("/api/audit-log", params={"end_date": "2000-01-01"}).json()
        assert not any(e["id"] == entry["id"] for e in results)

    @pytest.mark.parametrize("params", [
        {"entity_type": "invoice"},
        {"action": "delete"},
        {"start_date": "2025/01/01"},
        {"end_date": "01-02-2025"},
    ])
    def test_invalid_parameters_are_rejected(self, client, params):
        """Values outside the allowed set or format return 422."""
        response = client.get("/api/audit-log", params=params)
        assert response.status_code == 422


class TestAuditLogCap:
    """The log keeps only the most recent entries."""

    def test_cap_is_one_thousand(self):
        """The configured cap is 1,000 entries and the deque enforces it."""
        assert main.AUDIT_LOG_MAX_ENTRIES == 1000
        assert main.audit_log.maxlen == main.AUDIT_LOG_MAX_ENTRIES

    def test_oldest_entries_drop_off(self, monkeypatch):
        """Once full, recording another entry drops the oldest one."""
        small_log = deque(maxlen=3)
        monkeypatch.setattr(main, "audit_log", small_log)
        monkeypatch.setattr(main, "_next_audit_id", iter(range(1, 100)))
        fake_request = SimpleNamespace(headers={"X-Actor-Name": "Cap Test"})

        for i in range(5):
            main.record_audit(fake_request, "purchase_order", str(i), "create", None, {"n": i})

        assert len(small_log) == 3
        assert [e["id"] for e in small_log] == [3, 4, 5]
