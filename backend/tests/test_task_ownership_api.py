import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, add_task_ownership_column, get_db
from app.main import app
from app.models.task import Task


class TaskOwnershipEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        # This suite deliberately uses the real bearer-token dependency.
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)
        self.user_a_headers = self.register_and_login("owner-a@planora.local")
        self.user_b_headers = self.register_and_login("owner-b@planora.local")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email: str) -> dict[str, str]:
        response = self.client.post(
            "/auth/register",
            json={"name": email.split("@")[0], "email": email, "password": "secure-pass-123"},
        )
        self.assertEqual(response.status_code, 201)
        token = self.client.post(
            "/auth/login", json={"email": email, "password": "secure-pass-123"}
        )
        self.assertEqual(token.status_code, 200)
        return {"Authorization": f"Bearer {token.json()['access_token']}"}

    @staticmethod
    def payload(title: str) -> dict:
        return {
            "title": title,
            "duration_minutes": 30,
            "deadline": "2040-01-01T10:00:00",
            "priority": "high",
        }

    def create(self, title: str, headers: dict[str, str]) -> dict:
        response = self.client.post("/tasks", json=self.payload(title), headers=headers)
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_tasks_are_owned_and_isolated_across_crud_and_replanning(self):
        task_a = self.create("Owner A task", self.user_a_headers)
        task_b = self.create("Owner B task", self.user_b_headers)

        with self.session_local() as db:
            stored = db.get(Task, task_a["id"])
            self.assertIsNotNone(stored.user_id)

        self.assertEqual([task["id"] for task in self.client.get("/tasks", headers=self.user_a_headers).json()], [task_a["id"]])
        self.assertEqual([task["id"] for task in self.client.get("/tasks", headers=self.user_b_headers).json()], [task_b["id"]])

        self.assertEqual(self.client.get(f"/tasks/{task_b['id']}", headers=self.user_a_headers).status_code, 404)
        update = self.payload("Attempted takeover")
        self.assertEqual(self.client.put(f"/tasks/{task_b['id']}", json=update, headers=self.user_a_headers).status_code, 404)
        self.assertEqual(self.client.delete(f"/tasks/{task_b['id']}", headers=self.user_a_headers).status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/replan/{task_b['id']}",
                json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"},
                headers=self.user_a_headers,
            ).status_code,
            404,
        )

        owner_update = self.payload("Owner A updated")
        self.assertEqual(self.client.put(f"/tasks/{task_a['id']}", json=owner_update, headers=self.user_a_headers).status_code, 200)

    def test_task_endpoints_require_authentication(self):
        self.assertEqual(self.client.get("/tasks").status_code, 401)
        self.assertEqual(self.client.post("/tasks", json=self.payload("No owner")).status_code, 401)


class TaskOwnershipMigrationTests(unittest.TestCase):
    def test_existing_sqlite_tasks_are_backfilled_without_deletion(self):
        migration_engine = create_engine("sqlite://")
        try:
            with migration_engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE users ("
                        "id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, "
                        "email VARCHAR NOT NULL UNIQUE, password_hash VARCHAR NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TABLE tasks ("
                        "id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, "
                        "duration_minutes INTEGER NOT NULL, deadline DATETIME NOT NULL, "
                        "priority VARCHAR NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO tasks (id, title, duration_minutes, deadline, priority) "
                        "VALUES (7, 'Existing development task', 30, '2040-01-01 10:00:00', 'medium')"
                    )
                )

            with patch("app.database.engine", migration_engine):
                add_task_ownership_column()

            with migration_engine.connect() as connection:
                task = connection.execute(
                    text("SELECT id, title, user_id FROM tasks WHERE id = 7")
                ).mappings().one()
                self.assertEqual(task["title"], "Existing development task")
                self.assertIsNotNone(task["user_id"])
                self.assertEqual(
                    connection.execute(text("SELECT COUNT(*) FROM tasks")).scalar(), 1
                )
                self.assertIn(
                    "user_id", {column["name"] for column in inspect(migration_engine).get_columns("tasks")}
                )
        finally:
            migration_engine.dispose()


if __name__ == "__main__":
    unittest.main()
