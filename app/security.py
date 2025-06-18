from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends, Cookie
from typing import Optional

# Настройки сессии
SESSION_SECRET = "secretik"  # Замените на случайную строку
SESSION_ALGORITHM = "HS256"

def create_session_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SESSION_SECRET, algorithm=SESSION_ALGORITHM)

def verify_session_token(session_id: Optional[str] = Cookie(None)):
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )
    try:
        payload = jwt.decode(session_id, SESSION_SECRET, algorithms=[SESSION_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=400, detail="Некорректный токен")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")