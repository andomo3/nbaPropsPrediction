import os

from django.contrib import admin
from django.core.management import call_command
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


def cron_trigger(request, secret):
    """
    Called daily by cron-job.org to sync ESPN data and generate picks.
    Protected by a secret token in the URL path.
    Set CRON_SECRET env var on Railway, then point cron-job.org at:
      /cron/daily/<your-secret>/
    """
    expected = os.getenv("CRON_SECRET", "")
    if not expected or secret != expected:
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        call_command("sync_espn_games", days=1)
        call_command("generate_daily_picks")
        return JsonResponse({"status": "ok"})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


urlpatterns = [
    path("health/", health, name="health"),
    path("cron/daily/<str:secret>/", cron_trigger, name="cron-trigger"),
    path("admin/", admin.site.urls),
    path("api/", include("nba_betting.urls")),
]
