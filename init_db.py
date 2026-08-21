"""Initialize the database with all models and seed data."""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User, UserRole, AuditLog
from app.models.business import Service, ServiceArea
from app.models.order import Order, OrderAddon, OrderEvent, Payment, WhatsAppConfig
from app.models.staff import Staff, StaffAssignment
from app.models.recurring import RecurringOrder


async def init():
    settings = get_settings()

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created")

    # Check if already seeded
    async with SessionLocal() as session:
        existing = await session.scalar(select(User).limit(1))
        if existing:
            print("✓ Database already has data, skipping seed")
            return

        # Seed default WhatsApp config
        wc = WhatsAppConfig(id=1, support_number="919876543210")
        session.add(wc)

        # Seed service areas from defaults
        default_areas = [
            ("MP Nagar", "462011"),
            ("Minal", "462021"),
            ("JK Road", "462023"),
            ("Avadhpuri", "462044"),
            ("Indrapuri", "462022"),
            ("Patel Nagar", "462024"),
            ("Ayodhya By Pass", "462041"),
            ("Ayodhya Nagar", "462042"),
            ("Ashoka Garden", "462033"),
        ]
        for name, pincode in default_areas:
            session.add(ServiceArea(name=name, pincode=pincode, is_active=True))
        print(f"✓ Seeded {len(default_areas)} default service areas")

        # Seed a basic service
        session.add(Service(
            name="Standard Home Cleaning",
            category="express",
            description="Complete home cleaning service including sweeping, mopping, and dusting.",
            blurb="Perfect for regular home maintenance",
            base_price=499,
            duration_minutes=120,
            includes=["Sweeping", "Mopping", "Dusting", "Kitchen wipe-down"],
            excludes=["Deep carpet cleaning", "Window exteriors"],
            addon_price_30min=50,
            addon_price_60min=80,
            overtime_grace_minutes=15,
            is_active=True,
        ))
        session.add(Service(
            name="Deep Cleaning",
            category="packages",
            description="Thorough deep cleaning for every room in your home.",
            blurb="Complete home makeover",
            base_price=1999,
            price_max=4999,
            duration_minutes=240,
            includes=["All standard cleaning", "Carpet shampoo", "Window cleaning", "Cabinet cleaning"],
            excludes=["Pest control", "Paint touch-ups"],
            addon_price_30min=75,
            addon_price_60min=120,
            overtime_grace_minutes=15,
            is_active=True,
        ))
        print("✓ Seeded services")

        # Bootstrap owner if configured
        if settings.bootstrap_owner_name and settings.bootstrap_owner_phone and settings.bootstrap_owner_password:
            owner = User(
                full_name=settings.bootstrap_owner_name,
                phone=settings.bootstrap_owner_phone,
                email=settings.bootstrap_owner_email,
                password_hash=hash_password(settings.bootstrap_owner_password),
                role=UserRole.OWNER,
            )
            session.add(owner)
            session.add(AuditLog(actor_id=owner.id, action="system_bootstrap", entity_type="user", entity_id=str(owner.id)))
            print(f"✓ Bootstrapped owner: {settings.bootstrap_owner_name} ({settings.bootstrap_owner_phone})")

        await session.commit()
        print("✓ Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(init())