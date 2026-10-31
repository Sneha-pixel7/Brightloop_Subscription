from django.db import connection
from django.http import JsonResponse


def health(request):
    """Liveness + database readiness probe used by Docker and humans."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - report any DB failure as unhealthy
        return JsonResponse({"status": "unhealthy", "database": "down", "detail": str(exc)}, status=503)
    return JsonResponse({"status": "ok", "database": "up"})
