"""Suggested starter prompts for the chat screen.

Static on purpose (no DB table needed yet). Each prompt is written against the
Gold/Silver tables the AI analyst can query: daily_sales, product_daily,
customer_metrics, inventory_snapshot_daily, refund_daily, fulfillment_daily,
channel_daily.

``min_connections`` hides prompts that make no sense yet: only "compare my
stores" needs 2+ connected stores; everything else is always shown so a new
workspace never gets an empty list (the UI uses ``context.connections`` to show
a "connect a store to get answers" hint instead).
"""
from __future__ import annotations

from typing import Any

PROMPTS: list[dict[str, Any]] = [
    {"id": "sales-summary-30d", "category": "sales", "title": "Sales summary",
     "text": "Give me a summary of total sales, orders and average order value for the last 30 days.", "min_connections": 0},
    {"id": "sales-trend-90d", "category": "sales", "title": "Daily sales trend",
     "text": "Show my daily revenue trend for the last 90 days and point out the best and worst days.", "min_connections": 0},
    {"id": "sales-month-vs-prev", "category": "sales", "title": "This month vs last month",
     "text": "Compare this month's revenue and orders with last month.", "min_connections": 0},
    {"id": "products-top-10", "category": "products", "title": "Top selling products",
     "text": "What are my top 10 best selling products by revenue in the last 30 days?", "min_connections": 0},
    {"id": "products-declining", "category": "products", "title": "Declining products",
     "text": "Which products have sold noticeably less in the last 30 days than in the previous 30 days?", "min_connections": 0},
    {"id": "customers-repeat", "category": "customers", "title": "Repeat customers",
     "text": "How many repeat customers do I have and what share of revenue do they bring?", "min_connections": 0},
    {"id": "customers-top-spenders", "category": "customers", "title": "Top customers",
     "text": "Who are my top 10 customers by lifetime spend?", "min_connections": 0},
    {"id": "inventory-low-stock", "category": "inventory", "title": "Low stock",
     "text": "Which products are low on stock or out of stock right now?", "min_connections": 0},
    {"id": "refunds-rate", "category": "refunds", "title": "Refund rate",
     "text": "What is my refund rate for the last 30 days and which products are refunded the most?", "min_connections": 0},
    {"id": "fulfillment-speed", "category": "fulfillment", "title": "Fulfillment performance",
     "text": "How long does it take on average to fulfill orders, and is it getting better or worse?", "min_connections": 0},
    {"id": "channels-compare", "category": "channels", "title": "Compare my stores",
     "text": "Compare sales across all my connected stores for the last 90 days.", "min_connections": 2},
]

CATEGORIES = sorted({p["category"] for p in PROMPTS})
