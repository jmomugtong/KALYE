"""Row Level Security policies for multi-tenant data isolation

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable RLS on user-owned tables
    op.execute("ALTER TABLE images ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_feedbacks ENABLE ROW LEVEL SECURITY")

    # Create app role for API connections (least privilege)
    op.execute("""
        DO $$ BEGIN
            CREATE ROLE kalye_app LOGIN PASSWORD 'kalye_app_pw_change_in_prod';
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("GRANT CONNECT ON DATABASE kalye TO kalye_app")
    op.execute("GRANT USAGE ON SCHEMA public TO kalye_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kalye_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kalye_app")

    # images: users can only SELECT/UPDATE/DELETE their own rows
    # Admins (role='admin') can see all
    op.execute("""
        CREATE POLICY images_owner_policy ON images
            USING (
                user_id::text = current_setting('app.current_user_id', true)
                OR current_setting('app.current_user_role', true) = 'admin'
            )
    """)

    # Public SELECT on detections (read-only map data)
    op.execute("ALTER TABLE detections ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY detections_public_read ON detections
            FOR SELECT USING (true)
    """)
    op.execute("""
        CREATE POLICY detections_owner_write ON detections
            FOR ALL USING (
                image_id IN (
                    SELECT image_id FROM images
                    WHERE user_id::text = current_setting('app.current_user_id', true)
                )
                OR current_setting('app.current_user_role', true) = 'admin'
            )
    """)

    # user_feedbacks: users can only see/modify their own
    op.execute("""
        CREATE POLICY feedbacks_owner_policy ON user_feedbacks
            USING (
                user_id::text = current_setting('app.current_user_id', true)
                OR current_setting('app.current_user_role', true) = 'admin'
            )
    """)

    # walkability_scores and locations: public read-only
    op.execute("ALTER TABLE walkability_scores ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE locations ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY scores_public_read ON walkability_scores FOR SELECT USING (true)")
    op.execute("CREATE POLICY locations_public_read ON locations FOR SELECT USING (true)")


def downgrade() -> None:
    for table in ("images", "user_feedbacks", "detections", "walkability_scores", "locations"):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for policy, table in [
        ("images_owner_policy", "images"),
        ("detections_public_read", "detections"),
        ("detections_owner_write", "detections"),
        ("feedbacks_owner_policy", "user_feedbacks"),
        ("scores_public_read", "walkability_scores"),
        ("locations_public_read", "locations"),
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
