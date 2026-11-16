"""Separate unsubmitted vaccination records from records awaiting review."""

from alembic import op

revision = "2026_11_15_0100"
down_revision = "2026_09_28_0400"
branch_labels = None
depends_on = None


def upgrade():
    # The enum labels already exist from the initial schema. The prior status
    # normalization collapsed them in application code and converted old rows.
    op.execute(
        "UPDATE student_vaccine_doses "
        "SET status = 'PENDING' "
        "WHERE status = 'IN_REVIEW' AND applied_date IS NULL AND is_active IS TRUE"
    )

    # Restore only untouched aggregate rows. Reviewed or mixed clinical records
    # are left intact; later dose edits recalculate those aggregates.
    op.execute(
        "UPDATE student_vaccines AS sv "
        "SET status = 'PENDING' "
        "WHERE sv.status = 'IN_REVIEW' "
        "AND sv.is_active IS TRUE "
        "AND sv.reviewed_by IS NULL AND sv.reviewed_at IS NULL AND sv.admin_notes IS NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM student_vaccine_doses AS d "
        "  WHERE d.student_vaccine_id = sv.id AND d.is_active IS TRUE "
        "  AND (d.status <> 'PENDING' OR d.applied_date IS NOT NULL)"
        ")"
    )


def downgrade():
    op.execute(
        "UPDATE student_vaccines AS sv "
        "SET status = 'IN_REVIEW' "
        "WHERE sv.status = 'PENDING' "
        "AND sv.is_active IS TRUE "
        "AND sv.reviewed_by IS NULL AND sv.reviewed_at IS NULL AND sv.admin_notes IS NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM student_vaccine_doses AS d "
        "  WHERE d.student_vaccine_id = sv.id AND d.is_active IS TRUE "
        "  AND (d.status <> 'PENDING' OR d.applied_date IS NOT NULL)"
        ")"
    )
    op.execute(
        "UPDATE student_vaccine_doses "
        "SET status = 'IN_REVIEW' "
        "WHERE status = 'PENDING' AND applied_date IS NULL AND is_active IS TRUE"
    )
