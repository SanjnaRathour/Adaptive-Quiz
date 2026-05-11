"""dedupe and constrain in_progress attempts

Make it impossible to have two IN_PROGRESS attempts for the same
(student_id, quiz_id) pair. Closes a race in start_attempt where two
near-simultaneous requests both pass the "is there an IN_PROGRESS?" check
and both INSERT a fresh row.

Revision ID: 427047d5f0d2
Revises: 3a2437032600
Create Date: 2026-05-08 18:32:53.572127

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "427047d5f0d2"
down_revision: str | None = "3a2437032600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Dedupe existing rows: for each (quiz_id, student_id) with multiple
    #    IN_PROGRESS attempts, keep the most recently-created one and mark
    #    the rest ABANDONED so the unique index can be created.
    op.execute(
        """
        UPDATE quiz_attempts
        SET status = 'ABANDONED',
            completed_at = COALESCE(completed_at, NOW())
        WHERE status = 'IN_PROGRESS'
          AND id NOT IN (
              SELECT DISTINCT ON (quiz_id, student_id) id
              FROM quiz_attempts
              WHERE status = 'IN_PROGRESS'
              ORDER BY quiz_id, student_id, created_at DESC
          )
        """
    )

    # 2. Partial unique index — at most one IN_PROGRESS row per (quiz, student).
    op.create_index(
        "uq_in_progress_attempt",
        "quiz_attempts",
        ["quiz_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'IN_PROGRESS'"),
    )


def downgrade() -> None:
    op.drop_index("uq_in_progress_attempt", table_name="quiz_attempts")
