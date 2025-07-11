#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import pandas as pd

os.makedirs("logs", exist_ok=True)

log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "solar_logging.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

load_dotenv()

refresh_response = requests.post(
    os.getenv("REFRESH_URL"),
    data={
        "grant_type": "refresh_token",
        "client_id": os.getenv("SOLAR_CLIENT_ID"),
        "client_secret": os.getenv("SOLAR_CLIENT_SECRET"),
        "refresh_token": os.getenv("REFRESH_TOKEN")
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)
refresh_result = refresh_response.json()
access_token = refresh_result["access_token"]

now = datetime.now(tz=ZoneInfo("America/New_York"))
start_time = now.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
end_time = now.replace(hour=23, minute=59, second=0).strftime("%Y-%m-%dT%H:%M:%S")

solar_params = {
        "fields": "W_avg,Wh_sum",
        "start": f"{start_time}",
        "end": f"{end_time}",
        "tz": "US/Eastern",
        "gran": "5min"
    }
solar_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
try:
    solar_response = requests.get(
        os.getenv("SOLAR_API_URL"),
        params=solar_params,
        headers=solar_headers
    )
    solar_result = solar_response.json()
    logging.info(solar_response.url, solar_result)
    solar_data = solar_result["data"]
except Exception as e:
    logging.error("Error fetching data from solar API")

try:
    data = pd.DataFrame(solar_data)
    for i in range(len(data["ts"])):
        data[i, "ts"] = datetime.strptime(data[i, "ts"], "%Y-%m-%dT%H:%M:%S-04:00")
    listed_data = data[["ts", "Wh_sum", "W_avg"]].values.tolist()
except Exception as e:
    logging.error("Error dataframing data")

try:
    connection = psycopg2.connect(
        user=os.getenv("DATABASE_USER"),
        password=os.getenv("DATABASE_PASSWORD"),
        host=os.getenv("DATABASE_HOST"),
        port=os.getenv("DATABASE_PORT"),
        dbname=os.getenv("DATABASE_NAME"),
        sslmode="require"
    )
    cursor = connection.cursor()
    cursor.executemany(
        """INSERT INTO solar_data (ts, wh_sum, w_avg)
        VALUES (%s, %s, %s)""",
        listed_data
    )
    connection.commit()
    cursor.close()
    connection.close()
    logging.info("Solar data inserted successfully")
except Exception as e:
    logging.error(f"Error connecting to the database: {e}")

for handler in logging.root.handlers:
    handler.flush()