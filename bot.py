import aiohttp
import random
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select
from sqlalchemy import func
import config
from database import async_session
from models import ParkingSpot, User, ParkingSession

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Найти парковку")],
        [KeyboardButton(text="Поиск Mega Park")],
        [KeyboardButton(text="Бесплатные парковки")],
        [KeyboardButton(text="🚘 Мои парковки")],
        [KeyboardButton(text="💰 Пополнить баланс")]
    ],
    resize_keyboard=True
)



# ✅ Состояние регистрации
class RegistrationState(StatesGroup):
    waiting_for_car_number = State()



# ✅ Обработка команды /start с регистрацией
@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    tg_id = str(message.from_user.id)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            user = User(tg_id=tg_id, balance=0)
            session.add(user)
            await session.commit()

        if not user.car_number:
            await message.answer("🚗 Добро пожаловать! Укажите номер автомобиля для завершения регистрации:")
            await state.set_state(RegistrationState.waiting_for_car_number)
        else:
            await message.answer("✅ Вы уже зарегистрированы. Добро пожаловать!", reply_markup=main_kb)

# ✅ Обработка ввода номера авто
@dp.message(RegistrationState.waiting_for_car_number)
async def process_car_number(message: types.Message, state: FSMContext):
    car_number = message.text.strip()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == str(message.from_user.id)))
        user = result.scalars().first()
        if user:
            user.car_number = car_number
            session.add(user)
            await session.commit()
            await message.answer(f"✅ Ваш номер авто сохранён: {car_number}\nТеперь вы можете пользоваться ботом.", reply_markup=main_kb)
            await state.clear()

def generate_random_price_and_spaces():
    return random.randint(2, 10) * 100, random.randint(50, 500)

# ✅ Запрос к Google Places API
async def fetch_google_places(lat: float, lon: float, query: str = None, free_only: bool = False):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 3000,
        "type": "parking",
        "key": config.GOOGLE_MAPS_API_KEY,
        "language": "ru"
    }
    if query:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "location": f"{lat},{lon}",
            "radius": 3000,
            "key": config.GOOGLE_MAPS_API_KEY,
            "language": "ru"
        }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            results = data.get("results", [])
            if free_only:
                results = [
                    r for r in results if
                    "free" in r.get("name", "").lower()
                    or "бесплат" in r.get("name", "").lower()
                    or "free" in r.get("vicinity", "").lower()
                    or "бесплат" in r.get("vicinity", "").lower()
                ]
            return results

@dp.message(F.text == "💰 Пополнить баланс")
async def top_up_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1000 ₸", callback_data="topup_1000")],
        [InlineKeyboardButton(text="10000 ₸", callback_data="topup_10000")],
        [InlineKeyboardButton(text="20000 ₸", callback_data="topup_20000")]
    ])
    await message.answer("💳 Выберите сумму пополнения:", reply_markup=kb)

@dp.callback_query(F.data.startswith("topup_"))
async def top_up_balance(callback: types.CallbackQuery):
    tg_id = str(callback.from_user.id)
    amount = int(callback.data.split("_")[1])

    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalars().first()

        if not user:
            await callback.message.answer("⚠️ Сначала введите /start для регистрации.")
            return

        user.balance += amount
        session.add(user)
        await session.commit()

    await callback.message.answer(f"✅ Баланс пополнен на {amount} ₸. Текущий баланс: {user.balance} ₸", reply_markup=main_kb)



# ✅ Кнопка для отправки геопозиции
geo_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)
@dp.message(F.text == "📍 Найти парковку")
async def ask_location(message: types.Message):
    await message.answer("📡 Отправьте свою геолокацию для поиска ближайших парковок:", reply_markup=geo_kb)

@dp.message(F.location)
async def handle_location(message: types.Message):
    lat, lon = message.location.latitude, message.location.longitude
    results = await fetch_google_places(lat, lon)
    if not results:
        await message.answer("🚗 Рядом не найдено парковок.")
        return

    nearest = results[0]
    name = nearest.get("name")
    address = nearest.get("vicinity", "Адрес не указан")
    place_lat = nearest["geometry"]["location"]["lat"]
    place_lon = nearest["geometry"]["location"]["lng"]

    price, spaces = generate_random_price_and_spaces()

    async with async_session() as session:
        exists = await session.execute(select(ParkingSpot).where(ParkingSpot.location == name))
        exists = exists.scalar()

        if not exists:
            spot = ParkingSpot(
                location=name,
                price_per_hour=price,
                available=True,
                free_spaces=spaces,
                latitude=place_lat,
                longitude=place_lon
            )
            session.add(spot)
            await session.commit()
        else:
            spot = exists

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Забронировать", callback_data=f"buy_parking_{spot.id}")]]
    )
    await message.answer_location(latitude=place_lat, longitude=place_lon)
    await message.answer(
        f"🏁 {name}\n📍 {address}\n💰 {price} ₸/час\n🚘 Свободных мест: {spot.free_spaces}",
        reply_markup=keyboard
    )

@dp.message(F.text.startswith("Поиск "))
async def search_parking_by_name(message: types.Message):
    query = message.text[7:].strip()
    user_loc = (43.238949, 76.889709)
    results = await fetch_google_places(user_loc[0], user_loc[1], query=query)
    if not results:
        await message.answer("🔍 Ничего не найдено по запросу.")
        return

    tg_id = str(message.from_user.id)
    async with async_session() as session:
        for r in results[:3]:
            name = r.get("name")
            address = r.get("vicinity", "Адрес не указан")
            lat = r["geometry"]["location"]["lat"]
            lon = r["geometry"]["location"]["lng"]
            price, spaces = generate_random_price_and_spaces()

            exists = await session.execute(select(ParkingSpot).where(ParkingSpot.location == name))
            exists = exists.scalar()
            if not exists:
                spot = ParkingSpot(
                    location=name,
                    price_per_hour=price,
                    available=True,
                    free_spaces=spaces,
                    latitude=lat,
                    longitude=lon
                )
                session.add(spot)
                await session.commit()
            else:
                spot = exists

            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💳 Забронировать", callback_data=f"buy_parking_{spot.id}")]]
            )
            await message.answer_location(latitude=lat, longitude=lon)
            await message.answer(
                f"🏁 {name}\n📍 {address}\n💰 {spot.price_per_hour} ₸/час\n🚘 Свободных мест: {spot.free_spaces}",
                reply_markup=kb
            )

@dp.message(F.text.lower().strip() == "бесплатные парковки")
async def search_free_parkings(message: types.Message):
    user_loc = (43.238949, 76.889709)
    tg_id = str(message.from_user.id)

    async with async_session() as session:
        existing_spots_result = await session.execute(select(ParkingSpot.location))
        existing_names = set(row[0] for row in existing_spots_result)

        generated = []
        for _ in range(5):
            name = f"Free Parking Zone {random.randint(1000, 9999)}"
            if name not in existing_names:
                lat = user_loc[0] + random.uniform(-0.01, 0.01)
                lon = user_loc[1] + random.uniform(-0.01, 0.01)
                spot = ParkingSpot(
                    location=name,
                    price_per_hour=0,
                    available=True,
                    free_spaces=random.randint(20, 100),
                    latitude=lat,
                    longitude=lon
                )
                session.add(spot)
                await session.commit()
                generated.append(spot)

        if not generated:
            await message.answer("🚫 Не удалось сгенерировать новые бесплатные парковки.")
            return

        for spot in generated:
            await message.answer_location(latitude=spot.latitude, longitude=spot.longitude)
            await message.answer(
                f"🆓 Бесплатная парковка:\n🏁 {spot.location}\n📍 Алматы"
            )


# ✅ Покупка парковки (ложная оплата)
@dp.callback_query(F.data.startswith("buy_parking_"))
async def buy_parking(callback: types.CallbackQuery):
    parking_id = int(callback.data.split("_")[-1])
    tg_id = str(callback.from_user.id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    end_time = now + timedelta(hours=1)

    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = user_result.scalars().first()

        if not user:
            await callback.message.answer("⚠️ Вы не зарегистрированы. Введите /start для начала.", reply_markup=main_kb)
            return

        spot_result = await session.execute(
            select(ParkingSpot).where(ParkingSpot.id == parking_id).with_for_update()
        )
        spot = spot_result.scalars().first()

        if not spot or spot.free_spaces <= 0:
            await callback.message.answer("❌ Место недоступно.", reply_markup=main_kb)
            return

        if user.balance < spot.price_per_hour:
            await callback.message.answer(
                f"❌ Недостаточно средств. Нужно {spot.price_per_hour} ₸, у вас {user.balance} ₸.",
                reply_markup=main_kb
            )
            return

        user.balance -= spot.price_per_hour
        spot.free_spaces -= 1
        if spot.free_spaces == 0:
            spot.available = False

        session.add_all([user, spot])
        session.add(ParkingSession(
            user_id=user.id,
            spot_id=spot.id,
            start_time=now,
            end_time=end_time
        ))
        await session.commit()

    await callback.message.answer(
        f"✅ Парковка '{spot.location}' успешно куплена!\n⏳ До {end_time.strftime('%H:%M')} UTC",
        reply_markup=main_kb
    )


# ✅ Просмотр активных парковок пользователя
@dp.message(F.text == "🚘 Мои парковки")
async def view_user_parkings(message: types.Message):
    tg_id = str(message.from_user.id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = user_result.scalars().first()
        result = await session.execute(
            select(ParkingSession, ParkingSpot)
            .join(ParkingSpot, ParkingSession.spot_id == ParkingSpot.id)
            .where(ParkingSession.user_id == user.id, ParkingSession.end_time > now)
        )
        sessions = result.all()

    if not sessions:
        await message.answer("🚘 У вас нет активных парковок.")
        return

    text = "🅿️ Ваши парковки:\n\n"
    for s, spot in sessions:
        remaining = int((s.end_time - now).total_seconds() // 60)
        text += f"🏁 {spot.location}\n⏳ До: {s.end_time.strftime('%H:%M')} UTC\n🕒 Осталось: {remaining} мин\n\n"
    await message.answer(text)

# ✅ Авто-освобождение парковок
async def check_expired_sessions():
    while True:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with async_session() as session:
            result = await session.execute(
                select(ParkingSession, ParkingSpot, User)
                .join(ParkingSpot, ParkingSession.spot_id == ParkingSpot.id)
                .join(User, ParkingSession.user_id == User.id)
                .where(ParkingSession.end_time <= now)
            )
            sessions = result.all()

            for s, spot, user in sessions:
                spot.free_spaces += 1
                if not spot.available:
                    spot.available = True
                await bot.send_message(str(user.tg_id), f"⌛ Время парковки на '{spot.location}' истекло.")
                await session.delete(s)
                session.add(spot)

            await session.commit()
        await asyncio.sleep(60)  # проверка каждую минуту


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(check_expired_sessions())  
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())