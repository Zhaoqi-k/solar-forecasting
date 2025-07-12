#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime, timedelta
import logging
import pytz

os.makedirs("logs", exist_ok=True)

log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "lvillew_logging.log")

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

start_time = est.localize(datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)).strftime("%a, %d %b %Y %H:%M:%S")
end_time = est.localize(datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)).strftime("%a, %d %b %Y %H:%M:%S")

lville_params = {
                    "dt": "dobs",
                    "pi": "3",
                    "si": "LWRTR",
                    "startdatetime": start_time,
                    "enddatetime": end_time,
                    "units": "english"
                }
lville_headers = {
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                    "Referer": os.getenv("LVILLE_REFERER"),
                    "User-Agent": os.getenv("LVILLE_USER_AGENT"),
                    "X-Requested-With": "XMLHttpRequest"
                }

try:
    lville_response = requests.get(os.getenv("LVILLE_WEATHER_BASE_URL"), 
                                    params=lville_params,
                                    headers=lville_headers
                                    )
    lville_result = lville_response.json()
    lville_data = lville_result["Result"]["HistoricalObservations"]
except Exception as e:
    logging.error(f"Error fetching data from Lville API: {e}")

inserted_data = []

try:
    for entry in lville_data:
        observation = entry.get("Observation")
        if not observation:
            continue
        obs_utc = observation["ObservationTimeUtc"].strip("Z")
        utc_time = datetime.strptime(obs_utc, "%Y-%m-%dT%H:%M:%S")
        if utc_time.minute == 59:
            rounded_time = (utc_time + timedelta(hours=1)).replace(minute=0, second=0)
            keys = {
                "Humidity": "humidity",
                "RainMillimetersRatePerHour": "rain_rate",
                "SnowMillimetersRatePerHour": "snow_rate",
                "SolarIrradiance": "solar_irr",
                "TemperatureC": "temp",
                "WindSpeedKph": "wind_speed"
            }
            values = {v: observation[k]["Value"] for k, v in keys.items()}
            values = {}
            for k, v in keys.items():
                value = observation.get(k, {}).get("Value")
                values[v] = value
            inserted_data.append({
                "date": rounded_time,
                **values
            })
except Exception as e:
    logging.error(f"Error indexing Lville API data: {e}")

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
        """INSERT INTO weather_data (date, humidity, rain, snow, solar_irr, temp, wind)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (date) DO UPDATE SET
            humidity = EXCLUDED.humidity,
            rain = EXCLUDED.rain,
            snow = EXCLUDED.snow,
            solar_irr = EXCLUDED.solar_irr,
            temp = EXCLUDED.temp,
            wind = EXCLUDED.wind
        """,
        [
            (
                row["date"], 
                row["humidity"], 
                row["rain_rate"], 
                row["snow_rate"], 
                row["solar_irr"], 
                row["temp"], 
                row["wind"]
            )
            for row in inserted_data
        ])
    connection.commit()
    cursor.close()
    connection.close()
    logging.info("Weather data inserted successfully")
except Exception as e:
    logging.error(f"Error connecting to the database: {e}")

for handler in logging.root.handlers:
    handler.flush()