#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    handlers=[
        logging.FileHandler("logs/weather_logging.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()

now = datetime.now(tz=ZoneInfo("GMT")) - timedelta(minutes=15)
start_time = now - timedelta(minutes=4)

start_time = start_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
end_time = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

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
    lville_data = lville_result["Result"]["HistoricalObservations"][0]["Observation"]
except Exception as e:
    logging.error(f"Error fetching data from Lville API: {e}")
try:
    ow_response = requests.get(os.getenv("OPENWEATHER_API_URL"))
    ow_result = ow_response.json()
except Exception as e:
    logging.error(f"Error fetching data from OpenWeather API: {e}")

try:
    obs_utc = lville_data["ObservationTimeUtc"].strip("Z")
    utc_time = datetime.strptime(obs_utc, "%Y-%m-%dT%H:%M:%S")
    est_time = utc_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
    
    keys = {
        "HeatIndexC": "heat_index",
        "Humidity": "humidity",
        "RainMillimetersRatePerHour": "rain_rate",
        "SnowMillimetersRatePerHour": "snow_rate",
        "SolarIrradiance": "solar_irr",
        "TemperatureC": "temp",
        "WindSpeedKph": "wind_speed"
    }
    values = {v: lville_data[k]["Value"] for k, v in keys.items()}
    heat_index = values["heat_index"]
    humidity = values["humidity"]
    rain_rate = values["rain_rate"]
    snow_rate = values["snow_rate"]
    solar_irr = values["solar_irr"]
    temp = values["temp"]
    wind_speed = values["wind_speed"]
except Exception as e:
    logging.error(f"Error indexing Lville API data: {e}")
try:
    cloud_cover = ow_result["clouds"]["all"]
except Exception as e:
    logging.error(f"Error indexing OpenWeather API data: {e}")

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
    cursor.execute(
        """INSERT INTO weather_data (date, cloud_cover, heat_index, humidity, rain, snow, solar_irr, temp, wind)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (est_time, cloud_cover, heat_index, humidity, rain_rate, snow_rate, solar_irr, temp, wind_speed)
    )
    connection.commit()
    cursor.close()
    connection.close()
    logging.info("Weather data inserted successfully")
except Exception as e:
    logging.error(f"Error connecting to the database: {e}")