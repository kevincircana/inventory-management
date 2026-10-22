import itertools
from datetime import date, datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str
    quantity_on_hand: int
    unit_cost: float

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

# Tasks are kept in memory only. Ids start at 1000 so they never collide with
# the mock tasks in useAuth.js (ids 1-4), which the client merges into one list.
class Task(BaseModel):
    id: int
    title: str
    priority: str
    dueDate: str
    status: str = 'pending'

class CreateTaskRequest(BaseModel):
    title: str
    priority: str = 'medium'
    dueDate: str

tasks_store: List[Task] = []
_next_task_id = itertools.count(1000)

@app.get("/api/tasks", response_model=List[Task])
def get_tasks():
    """List tasks created through the API"""
    return tasks_store

@app.post("/api/tasks", response_model=Task, status_code=201)
def create_task(body: CreateTaskRequest):
    """Create a task"""
    task = Task(id=next(_next_task_id), **body.model_dump())
    tasks_store.append(task)
    return task

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """Delete a task by id"""
    for i, task in enumerate(tasks_store):
        if task.id == task_id:
            del tasks_store[i]
            return {"deleted": task_id}
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

@app.patch("/api/tasks/{task_id}", response_model=Task)
def toggle_task(task_id: int):
    """Toggle a task between pending and completed. The client sends no body."""
    for task in tasks_store:
        if task.id == task_id:
            task.status = 'pending' if task.status == 'completed' else 'completed'
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

@app.get("/api/purchase-orders/{backlog_item_id}", response_model=PurchaseOrder)
def get_purchase_order(backlog_item_id: str):
    """Get the purchase order for a backlog item"""
    for po in purchase_orders:
        if po["backlog_item_id"] == backlog_item_id:
            return po
    raise HTTPException(status_code=404, detail=f"No purchase order for backlog item {backlog_item_id}")

@app.post("/api/purchase-orders", response_model=PurchaseOrder, status_code=201)
def create_purchase_order(body: CreatePurchaseOrderRequest):
    """Create a purchase order for a backlog item"""
    if not any(item["id"] == body.backlog_item_id for item in backlog_items):
        raise HTTPException(status_code=404, detail=f"Backlog item {body.backlog_item_id} not found")
    # Only one PO per backlog item. The backlog endpoint flags items that already have one.
    if any(po["backlog_item_id"] == body.backlog_item_id for po in purchase_orders):
        raise HTTPException(status_code=400, detail=f"Backlog item {body.backlog_item_id} already has a purchase order")

    po = PurchaseOrder(
        id=f"PO-{len(purchase_orders) + 1:04d}",
        status="Pending",
        created_date=date.today().isoformat(),
        **body.model_dump()
    )
    # Appended to the module-level list so GET endpoints see it. Lost on restart, like all data here.
    purchase_orders.append(po.model_dump())
    return po

# Restocking. Orders live in memory only, like the other demo data.
RESTOCK_LEAD_TIME_DAYS = 14  # Fixed demo lead time. No supplier lead-time data exists yet.

class RestockingRecommendation(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_cost: float
    line_total: float
    forecasted_demand: int
    quantity_on_hand: int

class RestockingRecommendations(BaseModel):
    budget: float
    total_cost: float
    remaining_budget: float
    items: List[RestockingRecommendation]

class PlaceRestockingItem(BaseModel):
    sku: str
    quantity: int

class PlaceRestockingRequest(BaseModel):
    items: List[PlaceRestockingItem]

class RestockingOrderLine(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_cost: float
    line_total: float

class RestockingOrder(BaseModel):
    id: str
    order_number: str
    submitted_date: str
    expected_delivery: str
    lead_time_days: int
    status: str
    items: List[RestockingOrderLine]
    total_value: float

restocking_orders: List[RestockingOrder] = []

def build_restock_recommendations(budget: float) -> RestockingRecommendations:
    """Pick items to restock, largest shortfall first, without exceeding the budget"""
    # Shortfall is forecast demand not covered by stock on hand.
    # Forecast entries carry their own on-hand quantity and unit cost, so no inventory join is needed.
    candidates = []
    for forecast in demand_forecasts:
        shortfall = forecast["forecasted_demand"] - forecast["quantity_on_hand"]
        if shortfall > 0:
            candidates.append((shortfall, forecast))

    candidates.sort(key=lambda c: c[0], reverse=True)

    remaining = budget
    chosen = []
    for shortfall, forecast in candidates:
        line_total = round(shortfall * forecast["unit_cost"], 2)
        # Skip items that don't fit instead of stopping, so cheaper items lower
        # in the list can still use what is left of the budget.
        if line_total > remaining:
            continue
        remaining -= line_total
        chosen.append(RestockingRecommendation(
            sku=forecast["item_sku"],
            name=forecast["item_name"],
            quantity=shortfall,
            unit_cost=forecast["unit_cost"],
            line_total=line_total,
            forecasted_demand=forecast["forecasted_demand"],
            quantity_on_hand=forecast["quantity_on_hand"],
        ))

    total_cost = round(budget - remaining, 2)
    return RestockingRecommendations(
        budget=budget,
        total_cost=total_cost,
        remaining_budget=round(remaining, 2),
        items=chosen,
    )

@app.get("/api/restocking/recommendations", response_model=RestockingRecommendations)
def get_restocking_recommendations(budget: float = Query(0, ge=0)):
    """Recommend restocking items that fit within the given budget"""
    return build_restock_recommendations(budget)

@app.post("/api/restocking/orders", response_model=RestockingOrder, status_code=201)
def place_restocking_order(body: PlaceRestockingRequest):
    """Submit a restocking order. Unit costs are looked up on the server, not taken from the client."""
    if not body.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    forecast_by_sku = {f["item_sku"]: f for f in demand_forecasts}
    lines = []
    for requested in body.items:
        if requested.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Quantity for {requested.sku} must be greater than 0")
        forecast = forecast_by_sku.get(requested.sku)
        if forecast is None:
            raise HTTPException(status_code=404, detail=f"SKU {requested.sku} not found")
        lines.append(RestockingOrderLine(
            sku=forecast["item_sku"],
            name=forecast["item_name"],
            quantity=requested.quantity,
            unit_cost=forecast["unit_cost"],
            line_total=round(requested.quantity * forecast["unit_cost"], 2),
        ))

    submitted = datetime.now().replace(microsecond=0)
    expected = submitted + timedelta(days=RESTOCK_LEAD_TIME_DAYS)
    order = RestockingOrder(
        id=str(len(restocking_orders) + 1),
        order_number=f"RST-{submitted.year}-{len(restocking_orders) + 1:04d}",
        submitted_date=submitted.isoformat(),
        expected_delivery=expected.isoformat(),
        lead_time_days=RESTOCK_LEAD_TIME_DAYS,
        status="Submitted",
        items=lines,
        total_value=round(sum(line.line_total for line in lines), 2),
    )
    restocking_orders.append(order)
    return order

@app.get("/api/restocking/orders", response_model=List[RestockingOrder])
def get_restocking_orders():
    """List submitted restocking orders, newest first"""
    return list(reversed(restocking_orders))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
