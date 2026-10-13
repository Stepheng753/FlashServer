# Swagger Testing

Tests: [modules/Swagger/tests/test_swagger.py](../../modules/Swagger/tests/test_swagger.py)

```bash
.venv/bin/python -m unittest discover -s modules/Swagger/tests -p "test_*.py"
```

The tests use the real Flask app (`from app import app`) with the credentials from `config/secrets.json`. They touch no database.

| Class | What it checks |
| :--- | :--- |
| `TestSwaggerSpec` | Spec is OpenAPI 3.x with the expected servers and a tag for every module. Every operation uses a declared tag, has responses, and declares each `{path_param}`. Every documented path and method exists as a Flask route, and every Flask handler is documented. |
| `TestSwaggerRoutes` | `/` and `/openapi.json` return 401 without credentials. `/` and `/docs` render the UI. `/openapi.json` and `/swagger.json` match `OPENAPI_SPEC`. `/favicon.ico` is a PNG. Every `/static/...` asset the page references returns 200. |

The "documented routes exist" check is the one most likely to fail after a refactor. It tells you the spec still advertises an endpoint that was renamed or removed.
