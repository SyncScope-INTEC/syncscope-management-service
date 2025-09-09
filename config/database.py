"""
Database configuration utilities for Railway PostgreSQL
"""

import os

import dj_database_url
from decouple import config


def get_database_config():
    """
    Get database configuration for Railway PostgreSQL
    """
    # Try to get DATABASE_URL first (Railway style)
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        # Use dj_database_url to parse Railway's DATABASE_URL
        db_config = dj_database_url.parse(database_url)

        # Force the auth schema
        if "OPTIONS" not in db_config:
            db_config["OPTIONS"] = {}
        db_config["OPTIONS"]["options"] = "-c search_path=auth"

        return db_config

    # Fallback to individual environment variables
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="syncscope_auth"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432", cast=int),
        "OPTIONS": {"options": "-c search_path=auth"},
    }


def create_auth_schema_if_not_exists():
    """
    Create the auth schema if it doesn't exist
    This should be run before migrations
    """
    import psycopg2
    from django.conf import settings

    try:
        db_config = settings.DATABASES["default"]

        # Connect without specifying a schema
        conn = psycopg2.connect(
            host=db_config["HOST"],
            port=db_config["PORT"],
            user=db_config["USER"],
            password=db_config["PASSWORD"],
            database=db_config["NAME"],
        )

        conn.autocommit = True
        cursor = conn.cursor()

        # Create auth schema if it doesn't exist
        cursor.execute("CREATE SCHEMA IF NOT EXISTS auth;")

        cursor.close()
        conn.close()

        print("✓ Auth schema created or already exists")

    except Exception as e:
        print(f"Warning: Could not create auth schema: {e}")
        print("Make sure to create the 'auth' schema manually in your PostgreSQL database")
