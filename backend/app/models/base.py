import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    def __init_subclass__(cls, **kw):
        if not cls.__dict__.get('__abstract__') and '__tablename__' in cls.__dict__:
            args = cls.__dict__.get('__table_args__')
            if args is None:
                cls.__table_args__ = {'extend_existing': True}
            elif isinstance(args, dict):
                if 'extend_existing' not in args:
                    cls.__table_args__ = {**args, 'extend_existing': True}
            elif isinstance(args, tuple):
                if args and isinstance(args[-1], dict):
                    if 'extend_existing' not in args[-1]:
                        cls.__table_args__ = args[:-1] + ({**args[-1], 'extend_existing': True},)
                else:
                    cls.__table_args__ = args + ({'extend_existing': True},)
        super().__init_subclass__(**kw)


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Creation time"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Last update time"
    )
