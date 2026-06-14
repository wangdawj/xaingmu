"""
Flask 扩展初始化模块
================
集中管理 Flask 扩展实例，避免循环导入。
"""

from flask_sqlalchemy import SQLAlchemy

# 数据库 ORM 实例（在 app.py 中通过 db.init_app() 绑定到 Flask 应用）
db = SQLAlchemy()
