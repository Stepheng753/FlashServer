import os
import sys
import base64
import unittest

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from index.index import get_auth_credentials
import app

class ServerIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        u, p = get_auth_credentials()
        self.headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            self.headers["Authorization"] = f"Basic {token}"

    def test_invoices_page_registered(self):
        resp = self.client.get("/invoices", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Invoice Generator", resp.data)

    def test_invoices_prefixed_page(self):
        resp = self.client.get("/InvoiceGenerator/invoices", headers=self.headers)
        self.assertEqual(resp.status_code, 200)

    def test_api_summary(self):
        resp = self.client.get("/api/invoices/summary", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("total_invoiced", data)

    def test_swagger_includes_invoices(self):
        resp = self.client.get("/openapi.json", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        spec = resp.get_json()
        self.assertTrue(any(t["name"] == "Invoices" for t in spec["tags"]))
        self.assertIn("/invoices", spec["paths"])
        self.assertIn("/api/invoices/{invoice_id}/pdf", spec["paths"])

if __name__ == "__main__":
    unittest.main()
