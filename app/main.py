from fastapi import FastAPI, Depends, HTTPException, status, Response, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Cookie, File, Form
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from app.database import get_db, engine
from app import models, schemas, crud, security
from app.utils import gpx_utils
from datetime import timedelta
import base64
import os
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.utils.fire_risk_service import generate_risk_map

# Инициализация API
app = FastAPI()

# Настройки
SESSION_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# CORS (для того, чтобы можно было отправлять запросы с браузера)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Разрешает запросы только с указанных origins
    allow_credentials=True, # Разрешает передачу cookies
    allow_methods=["*"], # Разраешает все HTTP-методы (GET, POST и т.д.)
    allow_headers=["*"], # Разраешает все заголовки
)

templates = Jinja2Templates(directory="app/templates")


@app.post("/register", response_model=schemas.User)
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Эндпоинт для регистрации нового юзера
    :param user: данные нового пользователя
    :param db: сессия с БД
    :return: данные зарегистрированного пользователя
    """
    # Проверяем уникальность почты
    db_user = crud.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Почта уже существует")

    db_user = crud.get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Никнейм уже занят")
    # Регистрируем пользователя
    return crud.create_user(db, user)


@app.post("/login")
async def login(
        response: Response,
        user: schemas.UserLogin,
        db: Session = Depends(get_db)
):
    """
    Эндпоинт для авторизации пользователя с установкой JWT токена в куки
    :param response: объект, создаваемый FastAPI для установки дополнительных параметров к ответу
    :param user: авторизовывающийся пользователь
    :param db: сессия с БД
    :return: response с дополнительным сообщением
    """
    # Проверка авторизации
    db_user = crud.authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверные данные")

    if not db_user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь деактивирован!")

    # Если авторизация удалась, то генерируем JWT токен
    session_token = security.create_session_token(
        data={"sub": str(db_user.id)},
        expires_delta=timedelta(minutes=SESSION_EXPIRE_MINUTES)
    )

    # Устанавливаем его в куки
    response.set_cookie(
        key="session_id",
        value=session_token,
        max_age=SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,  # True in production
        samesite="lax",
    )

    # Возвращаем response
    return {"message": "Успешный вход"}


@app.post("/logout")
async def logout(response: Response):
    """
    Эндпоинт для выхода с аккаунта пользователя
    :param response: response: объект, создаваемый FastAPI для установки дополнительных параметров к ответу
    :return: response с дополнительным сообщением
    """
    # Отчищаем куки
    response.delete_cookie("session_id")
    # Возвращаем response
    return {"message": "Успешный выход"}


@app.get("/users/me", response_model=schemas.User)
async def get_current_user(
        session_id: str = Cookie(default=None),
        db: Session = Depends(get_db)
):
    """
    Эндпоинт для получения текущего авторизованного пользователя
    :param session_id: название куки
    :param db: сессия с БД
    :return: пользователь без пароля
    """
    # Если куки не установлены, то вызваем ошибку
    if not session_id:
        return None

    # Иначе находим и возвращаем пользователя
    user_id = security.verify_session_token(session_id)
    user = crud.get_user(db, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@app.put("/users/me", response_model=schemas.User)
async def update_current_user(
        user_data: schemas.UserUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для обновления профиля пользователя
    :param user_data: новые данные о пользователе
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: обновлённый пользователь
    """
    # Проверка уникальности email
    if user_data.email and user_data.email != current_user.email:
        existing_user = crud.get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Пользователь с такой почтой уже существует")

    # Проверка уникальности username
    if user_data.username and user_data.username != current_user.username:
        existing_user = crud.get_user_by_username(db, user_data.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="Пользователь с таким ником ежуе существует")

    # Обновляем поля
    current_user = crud.update_user(db, user_data, current_user)
    return current_user

@app.put("/admin/users/{user_id}/active", response_model=schemas.User)
async def update_user_active(
        user_id: int,
        active_data: schemas.UserActiveUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для обновления статуса пользователя
    :param user_id: id обновляемого пользователя
    :param active_data: нова информация о пользователе
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: пользователь с новыми данными
    """
    # Проверяем является ли текущий пользователь админом или владельцем аккаунта
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Обновляем данные пользователя, если такой существует
    user = crud.update_user_active(db, user_id, active_data.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return user

@app.get("/users/{user_id}", response_model=schemas.User)
async def get_user_data(user_id: int, db: Session = Depends(get_db)):
    """
    Эндпоинт для получения данных о пользователе
    :param user_id: id пользователя
    :param db: сессия БД
    :return: пользователь
    """
    # Получаем данные о пользователе
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    # Возвращаем, если такой пользователь существует
    return user


@app.get("/users/me/tracks", response_model=schemas.TrackPaginate)
async def get_current_user_tracks(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        skip: int = Query(0, ge=0, description="Количество пропускаемых записей"),
        limit: int = Query(10, le=100, description="Максимальное количество записей"),
):
    """
    Эндпоинт для получения треков текущего пользователя с настройками
    :param db: сессия БД
    :param current_user: текущий пользователь
    :param skip: количество пропускаемых записей
    :param limit: максимальное количество записей
    :return:
    """
    # Получаем треки текущего пользователя с настройками и их общее количество в БД
    tracks = crud.get_tracks_by_user(db, current_user.id, skip, limit)
    total_tracks = db.query(models.Track).filter(models.Track.user_id == current_user.id).count()

    return {
        "tracks": tracks,
        "total": total_tracks,
        "skip": skip,
        "limit": limit
    }

@app.get("/admin/users", response_model=schemas.UserPaginate)
async def get_all_users(
        skip: int = Query(0, ge=0, description="Количество пропускаемых записей"),
        limit: int = Query(10, le=100, description="Максимальное количество записей"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для получения пользователей с настройками
    :param skip: количество пропускаемых записей
    :param limit: максимальное количество записей
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: список пользователей
    """
    # Если текущий пользователь не админ, то не пропускаем дальше
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Получаем пользователей и их общее количество в БД
    users = crud.get_all_users(db, skip, limit, current_user.id)
    total = db.query(models.User).count()

    return {
        "users": users,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@app.get("/tracks/load", response_model=schemas.TrackPaginate)
async def get_all_tracks(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user, use_cache=False),
        skip: int = Query(0, ge=0, description="Количество пропускаемых записей"),
        limit: int = Query(10, le=100, description="Максимальное количество записей"),
):
    """
    Эндпоинт для получения треков с настройками
    :param db: сессия БД
    :param current_user: текущий пользователь
    :param skip: количество пропускаемых записей
    :param limit: максимальное количество записей
    :return: список треков
    """
    # Получаем треки с заданными параметрами
    tracks = crud.get_tracks(db, skip=skip, limit=limit)
    # Считаем общее количество треков в БД
    total_tracks = db.query(models.Track).count()

    # Добавляем флаг избранного для авторизованных пользователей
    if current_user:
        for track in tracks:
            track.is_favorite = crud.is_favorite(db, current_user.id, track.id)
    else:
        # Для неавторизованных устанавливаем false
        for track in tracks:
            track.is_favorite = False

    return {
        "tracks": tracks,
        "total": total_tracks,
        "skip": skip,
        "limit": limit
    }


@app.post("/tracks/upload")
async def upload_track(
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для загрузки нового трека
    :param title: название трека
    :param description: описание трека
    :param file: .gpx файл трека
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: информация о треке
    """
    # Проверка формата файла
    if not file.filename.endswith('.gpx'):
        raise HTTPException(400, "Неверный формат файла (Только .gpx)")

    if not title:
        raise HTTPException(400, "Название не может быть пустым")

    # Чтение и парсинг GPX
    contents = await file.read()
    points, stats = gpx_utils.parse_gpx(contents.decode('utf-8'))

    if len(points) == 0:
        raise HTTPException(400, "Трек должен иметь хотя бы одну координату")

    # Генерация изображения
    image = bytes(1)#gpx_utils.generate_track_image(points)
    region = gpx_utils.get_track_region(points)

    # Создание объекта трека
    track_data_for_create = schemas.TrackCreate(
        title=title,
        description=description,
        region=region,
        total_distance=stats["total_distance"],
        elevation_gain=stats["elevation_gain"],
        difficulty=stats["difficulty"],
    )

    # Создание трека в БД
    track = crud.create_track_with_points(
        db,
        track_data_for_create,
        points,
        image,
        current_user.id
    )

    return {
        "track": track,
        "points": points,
        "stats": stats
    }


@app.get("/tracks/{track_id}", response_model=schemas.TrackDetail)
async def get_track_details(track_id: int, db: Session = Depends(get_db)):
    """
    Эндпоинт для получения детальной информации о треке
    :param track_id: id трека
    :param db: сессия БД
    :return:
    """
    # Получаем детальную информацию
    track = crud.get_track_with_details(db, track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return track


@app.put("/tracks/{track_id}", response_model=schemas.Track)
async def update_track(
        track_id: int,
        track_data: schemas.TrackUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для изменения данных о треке
    :param track_id: id трека
    :param track_data: новая информация о треке
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return:
    """
    # Проверяем, что трек существует и принадлежит пользователю или пользователь админ
    track = crud.get_track(db, track_id)
    if not track or (track.user_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="Трек не найден или у вас нет прав")

    if not track_data.title:
        raise HTTPException(400, "Название не может быть пустым")

    # Обновляем данные трека
    updated_track = crud.update_track(db, track_id, track_data)
    if not updated_track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    return updated_track


@app.delete("/tracks/{track_id}")
async def delete_track(
        track_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для удаления трека
    :param track_id: id трека
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: сообщение о статусе
    """
    # Получаем трек из БД
    track = crud.get_track(db, track_id)

    # Проверяем, что трек принадлежит пользователю или пользователь админ
    if not track or (track.user_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="Отказано в доступе")

    # Удаляем трек и все связанные данные
    crud.delete_track(db, track_id)

    return {"message": "Трек успешно удалён"}


@app.post("/tracks/{track_id}/favorite", response_model=schemas.Track)
async def favorite_track(
        track_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для добавления трека в избранное
    :param track_id: id трека
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: добавленный трек
    """
    # Получаем трек из БД
    track = crud.get_track(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    # Добавляем в избранное текущего пользователя, если такой трек есть
    crud.add_to_favorites(db, current_user.id, track_id)
    # Обновляем флаг избранного
    track.is_favorite = True
    return track


@app.delete("/tracks/{track_id}/favorite", response_model=schemas.Track)
async def unfavorite_track(
        track_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для удаления трека из избранного
    :param track_id: id трека
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: удалённый трек
    """
    # Получаем трек из БД
    track = crud.get_track(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")

    # Удаляем из избранного текущего пользователя, если такой трек есть
    crud.remove_from_favorites(db, current_user.id, track_id)
    # Обновляем флаг избранного
    track.is_favorite = False
    return track

@app.post("/tracks/{track_id}/comments", response_model=schemas.Comment)
async def create_comment(
    track_id: int,
    comment_data: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Эндпоинт для создания комментария к треку
    :param track_id: id трека
    :param comment_data: содержимое комментария
    :param db: сессия БД
    :param current_user: текущий пользователь
    :return: полная информация ок комментарии
    """
    # Создаём комментарий
    db_comment = crud.create_comment(db, comment_data, current_user.id, track_id)
    return db_comment

@app.get("/favorites", response_model=schemas.TrackPaginate)
async def get_favorite_tracks(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        skip: int = Query(0, ge=0, description="Количество пропускаемых записей"),
        limit: int = Query(10, le=100, description="Максимальное количество записей"),
):
    """
    Эндпоинт для получения избранных треков пользователя
    :param db: сессия БД
    :param current_user: текущий пользователь
    :param skip: количество пропускаемых записей
    :param limit: максимальное количество записей
    :return: избранные треки и настройки пагинации
    """
    tracks = crud.get_favorite_tracks(db, current_user.id, skip, limit)
    total_tracks = db.query(models.Favorite).filter(
        models.Favorite.user_id == current_user.id
    ).count()

    for track in tracks:
        track.is_favorite = True

    return {
        "tracks": tracks,
        "total": total_tracks,
        "skip": skip,
        "limit": limit
    }

@app.get("/tracks/{track_id}/fire_risk", response_class=HTMLResponse)
async def get_fire_risk_map(
    request: Request,
    track_id: int,
    db: Session = Depends(get_db)
):
    """
    Эндпоинт для получения карты с оценкой пожароопасности для трека
    :param request: запрос
    :param track_id: id трека для которого делается оценка
    :param db: сессия БД
    :return: HTML код карты
    """

    try:
        # Генерируем HTML карты
        map_html = generate_risk_map(track_id, db)

        # Возвращаем полноценную HTML страницу
        return templates.TemplateResponse(
            "fire_risk.html",
            {
                "request": request,
                "map_html": map_html,
                "track_id": track_id
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)