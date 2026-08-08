from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None

    if response is None:
        return response

    default_code = getattr(exc, "default_code", "error")
    response.data = {
        "error": {
            "code": str(default_code),
            "message": _message_from_response(response.data),
            "details": response.data,
            "request_id": request_id,
        }
    }
    return response


def _message_from_response(data) -> str:
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    if isinstance(data, list):
        return " ".join(str(item) for item in data)
    return "Validation failed."
