"""
Reporting & export service for generating CSV financial reports.
PDF invoice generation can be added with a library like `weasyprint` or `pdfkit`.
"""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus, Payment, PaymentMethod


async def generate_csv_report(
    session: AsyncSession,
    start_date: date,
    end_date: date,
) -> str:
    """
    Generate a CSV report of all orders and payments within a date range.
    Returns the CSV as a string.
    """
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.scheduled_date >= start_date, Order.scheduled_date <= end_date)
                .options(selectinload(Order.payments))
                .order_by(Order.scheduled_date, Order.created_at)
            )
        ).all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "Order Code",
            "Date",
            "Slot",
            "Customer Name",
            "Customer Phone",
            "Service",
            "Source",
            "Status",
            "Amount",
            "Payment Status",
            "Payment Method",
            "Payment Amount",
            "Area",
            "Created At",
        ]
    )

    for order in orders:
        payments = list(order.payments) if order.payments else []
        if payments:
            for payment in payments:
                writer.writerow(
                    [
                        order.order_code,
                        order.scheduled_date.isoformat(),
                        order.scheduled_slot,
                        order.customer_name,
                        order.customer_phone,
                        order.service_name,
                        order.source.value,
                        order.status.value,
                        float(order.amount) if order.amount else "",
                        payment.status.value,
                        payment.method.value,
                        float(payment.amount),
                        order.area,
                        order.created_at.isoformat(),
                    ]
                )
        else:
            writer.writerow(
                [
                    order.order_code,
                    order.scheduled_date.isoformat(),
                    order.scheduled_slot,
                    order.customer_name,
                    order.customer_phone,
                    order.service_name,
                    order.source.value,
                    order.status.value,
                    float(order.amount) if order.amount else "",
                    "no_payment",
                    "",
                    "",
                    order.area,
                    order.created_at.isoformat(),
                ]
            )

    return output.getvalue()


async def generate_revenue_summary(
    session: AsyncSession,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Generate a revenue summary for the given date range.
    """
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.scheduled_date >= start_date, Order.scheduled_date <= end_date)
                .options(selectinload(Order.payments))
                .order_by(Order.scheduled_date)
            )
        ).all()
    )

    total_revenue = Decimal("0")
    upi_revenue = Decimal("0")
    cash_revenue = Decimal("0")
    total_orders = len(orders)
    completed_orders = sum(1 for o in orders if o.status == OrderStatus.COMPLETED)
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    daily_revenue: dict[str, dict[str, float]] = {}

    for order in orders:
        source = order.source.value
        by_source[source] = by_source.get(source, 0) + 1
        status = order.status.value
        by_status[status] = by_status.get(status, 0) + 1

        day_key = order.scheduled_date.isoformat()
        if day_key not in daily_revenue:
            daily_revenue[day_key] = {"revenue": 0.0, "upi": 0.0, "cash": 0.0, "orders": 0}
        daily_revenue[day_key]["orders"] += 1

        for payment in order.payments:
            if payment.status.value == "received":
                amt = float(payment.amount)
                total_revenue += payment.amount
                daily_revenue[day_key]["revenue"] += amt
                if payment.method == PaymentMethod.UPI:
                    upi_revenue += payment.amount
                    daily_revenue[day_key]["upi"] += amt
                else:
                    cash_revenue += payment.amount
                    daily_revenue[day_key]["cash"] += amt

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "total_revenue": float(total_revenue),
        "upi_revenue": float(upi_revenue),
        "cash_revenue": float(cash_revenue),
        "by_source": by_source,
        "by_status": by_status,
        "daily_revenue": [
            {"date": d, **v} for d, v in sorted(daily_revenue.items())
        ],
    }