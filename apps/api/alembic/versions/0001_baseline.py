"""Baseline schema (M0-M10) plus the append-only guard on audit_events.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-23

The baseline is created from the model metadata so that it cannot drift from
the models at the moment of the first deploy. Every later schema change must be
a normal, explicit migration (`alembic revision --autogenerate -m ...`, then
review the generated file).
"""
from alembic import op

from echominer.models import Base

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_AUDIT_GUARD = """
CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events;
CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_append_only();
"""


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute(_AUDIT_GUARD)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events;")
        op.execute("DROP FUNCTION IF EXISTS audit_events_append_only();")
    Base.metadata.drop_all(bind=bind)
