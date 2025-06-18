from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, engine
import models
import schemas
import crud
import security
from datetime import timedelta
import os

app = FastAPI()

# Настройки
SESSION_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создание таблиц
models.Base.metadata.create_all(bind=engine)


@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user)


@app.post("/login")
async def login(
        response: Response,
        user: schemas.UserLogin,
        db: Session = Depends(get_db)
):
    db_user = crud.authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_token = security.create_session_token(
        data={"sub": str(db_user.id)},
        expires_delta=timedelta(minutes=SESSION_EXPIRE_MINUTES)
    )

    response.set_cookie(
        key="session_id",
        value=session_token,
        max_age=SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,  # True in production
        samesite="lax",
    )

    return {"message": "Login successful"}


@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session_id")
    return {"message": "Logout successful"}


@app.get("/users/me", response_model=schemas.User)
async def get_current_user(
        session_id: str = Depends(lambda: None),
        db: Session = Depends(get_db)
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = security.verify_session_token(session_id)
    user = crud.get_user(db, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/protected")
async def protected_route(user: schemas.User = Depends(get_current_user)):
    return {"message": f"Hello {user.username}, this is protected!"}