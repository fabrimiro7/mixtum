from django.db import DatabaseError, connections
from django.http import HttpResponse


def live(_request):
    response = HttpResponse("ok\n", content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response


def ready(_request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        response = HttpResponse("unavailable\n", status=503, content_type="text/plain")
    else:
        response = HttpResponse("ok\n", content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response
