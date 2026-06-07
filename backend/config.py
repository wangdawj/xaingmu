import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "campus-energy-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "campus-energy-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)

    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "energy")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "energy123")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "campus_energy")

    INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "campus-energy-token")
    INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "campus")
    INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "energy")
    INFLUXDB_VERSION = os.getenv("INFLUXDB_VERSION", "2")

    KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )
