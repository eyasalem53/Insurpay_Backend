from sqlalchemy import inspect, text
from app.database.session import engine
from app.database.models import Base


def sync_database():
    # Create missing tables
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    # Add missing columns manually
    existing_user_columns = [
        column["name"] for column in inspector.get_columns("users")
    ]

    with engine.begin() as connection:
        if "account_status" not in existing_user_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN account_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
                    """
                )
            )

        if "is_active" not in existing_user_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE
                    """
                )
            )

        # Seed default roles
        connection.execute(
            text(
                """
                INSERT INTO roles (name)
                VALUES ('ADMIN'), ('USER')
                ON CONFLICT (name) DO NOTHING
                """
            )
        )