import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import config

# Отключаем строгую проверку SSL-сертификатов (НЕ рекомендуется для продакшена)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    config.DATABASE_URL.replace("?sslmode=require", ""),
    echo=True,
    pool_pre_ping=True,
    connect_args={"ssl": ssl_context}
)

async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()
