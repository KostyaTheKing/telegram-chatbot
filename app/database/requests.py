from app.database.models import async_session
from app.database.models import User, AI_models, User_Requests
from sqlalchemy import and_, select, delete, func
from config import ALLOWED_USERS, ADMIN_USERS
import datetime

async def add_simple_user(tg_username: str) -> int:
    '''
    Добавляет нового пользователя, у которого будет базовый доступ к боту.
    '''
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_username == tg_username))

        if not user:
            session.add(User(tg_username = tg_username, has_admin_priviliges = False))
            await session.commit()
            ALLOWED_USERS.add(tg_username)
            return 1
    return 0

async def add_admin(tg_username: str) -> int:
    '''
    Добавляет нового пользователя или обновляет права указанного пользователя до уровня администратора.
    '''
    async with async_session() as session:
        admin = await session.scalar(select(User).where(and_(User.tg_username == tg_username, User.has_admin_priviliges == True)))
        user = await session.scalar(select(User).where(User.tg_username == tg_username))
        
        if not user:
            session.add(User(tg_username = tg_username, has_admin_priviliges = True))
            await session.commit()
            ALLOWED_USERS.add(tg_username)
            ADMIN_USERS.add(tg_username)
            return 1
        elif not admin:
            user.has_admin_priviliges = True
            await session.commit()
            ADMIN_USERS.add(tg_username)
            return 1
    return 0

async def add_user(tg_username: str, role: str) -> int:
    '''
    Добавляет или юзера, или админа.
    '''
    match role:
        case "user":
            return await add_simple_user(tg_username)
        case "admin":
            return await add_admin(tg_username)


async def remove_user(tg_username: str) -> int:
    '''
    Удаляет пользователя из базы данных.
    '''
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_username == tg_username))

        if user:
            await session.delete(user)
            await session.commit()
            ALLOWED_USERS.remove(tg_username)
            ADMIN_USERS.discard(tg_username)
            return 1
    return 0

async def get_models_by_type(model_type: str):
    '''
    Получает список моделей в зависимости от их типа.
    '''
    async with async_session() as session:
        return await session.scalars(select(AI_models).where(AI_models.model_type == model_type))

async def fetch_model_info(model_name: str):
    '''
    Достаёт из бд информацию о модели: описание, цены.
    '''
    async with async_session() as session:
        return await session.execute(select(AI_models).where(AI_models.model_name == model_name))

async def store_money_spent_per_request(tg_username: str, money_spent: float, ai_model: str) -> None:
    '''
    Записывает в БД информацию о запросе пользователя: айди пользователя, количество потраченных денег в долларах, название
    ии модели, дату.
    '''
    current_date = datetime.datetime.now()
    async with async_session() as session:
        user_id = await session.scalar(select(User.id).where(User.tg_username == tg_username))
        session.add(User_Requests(user_id = user_id, ai_model = ai_model, money_spent = money_spent, date = current_date))
        await session.commit()

async def calculate_spent_money(tg_username: str, start = None, end = None) -> float:
    '''
    Расчёт потраченных денег за все запросы к ии.
    '''
    async with async_session() as session:
        user_id = await session.scalar(select(User.id).where(User.tg_username == tg_username))
        
        if (start is not None) and (end is not None):
            stmt = select(
                func.sum(User_Requests.money_spent)
            ).where(and_(User_Requests.user_id == user_id, User_Requests.date >= start, User_Requests.date <= end))
        else:
            stmt = select(
                func.sum(User_Requests.money_spent)
            ).where(User_Requests.user_id == user_id)
        total_money_spent = await session.scalar(stmt)
        return total_money_spent if total_money_spent is not None else 0.00

async def show_all_users_and_money_spent():
    '''
    Показывает никнеймы пользователей, а также, сколько денег они потратили.
    '''
    async with async_session() as session:
        res = await session.execute(select(User.tg_username, func.coalesce(func.sum(User_Requests.money_spent), 0.00)).join_from(User, User_Requests, isouter=True).group_by(User.tg_username))
        res = res.all()
    return res

async def remove_user_requests(tg_username: str, start = None, end = None):
    '''
    Удаляет все запросы пользователя из БД.
    '''
    async with async_session() as session:
        user_id = await session.scalar(select(User.id).where(User.tg_username == tg_username))
        if (start is not None) and (end is not None):
            stmt = delete(
                User_Requests
            ).where(
                and_(User_Requests.user_id == user_id, User_Requests.date >= start, User_Requests.date <= end)
            )
        else:
            stmt = delete(
                User_Requests
            ).where(
                User_Requests.user_id == user_id
            )
        await session.execute(stmt)
        await session.commit()

