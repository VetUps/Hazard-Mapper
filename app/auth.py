from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db
import crud
import schemas
from security import create_session_token, verify_session_token, SESSION_SECRET, SESSION_ALGORITHM

router = APIRouter()

# Настройки сессии
SESSION_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней


@router.post("/login")
async def login_for_session(
        response: Response,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )

    # Создаем сессионный токен
    session_token = create_session_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=SESSION_EXPIRE_MINUTES)
    )

    # Устанавливаем куки
    response.set_cookie(
        key="session_id",
        value=session_token,
        max_age=SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return {"message": "Успешный вход"}


@router.post("/logout")
async def logout(response: Response):
    # Удаляем куки
    response.delete_cookie("session_id")
    return {"message": "Успешный выход"}


def get_current_user(
        session_id: str = Depends(verify_session_token),
        db: Session = Depends(get_db)
):
    user_id = int(session_id)
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user