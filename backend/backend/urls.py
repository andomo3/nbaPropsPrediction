import os

from django.contrib import admin
from django.core.management import call_command
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_POST


def health(request):
    return JsonResponse({"status": "ok"})


@require_POST
def cron_trigger(request):
    """
    Called daily by cron-job.org to sync ESPN data and generate picks.
    Protected by a shared secret in the Authorization header.
    """
    token = request.headers.get("Authorization", "")
    expected = f"Bearer {os.getenv('CRON_SECRET', '')}"
    if not token or token != expected:
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        call_command("sync_espn_games", days=1)
        call_command("generate_daily_picks")
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


urlpatterns = [
    path("health/", health, name="health"),
    path("cron/daily/", cron_trigger, name="cron-trigger"),
    path("admin/", admin.site.urls),
    path("api/", include("nba_betting.urls")),
]
