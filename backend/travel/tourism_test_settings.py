import os


SECRET_KEY = "tourism-tests-only"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "rest_framework", "travel.tourism_test_app.TourismTravelConfig"]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql" if os.getenv("DB_HOST") else "django.db.backends.sqlite3",
    "NAME": os.getenv("DB_NAME", ":memory:"),
    "USER": os.getenv("DB_USER", ""),
    "PASSWORD": os.getenv("DB_PASSWORD", ""),
    "HOST": os.getenv("DB_HOST", ""),
    "PORT": os.getenv("DB_PORT", ""),
}}
MIGRATION_MODULES = {"travel": None} if not os.getenv("DB_HOST") else {}
ROOT_URLCONF = "travel.tourism_test_urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TOUR_API_KEY = os.getenv("TOUR_API_KEY", "test%2Bkey%2F%3D")
EXTERNAL_DATA_SYNC_INTERVAL_SECONDS = 600
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_THROTTLE_RATES": {"tourism": "1000/minute", "place_search": "1000/minute"},
}
