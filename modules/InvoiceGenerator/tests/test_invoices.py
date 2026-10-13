import io
import unittest
import os
import sys
import json

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask
from modules.InvoiceGenerator.db import (
    init_db,
    get_senders,
    add_sender,
    get_sender_by_id,
    update_sender,
    set_default_sender,
    delete_sender,
    get_clients,
    add_client,
    get_client_by_id,
    update_client,
    delete_client,
    add_preset,
    update_preset,
    get_presets_by_client,
    get_recurring_presets,
    process_recurring_invoices,
    delete_preset,
    generate_next_invoice_number,
    create_invoice,
    get_invoices,
    get_invoice_by_id,
    update_invoice,
    update_invoice_status,
    duplicate_invoice,
    delete_invoice,
    get_invoices_summary
)
from modules.InvoiceGenerator.pdf import generate_invoice_pdf
from modules.InvoiceGenerator.routes import invoice_bp


class InvoiceGeneratorTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.app = Flask(__name__, template_folder=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.app.config["TESTING"] = True
        cls.app.register_blueprint(invoice_bp)
        cls.client = cls.app.test_client()

    def test_01_sender_crud(self):
        senders = get_senders()
        self.assertGreaterEqual(len(senders), 1)

        # Add new sender
        new_sender_id = add_sender(
            name="Crossroads Tutoring Services",
            email="crossroads@example.com",
            phone="858-555-1234",
            address="San Diego, CA",
            payment_instructions="Zelle to stepheng753@gmail.com"
        )
        self.assertIsNotNone(new_sender_id)

        s = get_sender_by_id(new_sender_id)
        self.assertEqual(s["name"], "Crossroads Tutoring Services")
        self.assertEqual(s["email"], "crossroads@example.com")

        # Update sender
        update_sender(new_sender_id, name="Crossroads Tutoring LLC", email="billing@crossroads.com")
        s2 = get_sender_by_id(new_sender_id)
        self.assertEqual(s2["name"], "Crossroads Tutoring LLC")
        self.assertEqual(s2["email"], "billing@crossroads.com")

        # Set default
        set_default_sender(new_sender_id)
        s3 = get_sender_by_id(new_sender_id)
        self.assertEqual(s3["is_default"], 1)

        # Cleanup
        delete_sender(new_sender_id)
        self.assertIsNone(get_sender_by_id(new_sender_id))

    def test_02_client_and_preset_crud(self):
        # Add client
        client_id = add_client(
            name="Alice Walker",
            email="alice@example.com",
            phone="619-555-4321",
            address="789 Pacific Beach Dr, San Diego, CA",
            notes="SAT Math tutoring"
        )
        self.assertIsNotNone(client_id)
        c = get_client_by_id(client_id)
        self.assertEqual(c["name"], "Alice Walker")

        # Add preset
        items = [{"description": "SAT Math Tutoring (2 hrs)", "quantity": 2, "unit_price": 65.0}]
        preset_id = add_preset(
            client_id=client_id,
            preset_name="Weekly 2hr SAT Tutoring",
            default_due_days=7,
            items=items,
            notes="Please send confirmation upon payment."
        )
        self.assertIsNotNone(preset_id)

        presets = get_presets_by_client(client_id)
        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0]["preset_name"], "Weekly 2hr SAT Tutoring")
        self.assertEqual(len(presets[0]["items"]), 1)

        # Update preset with new line items
        updated_items = [
            {"description": "SAT Math Tutoring (2 hrs)", "quantity": 2, "unit_price": 70.0},
            {"description": "Prep Materials Workbook", "quantity": 1, "unit_price": 25.0}
        ]
        up_ok = update_preset(preset_id, preset_name="Weekly SAT Tutoring & Materials", items=updated_items, default_due_days=15)
        self.assertTrue(up_ok)

        presets = get_presets_by_client(client_id)
        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0]["preset_name"], "Weekly SAT Tutoring & Materials")
        self.assertEqual(len(presets[0]["items"]), 2)
        self.assertEqual(presets[0]["default_due_days"], 15)

        # Test PUT /api/invoices/presets/<id>
        resp = self.client.put(f"/api/invoices/presets/{preset_id}", json={
            "preset_name": "API Updated Preset",
            "items": [{"description": "Single Lesson", "quantity": 1, "unit_price": 50.0}],
            "default_due_days": 15
        })
        self.assertEqual(resp.status_code, 200)
        p_check = get_presets_by_client(client_id)[0]
        self.assertEqual(p_check["preset_name"], "API Updated Preset")
        self.assertEqual(len(p_check["items"]), 1)
        self.assertEqual(p_check["items"][0]["description"], "Single Lesson")

        # Test GET /api/invoices/presets (all presets)
        resp_all = self.client.get("/api/invoices/presets")
        self.assertEqual(resp_all.status_code, 200)
        all_presets_data = resp_all.get_json()
        self.assertTrue(any(p["id"] == preset_id for p in all_presets_data))

        # Test GET /api/invoices/presets/detail/<id>
        resp_detail = self.client.get(f"/api/invoices/presets/detail/{preset_id}")
        self.assertEqual(resp_detail.status_code, 200)
        detail_data = resp_detail.get_json()
        self.assertEqual(detail_data["preset_name"], "API Updated Preset")
        self.assertEqual(len(detail_data["items"]), 1)

        # Delete preset and client
        delete_preset(preset_id)
        self.assertEqual(len(get_presets_by_client(client_id)), 0)

        delete_client(client_id)
        self.assertIsNone(get_client_by_id(client_id))

    def test_03_invoice_lifecycle_and_calculations(self):
        client_id = add_client(
            name="Bob Martin",
            email="bob@example.com",
            address="100 Ocean Blvd"
        )

        inv_num = generate_next_invoice_number()
        self.assertTrue(inv_num.startswith("INV-"))

        # Create invoice
        data = {
            "invoice_number": inv_num,
            "client_id": client_id,
            "client_name": "Bob Martin",
            "issue_date": "2026-09-26",
            "due_date": "2026-10-10",
            "status": "draft",
            "discount_amount": 10.0,
            "tax_rate": 5.0,
            "items": [
                {"description": "Calculus Tutoring (3 hrs)", "quantity": 3, "unit_price": 70.0},
                {"description": "Practice Materials Booklet", "quantity": 1, "unit_price": 20.0}
            ]
        }
        # Subtotal: 3 * 70 (210) + 1 * 20 (20) = 230
        # Discount: 10 => Discounted: 220
        # Tax: 5% of 220 = 11
        # Total: 220 + 11 = 231
        inv_id = create_invoice(data)
        self.assertIsNotNone(inv_id)

        inv = get_invoice_by_id(inv_id)
        self.assertEqual(inv["subtotal"], 230.0)
        self.assertEqual(inv["discount_amount"], 10.0)
        self.assertEqual(inv["total_amount"], 231.0)
        self.assertEqual(len(inv["items"]), 2)

        # Update status
        self.assertTrue(update_invoice_status(inv_id, "sent"))
        self.assertEqual(get_invoice_by_id(inv_id)["status"], "sent")

        # Duplicate
        dup_id = duplicate_invoice(inv_id)
        self.assertIsNotNone(dup_id)
        dup_inv = get_invoice_by_id(dup_id)
        self.assertEqual(dup_inv["status"], "draft")
        self.assertEqual(dup_inv["total_amount"], 231.0)
        self.assertNotEqual(dup_inv["invoice_number"], inv["invoice_number"])

        # Summary check
        summary = get_invoices_summary()
        self.assertGreaterEqual(summary["total_invoiced"], 231.0)

        # Cleanup
        delete_invoice(inv_id)
        delete_invoice(dup_id)
        delete_client(client_id)

    def test_04_pdf_generation_bytes(self):
        sample_invoice = {
            "invoice_number": "INV-TEST-001",
            "sender_name_snapshot": "Stephen Giang",
            "sender_info": {"email": "stepheng753@gmail.com", "address": "San Diego, CA"},
            "client_name_snapshot": "Test Client",
            "client_info": {"email": "test@example.com"},
            "issue_date": "2026-09-26",
            "due_date": "2026-10-10",
            "status": "sent",
            "subtotal": 100.0,
            "discount_amount": 0.0,
            "tax_rate": 0.0,
            "total_amount": 100.0,
            "payment_instructions": "Zelle: stepheng753@gmail.com",
            "notes": "Thank you!",
            "items": [{"description": "Physics Tutoring", "quantity": 1, "unit_price": 100.0, "amount": 100.0}]
        }
        buf = generate_invoice_pdf(sample_invoice)
        self.assertIsInstance(buf, io.BytesIO)
        content = buf.getvalue()
        self.assertGreater(len(content), 1000)
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertIn(b"/Title (INV-TEST-001 - Test Client)", content)
        self.assertNotIn(b"anonymous", content.lower())

    def test_05_api_endpoints(self):
        # Summary
        resp = self.client.get("/api/invoices/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("total_invoiced", data)
        self.assertIn("outstanding", data)
        self.assertIn("paid", data)

        # Next number
        resp = self.client.get("/api/invoices/next-number")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("next_number", resp.get_json())

        # Senders
        resp = self.client.get("/api/invoices/senders")
        self.assertEqual(resp.status_code, 200)

        # Clients
        resp = self.client.get("/api/invoices/clients")
        self.assertEqual(resp.status_code, 200)

        # Invoices list
        resp = self.client.get("/api/invoices")
        self.assertEqual(resp.status_code, 200)

        # HTML UI Page
        resp = self.client.get("/invoices")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Invoice Generator & History", resp.data)

        # Preview Page
        inv_id = create_invoice({
            "client_name": "Preview Client",
            "client_phone": "8585551234",
            "items": [{"description": "Preview item", "quantity": 1, "unit_price": 50.0}]
        })
        resp = self.client.get(f"/invoices/{inv_id}/preview")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Preview Client", resp.data)
        self.assertIn(b"+1 (858) 555-1234", resp.data)
        resp_del = self.client.delete(f"/api/invoices/{inv_id}")
        self.assertEqual(resp_del.status_code, 200)
        self.assertTrue(resp_del.get_json().get("success"))

    def test_06_recurring_invoices_and_cron_endpoint(self):
        # 1. Setup client
        client_id = add_client("Recurring Test Corp", "recurring@corp.com", "8585559999", "123 Recurring Way")

        # 2. Add monthly recurring preset (e.g. 1st of every month)
        preset_id = add_preset(
            client_id=client_id,
            preset_name="Monthly Retainer 1st",
            default_due_days=14,
            items=[{"description": "Monthly Retainer", "quantity": 1, "unit_price": 1200.0}],
            notes="Recurring monthly invoice",
            is_recurring=1,
            recurrence_type="monthly",
            recurrence_day=1,
            recurrence_start_date="2026-10-01",
            auto_status="draft"
        )
        self.assertGreater(preset_id, 0)

        # 3. Add biweekly recurring preset (Every other Friday starting 2026-10-02)
        # 2026-10-02 is a Friday
        biweekly_id = add_preset(
            client_id=client_id,
            preset_name="Biweekly Tutoring",
            default_due_days=7,
            items=[{"description": "Biweekly Lessons", "quantity": 4, "unit_price": 80.0}],
            is_recurring=1,
            recurrence_type="biweekly",
            recurrence_day=4, # Friday
            recurrence_start_date="2026-10-02",
            auto_status="sent"
        )
        self.assertGreater(biweekly_id, 0)

        # 4. Verify get_recurring_presets
        recurring_presets = get_recurring_presets()
        self.assertTrue(any(p["id"] == preset_id for p in recurring_presets))
        self.assertTrue(any(p["id"] == biweekly_id for p in recurring_presets))

        # 5. Process recurring invoices on a day that should NOT match (2026-10-03 = Saturday)
        result_off_day = process_recurring_invoices(target_date="2026-10-03")
        self.assertTrue(result_off_day["success"])
        self.assertEqual(result_off_day["created_count"], 0)

        # 6. Process recurring invoices on 2026-10-01 (1st of month - matches monthly preset)
        result_first = process_recurring_invoices(target_date="2026-10-01")
        self.assertTrue(result_first["success"])
        self.assertGreaterEqual(result_first["created_count"], 1)
        created_monthly = next((inv for inv in result_first["invoices"] if inv["preset_name"] == "Monthly Retainer 1st"), None)
        self.assertIsNotNone(created_monthly)
        self.assertEqual(created_monthly["preset_name"], "Monthly Retainer 1st")
        self.assertEqual(created_monthly["issue_date"], "2026-10-01")
        self.assertEqual(created_monthly["status"], "draft")

        # 7. Running again on the same day should NOT duplicate (idempotency check)
        result_dup = process_recurring_invoices(target_date="2026-10-01")
        self.assertEqual(result_dup["created_count"], 0)

        # 8. Test Bi-weekly on first recurrence date 2026-10-02 (Friday)
        result_biweekly_1 = process_recurring_invoices(target_date="2026-10-02")
        self.assertGreaterEqual(result_biweekly_1["created_count"], 1)
        created_biweekly = next((inv for inv in result_biweekly_1["invoices"] if inv["preset_name"] == "Biweekly Tutoring"), None)
        self.assertIsNotNone(created_biweekly)
        self.assertEqual(created_biweekly["preset_name"], "Biweekly Tutoring")
        self.assertEqual(created_biweekly["status"], "sent")

        # Next Friday (2026-10-09) is the "off" week for bi-weekly: should NOT trigger
        result_biweekly_off = process_recurring_invoices(target_date="2026-10-09")
        self.assertEqual(result_biweekly_off["created_count"], 0)

        # Second Friday (2026-10-16, 14 days later): SHOULD trigger
        result_biweekly_2 = process_recurring_invoices(target_date="2026-10-16")
        self.assertGreaterEqual(result_biweekly_2["created_count"], 1)
        self.assertTrue(any(inv["preset_name"] == "Biweekly Tutoring" for inv in result_biweekly_2["invoices"]))

        # 9. Test API endpoint GET /api/invoices/recurring
        resp_list = self.client.get("/api/invoices/recurring")
        self.assertEqual(resp_list.status_code, 200)
        self.assertTrue(any(p["id"] == preset_id for p in resp_list.get_json()))

        # 10. Test API endpoint POST /api/invoices/recurring/run with query date
        resp_run = self.client.post("/api/invoices/recurring/run?date=2026-10-01")
        self.assertEqual(resp_run.status_code, 200)
        data_run = resp_run.get_json()
        self.assertTrue(data_run["success"])

        # Clean up created invoices and presets
        for inv_info in result_first["invoices"] + result_biweekly_1["invoices"] + result_biweekly_2["invoices"]:
            delete_invoice(inv_info["id"])
        delete_preset(preset_id)
        delete_preset(biweekly_id)
        delete_client(client_id)


if __name__ == "__main__":
    unittest.main()
