import asyncio
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select, func

from config import BOT_TOKEN
from db import init_db, SessionLocal, User, Vacancy, Interview
import hh_api
import gpt_helper

class OnboardingStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_experience = State()
    waiting_for_grade = State()
    waiting_for_salary = State()
    waiting_for_roles = State()
    waiting_for_cities = State()
    waiting_for_techs = State()

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Найти вакансии"), KeyboardButton(text="📊 Профиль")],
        [KeyboardButton(text="📈 Статистика"), KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.tg_id == user_id))

    if user:
        await message.answer(
            f"Привет, {user.full_name}! 👋\n\nЯ Job Helper. Помогу найти работу!",
            reply_markup=main_kb
        )
    else:
        await state.set_state(OnboardingStates.waiting_for_name)
        await message.answer("🚀 Как тебя зовут?")

@dp.message(OnboardingStates.waiting_for_name)
async def name_entered(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(OnboardingStates.waiting_for_experience)
    await message.answer("Сколько лет опыта? (цифра)")

@dp.message(OnboardingStates.waiting_for_experience)
async def experience_entered(message: types.Message, state: FSMContext):
    try:
        years = int(message.text.strip())
    except:
        await message.answer("❌ Напиши цифру!")
        return

    await state.update_data(experience=years)
    await state.set_state(OnboardingStates.waiting_for_grade)

    grade = "junior" if years < 2 else "middle" if years < 5 else "senior"
    await message.answer(f"Твой уровень: <b>{grade}</b>? (junior/middle/senior)")

@dp.message(OnboardingStates.waiting_for_grade)
async def grade_entered(message: types.Message, state: FSMContext):
    grade = message.text.lower().strip()
    if grade not in ("junior", "middle", "senior"):
        await message.answer("❌ Выбери: junior, middle, senior")
        return

    await state.update_data(grade=grade)
    await state.set_state(OnboardingStates.waiting_for_salary)
    await message.answer("Минимальная зарплата? (цифра, например: 100000)")

@dp.message(OnboardingStates.waiting_for_salary)
async def salary_entered(message: types.Message, state: FSMContext):
    try:
        salary = int(message.text.replace(" ", ""))
    except:
        await message.answer("❌ Напиши цифру!")
        return

    await state.update_data(salary_min=salary, salary_max=int(salary * 1.5))
    await state.set_state(OnboardingStates.waiting_for_roles)
    await message.answer("Какие роли? (через запятую)\nПример: Backend, DevOps")

@dp.message(OnboardingStates.waiting_for_roles)
async def roles_entered(message: types.Message, state: FSMContext):
    roles = [r.strip() for r in message.text.split(",")]
    await state.update_data(roles=roles)
    await state.set_state(OnboardingStates.waiting_for_cities)
    await message.answer("Города? (через запятую)\nПример: Москва, Санкт-Петербург, Remote")

@dp.message(OnboardingStates.waiting_for_cities)
async def cities_entered(message: types.Message, state: FSMContext):
    cities = [c.strip() for c in message.text.split(",")]
    await state.update_data(cities=cities)
    await state.set_state(OnboardingStates.waiting_for_techs)
    await message.answer("Технологии? (через запятую)\nПример: Python, Docker, SQL")

@dp.message(OnboardingStates.waiting_for_techs)
async def techs_entered(message: types.Message, state: FSMContext):
    techs = [t.strip() for t in message.text.split(",")]
    data = await state.get_data()

    user_id = message.from_user.id

    async with SessionLocal() as db:
        user = User(
            tg_id=user_id,
            full_name=data["name"],
            experience_years=data["experience"],
            current_grade=data["grade"],
            salary_min=data["salary_min"],
            salary_max=data["salary_max"],
            preferred_roles=", ".join(data["roles"]),
            preferred_cities=", ".join(data["cities"]),
            preferred_technologies=", ".join(techs),
            created_at=datetime.utcnow(),
        )
        db.add(user)
        await db.commit()

    await state.clear()
    await message.answer("✅ Профиль создан! 🎉", reply_markup=main_kb)

@dp.message(F.text == "🔍 Найти вакансии")
async def find_vacancies(message: types.Message):
    user_id = message.from_user.id

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.tg_id == user_id))

    if not user:
        await message.answer("❌ Профиль не найден. /start")
        return

    await message.answer("🔎 Ищу вакансии... (20-30 секунд)")

    roles = user.preferred_roles.split(", ")
    cities = user.preferred_cities.split(", ")

    vacancies = await hh_api.search_vacancies(roles=roles, cities=cities, salary_from=user.salary_min)

    if not vacancies:
        await message.answer(
            "😞 Вакансии не найдены.\n\n"
            "Попробуй:\n"
            "• Снизить зарплату\n"
            "• Расширить города\n"
            "• Добавить роли",
            reply_markup=main_kb
        )
        return

    async with SessionLocal() as db:
        for vac_data in vacancies[:10]:
            existing = await db.scalar(
                select(Vacancy).where(
                    Vacancy.hh_vacancy_id == vac_data["id"],
                    Vacancy.user_id == user.id
                )
            )
            if existing:
                continue

            score = await gpt_helper.calculate_relevance_score(vac_data, user)

            vac = Vacancy(
                user_id=user.id,
                hh_vacancy_id=vac_data["id"],
                title=vac_data["title"],
                company=vac_data["company"],
                salary_from=vac_data.get("salary_from"),
                salary_to=vac_data.get("salary_to"),
                description=vac_data.get("description", "")[:500],
                url=vac_data["url"],
                relevance_score=score,
                status="new",
                created_at=datetime.utcnow(),
            )
            db.add(vac)

        await db.commit()

    text = f"🎯 Найдено <b>{len(vacancies)}</b> вакансий!\n\n"
    for i, vac in enumerate(vacancies[:5], 1):
        salary_text = "На договоренность"
        if vac.get("salary_from") and vac.get("salary_to"):
            salary_text = f"{vac['salary_from']:,}–{vac['salary_to']:,} ₽"

        text += (
            f"{i}. <b>{vac['title']}</b>\n"
            f"   💼 {vac['company']}\n"
            f"   💰 {salary_text}\n"
            f"   <a href='{vac['url']}'>Смотреть</a>\n\n"
        )

    await message.answer(text)

@dp.message(F.text == "📊 Профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.tg_id == user_id))

    if not user:
        await message.answer("❌ Профиль не найден")
        return

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: {user.full_name}\n"
        f"Опыт: {user.experience_years} лет\n"
        f"Грейд: {user.current_grade}\n"
        f"Зарплата: {user.salary_min:,} – {user.salary_max:,} ₽\n"
        f"Роли: {user.preferred_roles}\n"
        f"Города: {user.preferred_cities}\n"
    )

    await message.answer(text, reply_markup=main_kb)

@dp.message(F.text == "📈 Статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.tg_id == user_id))
        if user:
            total = await db.scalar(
                select(func.count(Vacancy.id)).where(Vacancy.user_id == user.id)
            ) or 0

    await message.answer(f"📊 Найдено вакансий: <b>{total}</b>", reply_markup=main_kb)

@dp.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: types.Message):
    text = (
        "📖 <b>Job Helper</b>\n\n"
        "🔍 Найти вакансии — поиск на HH.ru\n"
        "📊 Профиль — твои данные\n"
        "📈 Статистика — вакансии\n"
        "ℹ️ Помощь — эта справка\n"
    )
    await message.answer(text, reply_markup=main_kb)

async def main():
    await init_db()
    print("🚀 BOT ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
