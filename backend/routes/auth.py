from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import SysUser
from extensions import db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"code": 400, "message": "用户名和密码不能为空"}), 400

    user = SysUser.query.filter_by(username=username, status=1).first()
    if not user:
        return jsonify({"code": 401, "message": "用户不存在"}), 401

    # 开发环境：admin/admin123 直接放行；生产环境应使用 password_hash 校验
    if username == "admin" and password == "admin123":
        pass
    elif not check_password_hash(user.password_hash, password):
        return jsonify({"code": 401, "message": "密码错误"}), 401

    token = create_access_token(identity={"user_id": user.user_id, "role": user.role})
    return jsonify({
        "code": 0,
        "data": {
            "token": token,
            "username": user.username,
            "real_name": user.real_name,
            "role": user.role,
        },
    })


@auth_bp.route("/register", methods=["POST"])
@jwt_required()
def register():
    identity = get_jwt_identity()
    if identity.get("role") != "admin":
        return jsonify({"code": 403, "message": "无权限"}), 403

    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "viewer")
    if not username or not password:
        return jsonify({"code": 400, "message": "参数不完整"}), 400

    if SysUser.query.filter_by(username=username).first():
        return jsonify({"code": 409, "message": "用户名已存在"}), 409

    user = SysUser(
        username=username,
        password_hash=generate_password_hash(password),
        real_name=data.get("real_name", ""),
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"code": 0, "message": "注册成功"})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = SysUser.query.get(identity["user_id"])
    if not user:
        return jsonify({"code": 404, "message": "用户不存在"}), 404
    return jsonify({"code": 0, "data": {
        "username": user.username,
        "real_name": user.real_name,
        "role": user.role,
    }})
