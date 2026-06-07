import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from config import Config
from extensions import db
from routes.energy import energy_bp
from routes.auth import auth_bp


def create_app():
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    app = Flask(__name__)
    cfg = Config()
    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["JWT_SECRET_KEY"] = cfg.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = cfg.JWT_ACCESS_TOKEN_EXPIRES
    app.config["SQLALCHEMY_DATABASE_URI"] = cfg.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    CORS(app)
    JWTManager(app)
    db.init_app(app)

    app.register_blueprint(energy_bp)
    app.register_blueprint(auth_bp)

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "campus-energy-platform"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
