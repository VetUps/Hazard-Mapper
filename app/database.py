from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "mysql+mysqlconnector://root:1234@localhost/hazard_mapper_db"

 # Создаём движок
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(
    autocommit=False, # Ручное управление транзакциями
    autoflush=False, # Отключение авто синхронизацию с изменениями с БД
    bind=engine # Привязываем движок
)

# Базовый класс для всех ORM-моделей (таблиц БД)
Base = declarative_base()

# Генератор сессий БД, чтобы у каждого API-запроса была своя
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()