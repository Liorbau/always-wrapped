from flask import Blueprint, jsonify, request

from core.timezone import resolve_tz
from app.modules.wrapped.orchestrators import build_edition

wrapped_bp = Blueprint("wrapped", __name__, url_prefix="/api")


@wrapped_bp.get("/wrapped")
def wrapped():
    return jsonify(build_edition.execute(
        period=request.args.get("period", "week"),
        force=request.args.get("force") == "1",
        start=request.args.get("start"),
        end=request.args.get("end"),
        tz=resolve_tz(request.args.get("tz")),
    ))
