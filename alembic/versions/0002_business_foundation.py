"""Phase 2 service catalog, areas, and addresses.

Revision ID: 0002_business_foundation
Revises: 0001_phase_one_auth_foundation
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_business_foundation"
down_revision = "0001_phase_one_auth_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("service_areas", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("pincode", sa.String(6), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.UniqueConstraint("name"), sa.UniqueConstraint("pincode", name="uq_service_areas_pincode"))
    op.create_index("ix_service_areas_pincode", "service_areas", ["pincode"])
    op.create_table("services", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()), sa.Column("base_price", sa.Numeric(12, 2), nullable=False), sa.Column("duration_minutes", sa.Integer(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.UniqueConstraint("name"))
    op.create_table("service_addons", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()), sa.Column("price", sa.Numeric(12, 2), nullable=False), sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.create_index("ix_service_addons_service_id", "service_addons", ["service_id"])
    op.create_table("addresses", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("label", sa.String(60), nullable=False), sa.Column("recipient_name", sa.String(120), nullable=False), sa.Column("recipient_phone", sa.String(20), nullable=False), sa.Column("line1", sa.String(255), nullable=False), sa.Column("line2", sa.String(255)), sa.Column("landmark", sa.String(160)), sa.Column("city", sa.String(100), nullable=False), sa.Column("state", sa.String(100), nullable=False), sa.Column("pincode", sa.String(6), nullable=False), sa.Column("service_area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_areas.id", ondelete="SET NULL")), sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])
    op.create_index("ix_addresses_pincode", "addresses", ["pincode"])


def downgrade() -> None:
    op.drop_table("addresses")
    op.drop_table("service_addons")
    op.drop_table("services")
    op.drop_table("service_areas")
