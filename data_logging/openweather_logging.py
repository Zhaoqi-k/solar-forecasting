#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime, timedelta
import logging
import pytz

os.makedirs("logs", exist_ok=True)

log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "ow_logging.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

load_dotenv()

est = pytz.timezone("US/Eastern")
yesterday = datetime.now(est) - timedelta(days=1)
timestamps = [
    datetime.timestamp(yesterday.replace(hour=i, minute=0, second=0)) for i in range(24)
]
cloud_cover = []

try:
    for time in timestamps:
        ow_response = requests.get(
            os.getenv("OW_API_URL"),
            params={
                "lat": 40.2942,
                "lon": -74.7247,
                "dt": time,
                "appid": os.getenv("OW_API_KEY")
            }
            )
        ow_result = ow_response.json()
        data = ow_result["data"][0]["clouds"]
        cloud_cover.append(data)
except Exception as e:
    logging.error(f"Error fetching data from OpenWeather API: {e}")

utc_time = [
    datetime.fromtimestamp(time).astimezone(tz=pytz.utc).isoformat(sep=" ") for time in timestamps
]
zipped_data = list(zip(utc_time, cloud_cover))
try:
    connection = psycopg2.connect(
        user = os.getenv("DATABASE_USER"),
        password = os.getenv("DATABASE_PASSWORD"),
        host = os.getenv("DATABASE_HOST"),
        port = os.getenv("DATABASE_PORT"),
        dbname = os.getenv("DATABASE_NAME"),
        sslmode = "require"
    )
    cursor = connection.cursor()
    cursor.executemany(
        """INSERT INTO weather_data (date, cloud_cover)
        VALUES (%s, %s)
        ON CONFLICT(date) DO UPDATE SET
            cloud_cover = COALESCE(EXCLUDED.cloud_cover, weather_data.cloud_cover)""",
        zipped_data
    )
    connection.commit()
    cursor.close()
    connection.close()
    logging.info("Weather data inserted successfully")
except Exception as e:
    logging.error(f"Error connecting to the database: {e}")

for handler in logging.root.handlers:
    handler.flush()