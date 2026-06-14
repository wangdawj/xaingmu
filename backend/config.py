"""
应用配置模块
=========
从环境变量加载 MySQL 等连接参数，并提供 SQLAlchemy 连接 URI。
"""

import os


class Config:
    """全局配置类：所有配置项支持环境变量覆盖，提供合理默认值"""

    # Flask 密钥（生产环境应通过环境变量注入）
    SECRET_KEY = os.getenv("SECRET_KEY", "campus-energy-secret-key")

    # ---- MySQL 连接参数 ----
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "energy")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "energy123")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "campus_energy")

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        """动态生成 SQLAlchemy 连接 URI（pymysql 驱动 + utf8mb4 编码）"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )
