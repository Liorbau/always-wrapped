"""Owner unlock endpoints — password gate for browser mutations."""

from flask import Blueprint, jsonify, make_response, request

from app import owner_auth

owner_bp = Blueprint("owner", __name__, url_prefix="/api/owner")


@owner_bp.get("/status")
def status():
    return jsonify({"unlocked": owner_auth.is_unlocked(), "ttl_days": owner_auth.TTL_DAYS})


@owner_bp.post("/unlock")
def unlock():
    body = request.get_json(silent=True) or {}
    value = owner_auth.unlock(body.get("token"))
    response = make_response(jsonify({"unlocked": True, "ttl_days": owner_auth.TTL_DAYS}))
    response.set_cookie(owner_auth.COOKIE, value, **owner_auth.cookie_kwargs())
    return response
