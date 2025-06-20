from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends, Cookie
from typing import Optional

# Настройки сессии
SESSION_SECRET = "secretik" # Устанавливаем секрет JWT токена
SESSION_ALGORITHM = "HS256" # Алгоритм шифрования

def create_session_token(data: dict, expires_delta: timedelta = None):
    """
    Создаёт JWT токен с указанными данными и временем действия
    :param data: данные для записи в токен
    :param expires_delta: время действия токена (по умолчанию 15 минут)
    :return: JWT токен
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SESSION_SECRET, algorithm=SESSION_ALGORITHM)

def verify_session_token(session_id: Optional[str] = Cookie(None)):
    """
    Проверяет токен
    :param session_id: Куки с именем session_id
    :return: id пользователя либо ошибка
    """

    # Если куки не установлены рейзим ошибку
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )
    try:
        # Декодируем JWT токен
        payload = jwt.decode(session_id, SESSION_SECRET, algorithms=[SESSION_ALGORITHM])
        # Достаём от туда id пользователя
        user_id: str = payload.get("sub")
        # Если не удаётся, то рейзим ошибку либо возвращаем user id
        if user_id is None:
            raise HTTPException(status_code=400, detail="Некорректный токен")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")