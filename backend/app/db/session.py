from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria

from app.core.config import settings

connect_args = {}
engine_kwargs: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Pool tuning matters for Postgres only — SQLite doesn't pool. Values
    # come from env so the operator can scale at runtime without a code change.
    engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
    )

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
    **engine_kwargs,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


# ---------- Soft-delete global filter ----------
# Any Select against a SoftDeleteMixin subclass auto-filters out is_deleted=True
# unless the statement uses execution_options(include_deleted=True).

@event.listens_for(SessionLocal, "do_orm_execute")
def _filter_soft_deleted(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_deleted", False):
        return
    # Late import avoids a circular at app boot.
    from app.models.base import SoftDeleteMixin
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.is_deleted == False,  # noqa: E712
            include_aliases=True,
        )
    )


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
