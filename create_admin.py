from app.database.session import SessionLocal
from app.database.models import User, Role
from app.core.security import hash_password


ADMIN_FULL_NAME = "Admin InsurPay"
ADMIN_EMAIL = "admin@insurpay.com"
ADMIN_PASSWORD = "admin123"


def create_admin():
    db = SessionLocal()

    try:
        admin_role = db.query(Role).filter(Role.name == "ADMIN").first()

        if not admin_role:
            admin_role = Role(name="ADMIN")
            db.add(admin_role)
            db.commit()
            db.refresh(admin_role)

        user_role = db.query(Role).filter(Role.name == "USER").first()

        if not user_role:
            user_role = Role(name="USER")
            db.add(user_role)
            db.commit()

        existing_admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()

        if existing_admin:
            existing_admin.full_name = ADMIN_FULL_NAME
            existing_admin.hashed_password = hash_password(ADMIN_PASSWORD)
            existing_admin.role_id = admin_role.id
            existing_admin.is_active = True
            existing_admin.account_status = "APPROVED"

            db.commit()
            print("Admin account updated successfully.")
            return

        admin = User(
            full_name=ADMIN_FULL_NAME,
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role_id=admin_role.id,
            is_active=True,
            account_status="APPROVED"
        )

        db.add(admin)
        db.commit()

        print("Admin account created successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()