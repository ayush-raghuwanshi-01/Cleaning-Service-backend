"""
End-to-end API test for the Home Shine backend.

Run against a locally running server (uvicorn on 127.0.0.1:8000) with your
venv active and migrations applied:

    python scripts/api_test.py

It registers a throwaway customer + admin, creates a service, places an order,
sets the price, advances status, records add-ons + payment, and checks tracking
+ day stats. Prints PASS/FAIL for every step.
"""

import os
import sys
from datetime import date, timedelta

# Ensure the project root is on sys.path so `app.*` imports resolve when the
# script is run as `python scripts/api_test.py` from the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from sqlalchemy import update

from app.core.config import get_settings
from app.db.session import engine
from app.models.user import User, UserRole

BASE = "http://127.0.0.1:8000/api/v1"

PASS = 0
FAIL = 0


def check(label, ok, extra=""):
    global PASS, FAIL
    mark = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{mark}] {label}{('  -> ' + extra) if (extra and not ok) else ''}")


def promote_to_owner(phone: str) -> None:
    """Promote a registered account to OWNER role directly in the DB (registration
    only creates CUSTOMER accounts). Uses the app's async engine."""
    import asyncio

    async def _promote() -> None:
        async with engine.begin() as conn:
            await conn.execute(update(User).where(User.phone == phone).values(role=UserRole.OWNER))

    asyncio.run(_promote())


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    import time as _time
    stamp = _time.time_ns() % 1000000  # unique per run

    # --- health (server + DB readiness) ---
    r = httpx.get("http://127.0.0.1:8000/health", timeout=10)
    check("GET /health", r.status_code == 200 and r.json().get("status") == "ok", f"{r.status_code} {r.text}")

    # --- public catalog (guest, no auth) ---
    r = c.get("/services")
    check("GET /services (public)", r.status_code == 200, f"{r.status_code}")
    r = c.get("/service-areas")
    check("GET /service-areas (public)", r.status_code == 200, f"{r.status_code}")
    r = c.get("/orders/track/DOESNOTEXIST")
    check("GET /orders/track unknown (404 expected)", r.status_code == 404, f"{r.status_code}")

    # --- customer register + login (unique phone per run) ---
    cphone = f"98{stamp:06d}1"[:10]
    passw = "TestPassword123!"
    r = c.post("/auth/register", json={"full_name": "Test Customer", "phone": cphone, "password": passw})
    check("register customer", r.status_code == 201, f"{r.status_code} {r.text}")
    r = c.post("/auth/login", json={"identifier": cphone, "password": passw})
    check("customer login", r.status_code == 200, f"{r.status_code} {r.text}")
    ctoken = r.json()["access_token"]
    chead = {"Authorization": f"Bearer {ctoken}"}

    # --- owner register + promote to OWNER in DB ---
    aphone = f"98{stamp:06d}2"[:10]
    r = c.post("/auth/register", json={"full_name": "Owner", "phone": aphone, "password": passw})
    check("register owner", r.status_code == 201, f"{r.status_code} {r.text}")
    promote_to_owner(aphone)
    check("promote owner to OWNER role", True)
    r = c.post("/auth/login", json={"identifier": aphone, "password": passw})
    check("owner login", r.status_code == 200, f"{r.status_code} {r.text}")
    atoken = r.json()["access_token"]
    ahead = {"Authorization": f"Bearer {atoken}"}

    # --- auth guards ---
    r = c.post("/admin/orders", json={})
    check("POST /admin/orders without token (401 expected)", r.status_code == 401, f"{r.status_code}")
    r = c.get("/admin/orders", headers=chead)
    check("GET /admin/orders as CUSTOMER (403 expected)", r.status_code == 403, f"{r.status_code}")

    # --- create service ---
    r = c.post(
        "/admin/services",
        headers=ahead,
        json={
            "name": f"Basic Home Cleaning {stamp}",
            "category": "express",
            "base_price": 199,
            "duration_minutes": 120,
            "addon_price_30min": 50,
            "addon_price_60min": 80,
            "overtime_grace_minutes": 15,
            "includes": ["Sweeping", "Mopping"],
        },
    )
    check("create service (admin)", r.status_code == 201, f"{r.status_code} {r.text}")
    service_id = r.json()["id"]

    r = c.get("/services")
    check("service in public catalog", r.status_code == 200 and any(s["id"] == service_id for s in r.json()),
          f"{r.status_code}")

    # --- place order ---
    when = (date.today() + timedelta(days=1)).isoformat()
    r = c.post(
        "/orders",
        headers=chead,
        json={
            "service_id": service_id,
            "scheduled_date": when,
            "scheduled_slot": "10:00 AM - 12:00 PM",
            "street": "Plot 12, MP Nagar",
            "area": "MP Nagar",
            "city": "Bhopal",
            "state": "Madhya Pradesh",
            "pincode": "462011",
            "description": "2BHK flat cleaning",
        },
    )
    check("place order (customer)", r.status_code == 201, f"{r.status_code} {r.text}")
    order = r.json()
    order_id = order["id"]
    order_code = order["order_code"]
    check("order status = requested", order["status"] == "requested", f"{order['status']}")
    check("order payment_status = unpaid", order["payment_status"] == "unpaid", f"{order['payment_status']}")

    # --- admin sees order + sets price ---
    r = c.get("/admin/orders", headers=ahead)
    check("admin sees order in feed", r.status_code == 200 and any(o["id"] == order_id for o in r.json()),
          f"{r.status_code}")

    r = c.patch(f"/admin/orders/{order_id}", headers=ahead,
                json={"estimated_hours": "3.00", "amount": "1200.00", "description": "agreed ₹1200 on call"})
    check("set estimated hours + amount (admin)", r.status_code == 200 and str(r.json()["amount"]) == "1200.00",
          f"{r.status_code} {r.text}")

    # --- status transitions (valid) ---
    for s in ["contacted", "confirmed", "in_progress", "completed"]:
        r = c.post(f"/admin/orders/{order_id}/status", headers=ahead, json={"status": s})
        check(f"status -> {s}", r.status_code == 200 and r.json()["status"] == s, f"{r.status_code} {r.text}")

    # --- invalid transition rejected ---
    r = c.post(f"/admin/orders/{order_id}/status", headers=ahead, json={"status": "requested"})
    check("invalid transition rejected (422 expected)", r.status_code == 422, f"{r.status_code}")

    # --- add addon + record payment ---
    r = c.post(f"/admin/orders/{order_id}/addons", headers=ahead,
               json={"addon_type": "60min", "price": "80.00", "quantity": 1})
    check("add 60-min add-on", r.status_code == 201, f"{r.status_code} {r.text}")

    r = c.post(f"/admin/orders/{order_id}/payments", headers=ahead,
               json={"amount": "1200.00", "method": "CASH", "status": "received", "reference": "on-site"})
    check("record payment", r.status_code == 201, f"{r.status_code} {r.text}")
    detail = r.json()
    check("payment_status = paid", detail["payment_status"] == "paid", f"{detail['payment_status']}")
    check("payment_summary shows paid", detail["payment_summary"] == "Paid ₹1200", f"{detail['payment_summary']}")

    # --- customer views own order (with events) ---
    r = c.get(f"/orders/{order_id}", headers=chead)
    check("customer views order detail", r.status_code == 200, f"{r.status_code}")
    check("order has timeline events", len(r.json()["events"]) >= 7, f"events={len(r.json()['events'])}")

    # --- public tracking by order code ---
    r = c.get(f"/orders/track/{order_code}")
    check("public track by order code", r.status_code == 200 and r.json()["order_code"] == order_code,
          f"{r.status_code} {r.text}")

    # --- day stats ---
    r = c.get("/admin/stats", headers=ahead)
    check("day stats", r.status_code == 200, f"{r.status_code}")
    if r.status_code == 200:
        check("day stats revenue reflects payment", str(r.json()["revenue"]) == "1200.00", f"{r.json()['revenue']}")

    # --- manual add-order from phone (admin intake) ---
    r = c.post(
        "/admin/orders",
        headers=ahead,
        json={
            "source": "phone",
            "customer_name": "Walk-in Client",
            "customer_phone": "9876500000",
            "service_id": service_id,
            "scheduled_date": when,
            "scheduled_slot": "02:00 PM - 04:00 PM",
            "street": "B-4, Arera Colony",
            "area": "Arera Colony",
            "pincode": "462016",
            "amount": "899.00",
            "estimated_hours": "2.00",
        },
    )
    check("manual add-order (admin, source=phone)", r.status_code == 201, f"{r.status_code} {r.text}")
    if r.status_code == 201:
        check("manual order source = phone", r.json()["source"] == "phone", f"{r.json()['source']}")

    # --- whatsapp config ---
    r = c.get("/admin/whatsapp-config", headers=ahead)
    check("get whatsapp config", r.status_code == 200, f"{r.status_code}")
    r = c.patch("/admin/whatsapp-config", headers=ahead,
                json={"support_number": "919876543210", "staff_group_link": "https://chat.whatsapp.com/abc"})
    check("update whatsapp config", r.status_code == 200, f"{r.status_code} {r.text}")

    # --- customer cancel flow (fresh order) ---
    r = c.post(
        "/orders",
        headers=chead,
        json={
            "service_id": service_id,
            "scheduled_date": when,
            "scheduled_slot": "04:00 PM - 06:00 PM",
            "street": "C-12, Kolar",
            "area": "Kolar Road",
            "pincode": "462042",
        },
    )
    if r.status_code == 201:
        cancel_id = r.json()["id"]
        r = c.post(f"/orders/{cancel_id}/cancel", headers=chead)
        check("customer cancels own order", r.status_code == 200 and r.json()["status"] == "cancelled",
              f"{r.status_code} {r.text}")

    print("\n" + "=" * 46)
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 46)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
