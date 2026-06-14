"""
Flask 应用工厂模块
===============
创建并配置 Flask 应用实例，注册蓝图、扩展、CORS 等。
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from config import Config
from extensions import db
from routes.energy import energy_bp

# 加载 .env 环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def create_app(config_class=Config):
    """应用工厂函数：创建并配置 Flask 应用实例"""
    app = Flask(__name__)
    cfg = config_class()

    # Flask 核心配置
    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = cfg.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # 启用跨域请求支持
    CORS(app)

    # 初始化数据库扩展
    db.init_app(app)

    # 注册能耗管理蓝图
    app.register_blueprint(energy_bp)

    @app.route("/api/health")
    def health():
        """健康检查接口"""
        return jsonify({"status": "ok", "service": "campus-energy-platform"})

    return app


if __name__ == "__main__":
    app = create_app()
    # 开发模式启动，监听所有网卡
    app.run(host="0.0.0.0", port=5000, debug=True)
