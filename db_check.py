from database import engine
import asyncio

async def test_connection():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: print("✅ Успешное подключение к Railway!"))
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
