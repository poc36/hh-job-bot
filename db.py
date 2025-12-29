from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import DATABASE_URL

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(unique=True)
    full_name: Mapped[str]
    experience_years: Mapped[int]
    current_grade: Mapped[str]
    salary_min: Mapped[int]
    salary_max: Mapped[int]
    preferred_roles: Mapped[str]
    preferred_cities: Mapped[str]
    preferred_technologies: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    vacancies = relationship("Vacancy", back_populates="user")
    interviews = relationship("Interview", back_populates="user")

class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    hh_vacancy_id: Mapped[str]
    title: Mapped[str]
    company: Mapped[str]
    salary_from: Mapped[int | None] = mapped_column(default=None)
    salary_to: Mapped[int | None] = mapped_column(default=None)
    description: Mapped[str]
    url: Mapped[str]
    relevance_score: Mapped[float] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default="new")
    responded_at: Mapped[datetime | None] = mapped_column(default=None)
    cover_letter: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user = relationship("User", back_populates="vacancies")

class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    company: Mapped[str]
    position: Mapped[str]
    interview_date: Mapped[datetime | None] = mapped_column(default=None)
    interview_type: Mapped[str] = mapped_column(default="phone")
    checklist: Mapped[str | None] = mapped_column(default=None)
    interview_questions: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="scheduled")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user = relationship("User", back_populates="interviews")

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ БД создана!")
