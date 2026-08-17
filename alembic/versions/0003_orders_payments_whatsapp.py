"""Orders, payments, add-ons, event timeline, WhatsApp config, service pricing fields.

Revision ID: 0003_orders_payments_whatsapp
Revises: 0002_business_foundation
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_orders_payments_whatsapp"
down_revision = "0002_business_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- extend services with per-service time-based pricing fields ---
    op.add_column("services", sa.Column("category", sa.String(30), nullable=False, server_default="express"))
    op.add_column("services", sa.Column("blurb", sa.String(400), nullable=True))
    op.add_column("services", sa.Column("price_max", sa.Numeric(12, 2), nullable=True))
    op.add_column("services", sa.Column("includes", postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column("services", sa.Column("excludes", postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column("services", sa.Column("addon_price_30min", sa.Numeric(12, 2), nullable=True))
    op.add_column("services", sa.Column("addon_price_60min", sa.Numeric(12, 2), nullable=True))
    op.add_column("services", sa.Column("overtime_grace_minutes", sa.Integer(), nullable=False, server_default="15"))

    # --- enums ---
    order_status = postgresql.ENUM(
        "requested", "contacted", "confirmed", "in_progress", "completed", "cancelled", name="order_status",
        create_type=False,
    )
    order_source = postgresql.ENUM("website", "phone", "whatsapp", name="order_source", create_type=False)
    payment_method = postgresql.ENUM("UPI", "CASH", name="payment_method", create_type=False)
    payment_status = postgresql.ENUM("pending", "received", name="payment_status", create_type=False)
    order_addon_type = postgresql.ENUM("30min", "60min", name="order_addon_type", create_type=False)

    order_status.create(bind, checkfirst=True)
    order_source.create(bind, checkfirst=True)
    payment_method.create(bind, checkfirst=True)
    payment_status.create(bind, checkfirst=True)
    order_addon_type.create(bind, checkfirst=True)

    # --- orders ---
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_code", sa.String(16), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_name", sa.String(160), nullable=False),
        sa.Column("source", order_source, nullable=False, server_default="website"),
        sa.Column("status", order_status, nullable=False, server_default="requested"),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=True),
        sa.Column("street", sa.String(255), nullable=False),
        sa.Column("area", sa.String(120), nullable=False),
        sa.Column("city", sa.String(100), nullable=False, server_default="Bhopal"),
        sa.Column("state", sa.String(100), nullable=False, server_default="Madhya Pradesh"),
        sa.Column("pincode", sa.String(6), nullable=False),
        sa.Column("floor", sa.String(60), nullable=True),
        sa.Column("landmark", sa.String(160), nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_slot", sa.String(60), nullable=False),
        sa.Column("estimated_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("overtime_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("order_code"),
    )
    op.create_index("ix_orders_order_code", "orders", ["order_code"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_service_id", "orders", ["service_id"])
    op.create_index("ix_orders_pincode", "orders", ["pincode"])
    op.create_index("ix_orders_scheduled_date", "orders", ["scheduled_date"])

    # --- payments ---
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", payment_method, nullable=False, server_default="UPI"),
        sa.Column("status", payment_status, nullable=False, server_default="received"),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("collected_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])

    # --- order add-ons ---
    op.create_table(
        "order_addons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("addon_type", order_addon_type, nullable=False, server_default="30min"),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_order_addons_order_id", "order_addons", ["order_id"])

    # --- order event timeline ---
    op.create_table(
        "order_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])

    # --- whatsapp config ---
    op.create_table(
        "whatsapp_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("staff_group_link", sa.String(500), nullable=True),
        sa.Column("support_number", sa.String(20), nullable=False, server_default="919876543210"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_config")
    op.drop_table("order_events")
    op.drop_table("order_addons")
    op.drop_table("payments")
    op.drop_table("orders")

    postgresql.ENUM(name="order_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="order_source").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="payment_method").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="payment_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="order_addon_type").drop(op.get_bind(), checkfirst=True)

    op.drop_column("services", "overtime_grace_minutes")
    op.drop_column("services", "addon_price_60min")
    op.drop_column("services", "addon_price_30min")
    op.drop_column("services", "excludes")
    op.drop_column("services", "includes")
    op.drop_column("services", "price_max")
    op.drop_column("services", "blurb")
    op.drop_column("services", "category")