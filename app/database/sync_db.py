from sqlalchemy import inspect, text
from app.database.session import engine
from app.database.models import Base


from sqlalchemy import inspect, text
from app.database.session import engine
from app.database.models import Base


def sync_database():
    # Create missing tables
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

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

        if "date_naissance" not in existing_user_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN date_naissance DATE
                    """
                )
            )

        if "phone_number" not in existing_user_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN phone_number VARCHAR(30)
                    """
                )
            )

        if "num_adherent" not in existing_user_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN num_adherent VARCHAR(100)
                    """
                )
            )

        if "address" not in existing_user_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN address TEXT
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