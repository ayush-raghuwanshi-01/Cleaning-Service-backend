from uuid import UUID as _UUID

from sqlalchemy import TypeDecorator, types
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise stores as
    a string (varchar(32)) for SQLite and other backends.
    """
    impl = types.String(32)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(types.String(32))

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return value
        if isinstance(value, _UUID):
            return value.hex
        return str(value).replace("-", "")

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return value
        return _UUID(value)


class Base(DeclarativeBase):
    pass