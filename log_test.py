import logging
import os

os.makedirs("logs", exist_ok=True)

log_path = "logs/weather_logging.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    handlers=[logging.FileHandler(log_path)]
)

logging.info("This is a test log message.")