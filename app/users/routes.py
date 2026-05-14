from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import User, Role
from app.auth.dependencies import require_admin

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


def serialize_user(user: User):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "is_active": user.is_active,
        "account_status": user.account_status,
        "role": user.role.name if user.role else None,
        "created_at": user.created_at
    }


@router.get("/")
def get_all_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    users = db.query(User).order_by(User.id.desc()).all()
    return [serialize_user(user) for user in users]


@router.get("/pending")
def get_pending_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    users = (
        db.query(User)
        .filter(User.account_status == "PENDING")
        .order_by(User.id.desc())
        .all()
    )

    return [serialize_user(user) for user in users]


@router.patch("/{user_id}/approve")
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    user.account_status = "APPROVED"
    user.is_active = True

    db.commit()
    db.refresh(user)

    return {
        "message": "Utilisateur approuvé avec succès",
        "user": serialize_user(user)
    }


@router.delete("/{user_id}/reject")
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    if user.role and user.role.name == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de rejeter un administrateur"
        )

    db.delete(user)
    db.commit()

    return {
        "message": "Demande d'inscription rejetée avec succès"
    }


@router.patch("/{user_id}/ban")
def ban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas bannir votre propre compte"
        )

    user.account_status = "BANNED"
    user.is_active = False

    db.commit()
    db.refresh(user)

    return {
        "message": "Utilisateur banni avec succès",
        "user": serialize_user(user)
    }


@router.patch("/{user_id}/unban")
def unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    user.account_status = "APPROVED"
    user.is_active = True

    db.commit()
    db.refresh(user)

    return {
        "message": "Utilisateur débanni avec succès",
        "user": serialize_user(user)
    }


@router.patch("/{user_id}/promote")
def promote_to_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    admin_role = db.query(Role).filter(Role.name == "ADMIN").first()

    if not admin_role:
        admin_role = Role(name="ADMIN")
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)

    user.role_id = admin_role.id

    db.commit()
    db.refresh(user)

    return {
        "message": "Utilisateur promu administrateur avec succès",
        "user": serialize_user(user)
    }


@router.patch("/{user_id}/demote")
def demote_to_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas rétrograder votre propre compte"
        )

    user_role = db.query(Role).filter(Role.name == "USER").first()

    if not user_role:
        user_role = Role(name="USER")
        db.add(user_role)
        db.commit()
        db.refresh(user_role)

    user.role_id = user_role.id

    db.commit()
    db.refresh(user)

    return {
        "message": "Utilisateur rétrogradé avec succès",
        "user": serialize_user(user)
    }