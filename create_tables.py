import asyncio
from database import engine, Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    print("📌 Создаю таблицы в базе данных...")
    await init_db()
    print("✅ Таблицы успешно созданы!")

if __name__ == "__main__":
    asyncio.run(main())
