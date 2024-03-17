import os
import requests
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
from sqlalchemy import func
from pydantic import BaseModel, Field
from starlette import status
from models import Base, Currency
from database import engine, SessionLocal
from datetime import datetime
from typing import Annotated
from models import Rates
from sqlalchemy.orm import Session

load_dotenv()

app = FastAPI()

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


class RateRequest(BaseModel):
    source: str = Field(default="RUB", min_length=3, max_length=3)
    target: str = Field(default="USD", min_length=3, max_length=3)
    sum: float = Field(gt=0)


@app.get('/healthy', status_code=status.HTTP_200_OK)
async def health_check():
    return {'status': 'Healthy'}


def get_currency_title(db):
    currencies = db.query(Currency).all()
    currency_dict = {currency.code: currency.title for currency in currencies}

    if not currency_dict:
        url = f"http://api.exchangeratesapi.io/v1/symbols?access_key={os.getenv('RATES_TOKEN')}"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            if data["success"]:
                for code, title in data["symbols"].items():
                    new_currency = Currency(code=code, title=title)
                    db.add(new_currency)
                db.commit()
            currencies = db.query(Currency).all()
            currency_dict = {currency.code: currency.title for currency in currencies}

    return currency_dict


def get_rates():
    url = f"http://api.exchangeratesapi.io/v1/latest?access_key={os.getenv('RATES_TOKEN')}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data
    return False


@app.get('/update-rates', status_code=status.HTTP_200_OK)
async def get_and_feel_rates(db: db_dependency):
    currency_titles = get_currency_title(db)
    currency_rates = get_rates()

    if not currency_titles or not currency_rates:
        return {'error': 'Ошибка получения данных'}

    currency_date = datetime.now()

    for code, rate in currency_rates["rates"].items():
        # Проверяем, существует ли уже валюта с таким кодом в базе
        existing_currency = db.query(Rates).filter(Rates.code == code).first()
        if existing_currency:
            # Если валюта существует, обновляем её курс и время
            existing_currency.rate = rate
            existing_currency.created_at = currency_date
        else:
            # Если валюты нет, создаём новую запись
            new_currency = Rates(code=code, title=currency_titles.get(code, ''), rate=rate, created_at=currency_date)
            db.add(new_currency)
    db.commit()
    return {'status': 'success'}


@app.get("/", status_code=status.HTTP_200_OK)
async def get_last_update(db: db_dependency):
    last_update = db.query(func.max(Rates.created_at)).scalar()

    if last_update is None:
        return {"message": "Данные о валютах не найдены"}

    return {"last_update": last_update.strftime("%Y-%m-%d %H:%M:%S")}


@app.post('/get-rate', status_code=status.HTTP_200_OK)
async def get_rate(db: db_dependency, rate_request: RateRequest):
    source_currency_to_base = db.query(Rates).filter(Rates.code == rate_request.source).first()
    target_currency_to_base = db.query(Rates).filter(Rates.code == rate_request.target).first()

    if not source_currency_to_base or not target_currency_to_base:
        raise HTTPException(status_code=404, detail="Currency not found")

    # Евро базовая валюта
    if rate_request.target == "EUR":
        if source_currency_to_base.rate == 0:
            raise HTTPException(status_code=400, detail="Некорректный курс валюты источника.")
        return {'result': rate_request.sum / source_currency_to_base.rate}

    source_in_euro = rate_request.sum / source_currency_to_base.rate
    sum_result = source_in_euro * target_currency_to_base.rate

    return {'result': sum_result}
