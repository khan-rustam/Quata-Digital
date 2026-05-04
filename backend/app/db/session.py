from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria

from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
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
