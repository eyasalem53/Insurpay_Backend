from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database.models import User, Role
from app.core.security import hash_password, verify_password, create_access_token
from app.auth.schemas import RegisterRequest, LoginRequest


def register_user(db: Session, payload: RegisterRequest):
    existing_user = db.query(User).filter(User.email == payload.email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    default_role = db.query(Role).filter(Role.name == "USER").first()

    if not default_role:
        default_role = Role(name="USER")
        db.add(default_role)
        db.commit()
        db.refresh(default_role)

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role_id=default_role.id,
        is_active=False,
        account_status="PENDING",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def login_user(db: Session, payload: LoginRequest):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.account_status == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte est en attente d'approbation par l'administrateur.",
        )

    if user.account_status == "BANNED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte a été suspendu. Veuillez contacter l'administrateur.",
        )

    if user.account_status != "APPROVED" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte n'est pas autorisé à accéder à la plateforme.",
        )

    token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role.name if user.role else None,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
    }