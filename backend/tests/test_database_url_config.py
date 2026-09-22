"""DATABASE_URL handling: Railway PostgreSQL acceptance, psycopg driver use,
SQLite continuity for local/test setups, and the Railway SQLite guard."""

import unittest
from unittest.mock import patch

from sqlalchemy.engine.url import make_url

from app.database import ensure_production_database, normalize_database_url


class NormalizeDatabaseUrlTests(unittest.TestCase):
    def test_railway_postgresql_scheme_uses_psycopg(self):
        normalized = normalize_database_url(
            "postgresql://user:pass@host:5432/planora"
        )
        self.assertEqual(
            normalized, "postgresql+psycopg://user:pass@host:5432/planora"
        )
        # The URL resolves to the psycopg (v3) driver without connecting.
        self.assertEqual(make_url(normalized).drivername, "postgresql+psycopg")

    def test_legacy_postgres_scheme_uses_psycopg(self):
        normalized = normalize_database_url("postgres://user:pass@host:5432/planora")
        self.assertEqual(
            normalized, "postgresql+psycopg://user:pass@host:5432/planora"
        )

    def test_already_qualified_url_is_unchanged(self):
        url = "postgresql+psycopg://user:pass@host:5432/planora"
        self.assertEqual(normalize_database_url(url), url)

    def test_sqlite_urls_pass_through(self):
        self.assertEqual(
            normalize_database_url("sqlite:///./missed_task_replanner.db"),
            "sqlite:///./missed_task_replanner.db",
        )
        self.assertEqual(normalize_database_url("sqlite://"), "sqlite://")

    def test_surrounding_whitespace_and_quotes_are_stripped(self):
        self.assertEqual(
            normalize_database_url("  postgresql://user:pass@host:5432/planora\n"),
            "postgresql+psycopg://user:pass@host:5432/planora",
        )


class ProductionDatabaseGuardTests(unittest.TestCase):
    def test_sqlite_on_railway_fails_fast(self):
        with patch.dict("os.environ", {"RAILWAY_ENVIRONMENT": "production"}):
            with self.assertRaises(RuntimeError) as context:
                ensure_production_database("sqlite:///./missed_task_replanner.db")
        self.assertIn("DATABASE_URL", str(context.exception))

    def test_postgres_on_railway_is_accepted(self):
        with patch.dict("os.environ", {"RAILWAY_ENVIRONMENT": "production"}):
            ensure_production_database("postgresql+psycopg://user:pass@host:5432/planora")

    def test_sqlite_without_railway_marker_is_allowed(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("RAILWAY_ENVIRONMENT", None)
            ensure_production_database("sqlite:///./missed_task_replanner.db")
            ensure_production_database("sqlite://")


if __name__ == "__main__":
    unittest.main()
