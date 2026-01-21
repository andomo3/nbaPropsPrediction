import os

import dj_database_url
import psycopg2
import redis


def check_postgres():
    database_url = os.getenv(
        "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/nba_props"
    )
    config = dj_database_url.parse(database_url)
    if config.get("ENGINE") != "django.db.backends.postgresql":
        return False, "Postgres check skipped: DATABASE_URL is not Postgres."

    try:
        connection = psycopg2.connect(
            dbname=config.get("NAME"),
            user=config.get("USER"),
            password=config.get("PASSWORD"),
            host=config.get("HOST"),
            port=config.get("PORT") or 5432,
            connect_timeout=5,
        )
        connection.close()
        return True, "Postgres connection OK."
    except Exception as exc:
        return False, f"Postgres connection failed: {exc}"


def check_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(
            redis_url, socket_connect_timeout=5, socket_timeout=5
        )
        client.set("infra_check", "ok", ex=30)
        value = client.get("infra_check")
        if value != b"ok":
            return False, "Redis set/get failed."
        return True, "Redis connection OK."
    except Exception as exc:
        return False, f"Redis connection failed: {exc}"


def main():
    db_ok, db_message = check_postgres()
    redis_ok, redis_message = check_redis()

    print(db_message)
    print(redis_message)

    if db_ok and redis_ok:
        print("✅ Infrastructure Ready")


if __name__ == "__main__":
    main()
