"""The single error contract shared by every endpoint and the frontend.

Wire shape (never change casually — static/src/api/client.js parses it):

    {"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {}}}
"""

VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
FORBIDDEN = "FORBIDDEN"
UPSTREAM_ERROR = "UPSTREAM_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

STATUS_BY_CODE = {
    VALIDATION_ERROR: 400,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    CONFLICT: 409,
    BUDGET_EXHAUSTED: 429,
    INTERNAL_ERROR: 500,
    UPSTREAM_ERROR: 502,
}


class AppError(Exception):
    """Raised anywhere below the router; the app-wide handler maps it to JSON."""

    def __init__(self, code, message, details=None, status=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status = status or STATUS_BY_CODE.get(code, 500)

    def to_payload(self):
        return error_payload(self.code, self.message, self.details)


def error_payload(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details or {}}}


def validation_error(message, details=None):
    return AppError(VALIDATION_ERROR, message, details)


def not_found(message, details=None):
    return AppError(NOT_FOUND, message, details)


def conflict(message, details=None):
    return AppError(CONFLICT, message, details)


def budget_exhausted(message, details=None):
    return AppError(BUDGET_EXHAUSTED, message, details)


def upstream_error(message, details=None):
    return AppError(UPSTREAM_ERROR, message, details)
