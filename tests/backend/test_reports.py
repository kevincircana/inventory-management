"""
Tests for report endpoints (quarterly and monthly trends).

Reports must honour the same global filters as /api/orders, and must not be
limited to the 2025 quarters that were previously hard-coded.
"""
import pytest


class TestQuarterlyReportEndpoint:
    """Test suite for /api/reports/quarterly."""

    def test_quarters_are_sorted_by_year_then_quarter(self, client):
        """Quarters come back in chronological order."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        quarters = [q["quarter"] for q in response.json()]
        keys = [(int(q.split("-")[1]), int(q[1])) for q in quarters]
        assert keys == sorted(keys)

    def test_quarter_totals_match_orders_endpoint(self, client):
        """Total orders across quarters equals the orders returned by /api/orders."""
        report = client.get("/api/reports/quarterly", params={"warehouse": "London"}).json()
        orders = client.get("/api/orders", params={"warehouse": "London"}).json()

        assert sum(q["total_orders"] for q in report) == len(orders)

    def test_warehouse_filter_reduces_totals(self, client):
        """Filtering by warehouse returns fewer orders than the unfiltered report."""
        all_total = sum(q["total_orders"] for q in client.get("/api/reports/quarterly").json())
        london_total = sum(
            q["total_orders"]
            for q in client.get("/api/reports/quarterly", params={"warehouse": "London"}).json()
        )

        assert 0 < london_total < all_total

    def test_month_filter_returns_single_quarter(self, client):
        """Filtering by a quarter value (e.g. Q1-2025) leaves only that quarter's orders."""
        response = client.get("/api/reports/quarterly", params={"month": "Q1-2025"})
        assert response.status_code == 200

        quarters = {q["quarter"] for q in response.json()}
        assert quarters == {"Q1-2025"}

    def test_all_filter_value_is_ignored(self, client):
        """The 'all' value means no filter, matching the other endpoints."""
        unfiltered = client.get("/api/reports/quarterly").json()
        with_all = client.get(
            "/api/reports/quarterly",
            params={"warehouse": "all", "category": "all", "status": "all", "month": "all"},
        ).json()

        assert with_all == unfiltered

    def test_fulfillment_rate_within_bounds(self, client):
        """Fulfillment rate is a percentage between 0 and 100."""
        for q in client.get("/api/reports/quarterly").json():
            assert 0 <= q["fulfillment_rate"] <= 100


class TestMonthlyTrendsEndpoint:
    """Test suite for /api/reports/monthly-trends."""

    def test_months_are_sorted_and_formatted(self, client):
        """Months come back sorted as YYYY-MM."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        months = [m["month"] for m in response.json()]
        assert months == sorted(months)
        for month in months:
            assert len(month) == 7 and month[4] == "-"

    def test_month_filter_returns_only_that_month(self, client):
        """Filtering by a YYYY-MM value returns only that month."""
        response = client.get("/api/reports/monthly-trends", params={"month": "2025-03"})
        assert response.status_code == 200

        months = {m["month"] for m in response.json()}
        assert months <= {"2025-03"}

    def test_status_filter_limits_order_counts(self, client):
        """Filtering by status returns no more orders than the unfiltered trend."""
        all_count = sum(m["order_count"] for m in client.get("/api/reports/monthly-trends").json())
        delivered_count = sum(
            m["order_count"]
            for m in client.get(
                "/api/reports/monthly-trends", params={"status": "Delivered"}
            ).json()
        )

        assert delivered_count <= all_count

    def test_monthly_totals_match_orders_endpoint(self, client):
        """Total orders across months equals the orders returned by /api/orders for the same filter."""
        report = client.get("/api/reports/monthly-trends", params={"category": "Sensors"}).json()
        orders = client.get("/api/orders", params={"category": "Sensors"}).json()

        assert sum(m["order_count"] for m in report) == len(orders)
