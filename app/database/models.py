from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import Double, String, Text, Boolean, DateTime, Enum, ForeignKey, select
from config import ALLOWED_USERS, ADMIN_USERS, BASE_ADMIN, MODELS_IN_USE
import datetime
import enum
from pathlib import Path

# Используем SQLite3 в асинхронном режиме
engine = create_async_engine(url = "sqlite+aiosqlite:///db/telebot.db")

async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_username: Mapped[str] = mapped_column(String(32), unique=True)
    has_admin_priviliges: Mapped[bool] = mapped_column(Boolean)

class User_Requests(Base):
    __tablename__ = "user_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ai_model: Mapped[str] = mapped_column(ForeignKey("ai_models.model_name", ondelete="RESTRICT"))
    money_spent: Mapped[float] = mapped_column(Double(6))
    date: Mapped[datetime.datetime] = mapped_column(DateTime)

class Ai_model_types(enum.Enum):
    text = "text"
    image = "image"
    video = "video"
    audio = "audio"

class AI_models(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(Text, unique=True)
    model_type: Mapped[enum.Enum] = mapped_column(Enum(Ai_model_types))
    input_price: Mapped[float] = mapped_column(Double(6))
    input_cached_price: Mapped[float] = mapped_column(Double(6), nullable=True)
    output_price: Mapped[float] = mapped_column(Double(6))
    description: Mapped[str] = mapped_column(Text)

async def get_allowed_users() -> set[str]:
    '''
    Получает множество пользователей, у которых есть доступ к боту.
    '''
    async with async_session() as session:
        allowed_users = await session.scalars(select(User.tg_username))
        return set(allowed_users)

async def get_admins() -> set[str]:
    '''
    Получает множество пользователей, у которых есть права администратора.
    '''
    async with async_session() as session:
        admin_users = await session.scalars(select(User.tg_username).where(User.has_admin_priviliges))
    return set(admin_users)

async def async_main():
    '''
    Запускает базу данных и создаёт её. Также обновляет множество пользователей.
    '''
    Path("db").mkdir(exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    registered_users = await get_allowed_users()
    admins = await get_admins()
    async with async_session() as session:
        await session.execute(insert(User).values(tg_username = BASE_ADMIN, has_admin_priviliges = True).on_conflict_do_nothing(index_elements = ["tg_username"]))
        await session.commit()
        await session.execute(insert(AI_models).values(MODELS_IN_USE).on_conflict_do_nothing(index_elements = ["model_name"]))
        await session.commit()
    ALLOWED_USERS.update(registered_users)
    ADMIN_USERS.update(admins)


async def close_connection():
    '''
    Закрывает базу данных.
    '''
    await engine.dispose()