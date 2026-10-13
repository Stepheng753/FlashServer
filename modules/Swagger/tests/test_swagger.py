import base64
import os
import re
import sys
import unittest

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from index.index import get_auth_credentials
from modules.Swagger.swagger import OPENAPI_SPEC
import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def flask_rule_to_openapi(rule):
    """'/api/todo/items/<int:item_id>' -> '/api/todo/items/{item_id}'"""
    return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule)


def app_routes():
    """Set of (openapi_path, METHOD) for every route registered on the real Flask app."""
    routes = set()
    for rule in app.app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            routes.add((flask_rule_to_openapi(rule.rule), method))
    return routes


def undocumented_handlers():
    """
    Flask handlers (endpoint + method) with no documented URL.
    A handler with several URL aliases only needs one of them in the spec.
    Prefixed duplicates (/TutoringCalculator/..., /Finance/..., /InvoiceGenerator/...)
    are separate blueprint registrations of the same handlers and are skipped,
    as are the Swagger module's own routes.
    """
    documented = {(p, m.upper()) for p, m, _ in documented_operations()}
    handlers = {}
    for rule in app.app.url_map.iter_rules():
        endpoint = rule.endpoint
        if endpoint == "static" or endpoint.startswith(("swagger.", "tutoring_calculator.", "invoice_generator.", "finance_dashboard.")):
            continue
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            handlers.setdefault((endpoint, method), []).append(flask_rule_to_openapi(rule.rule))
    return sorted(
        f"{endpoint} {method} {paths}"
        for (endpoint, method), paths in handlers.items()
        if not any((path, method) in documented for path in paths)
    )


def documented_operations():
    for path, item in OPENAPI_SPEC["paths"].items():
        for method, op in item.items():
            if method in HTTP_METHODS:
                yield path, method, op


class TestSwaggerSpec(unittest.TestCase):

    def test_spec_basics(self):
        self.assertTrue(OPENAPI_SPEC["openapi"].startswith("3."))
        self.assertTrue(OPENAPI_SPEC["info"]["title"])
        self.assertTrue(OPENAPI_SPEC["paths"])
        self.assertEqual(OPENAPI_SPEC["servers"][0]["url"], "/")
        self.assertIn("http://localhost:5000", [s["url"] for s in OPENAPI_SPEC["servers"]])

    def test_every_module_has_a_tag(self):
        tags = {t["name"] for t in OPENAPI_SPEC["tags"]}
        for expected in ("Tutoring Calculator", "Monitoring", "To Do", "Invoices", "Finance"):
            self.assertIn(expected, tags)

    def test_operation_tags_are_declared(self):
        declared = {t["name"] for t in OPENAPI_SPEC["tags"]}
        for path, method, op in documented_operations():
            for tag in op.get("tags", []):
                self.assertIn(tag, declared, f"{method.upper()} {path} uses undeclared tag {tag!r}")

    def test_operations_have_responses(self):
        for path, method, op in documented_operations():
            self.assertTrue(op.get("responses"), f"{method.upper()} {path} has no responses")

    def test_path_parameters_are_declared(self):
        for path, method, op in documented_operations():
            declared = {p["name"] for p in op.get("parameters", []) + OPENAPI_SPEC["paths"][path].get("parameters", [])
                        if p.get("in") == "path"}
            for name in re.findall(r"{([^}]+)}", path):
                self.assertIn(name, declared, f"{method.upper()} {path} missing path parameter {name!r}")

    def test_security_scheme_defined(self):
        self.assertTrue(OPENAPI_SPEC["components"]["securitySchemes"])

    def test_documented_paths_exist_in_app(self):
        """Guards against the spec advertising endpoints that no longer exist."""
        routes = app_routes()
        missing = [f"{m.upper()} {p}" for p, m, _ in documented_operations() if (p, m.upper()) not in routes]
        self.assertEqual(missing, [], "Documented in Swagger but not routed in Flask")


    def test_every_handler_is_documented(self):
        """Guards against adding an endpoint without describing it in the spec."""
        self.assertEqual(undocumented_handlers(), [], "Flask handlers missing from the Swagger spec")

    def test_documented_methods_have_summary_or_description(self):
        for path, method, op in documented_operations():
            self.assertTrue(op.get("summary") or op.get("description"), f"{method.upper()} {path} has no summary")


class TestSwaggerRoutes(unittest.TestCase):

    def setUp(self):
        self.client = app.app.test_client()
        u, p = get_auth_credentials()
        self.headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            self.headers["Authorization"] = f"Basic {token}"

    def test_requires_authentication(self):
        self.assertEqual(self.client.get("/").status_code, 401)
        self.assertEqual(self.client.get("/openapi.json").status_code, 401)

    def test_ui_served_at_root_and_docs(self):
        for path in ("/", "/docs"):
            resp = self.client.get(path, headers=self.headers)
            self.assertEqual(resp.status_code, 200, path)
            self.assertIn(b"swagger-ui", resp.data.lower())
            self.assertIn(b"/static/shared.css", resp.data)

    def test_openapi_json_matches_spec(self):
        for path in ("/openapi.json", "/swagger.json"):
            resp = self.client.get(path, headers=self.headers)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["paths"].keys(), OPENAPI_SPEC["paths"].keys())

    def test_favicon_is_png(self):
        resp = self.client.get("/favicon.ico", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/png")
        resp.close()

    def test_assets_referenced_by_ui_exist(self):
        for asset in re.findall(rb'"(/static/[^"]+)"', self.client.get("/", headers=self.headers).data):
            resp = self.client.get(asset.decode(), headers=self.headers)
            self.assertEqual(resp.status_code, 200, asset)
            resp.close()


if __name__ == "__main__":
    unittest.main()
