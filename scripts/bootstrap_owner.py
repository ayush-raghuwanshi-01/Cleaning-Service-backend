"""Create the first Home Shine OWNER account from local environment variables."""

import asyncio
import sys
from pathlib import Path

# Allow `python scripts/bootstrap_owner.py` from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import AuditLog, User, UserRole


async def main() -> None:
    settings = get_settings()
    values = {
        "BOOTSTRAP_OWNER_NAME": settings.bootstrap_owner_name,
        "BOOTSTRAP_OWNER_PHONE": settings.bootstrap_owner_phone,
        "BOOTSTRAP_OWNER_PASSWORD": settings.bootstrap_owner_password,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    async with SessionLocal() as session:
        existing_owner = await session.scalar(select(User).where(User.role == UserRole.OWNER))
        if existing_owner:
            raise SystemExit("An OWNER account already exists; bootstrap is intentionally blocked.")
        phone = settings.bootstrap_owner_phone
        email = settings.bootstrap_owner_email
        duplicate_conditions = [User.phone == phone]
        if email:
            duplicate_conditions.append(User.email == email.lower())
        duplicate = await session.scalar(select(User).where(or_(*duplicate_conditions)))
        if duplicate:
            raise SystemExit("The bootstrap phone number or email is already registered.")
        owner = User(full_name=settings.bootstrap_owner_name, phone=phone, email=email.lower() if email else None, password_hash=hash_password(settings.bootstrap_owner_password), role=UserRole.OWNER)
        session.add(owner)
        await session.flush()
        session.add(AuditLog(actor_id=owner.id, action="owner_bootstrapped", entity_type="user", entity_id=str(owner.id)))
        await session.commit()
    print("OWNER account created. Remove BOOTSTRAP_OWNER_* variables now.")


if __name__ == "__main__":
    asyncio.run(main())
