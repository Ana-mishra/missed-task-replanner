import unittest

from fastapi.testclient import TestClient

from app.main import app


class CorsTests(unittest.TestCase):
    def test_vite_origin_receives_cors_response_header(self):
        client = TestClient(app)

        response = client.options(
            "/tasks",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertIn("GET", response.headers["access-control-allow-methods"])


if __name__ == "__main__":
    unittest.main()
