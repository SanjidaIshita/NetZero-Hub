from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .services.exceptions import ServiceError


def exception_handler(exc, context):
    if isinstance(exc, ServiceError):
        return Response({"code": exc.code, "detail": exc.message, **exc.extra}, status=exc.status_code)
    return drf_exception_handler(exc, context)
