import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import datetime
import pytz

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.TutoringCalculator.apis.drive_sheets_api import (
    parse_hours,
    parse_currency,
    is_valid_student_name,
    update_sheet_pay_status,
    update_sheet_hours_and_balances,
    get_previous_balances
)
from modules.TutoringCalculator.apis.calendar_api import calculate_tutoring_hours
from modules.TutoringCalculator.config import PST


class TestTutoringCalculator(unittest.TestCase):

    def test_parse_hours(self):
        self.assertEqual(parse_hours(None), 0.0)
        self.assertEqual(parse_hours(""), 0.0)
        self.assertEqual(parse_hours(0), 0.0)
        self.assertEqual(parse_hours("0"), 0.0)
        self.assertEqual(parse_hours("0.0"), 0.0)
        self.assertEqual(parse_hours(1.5), 1.5)
        self.assertEqual(parse_hours("1.5"), 1.5)
        self.assertEqual(parse_hours(" 2.75 hrs "), 2.75)

    def test_get_previous_balances_status_matching(self):
        """Ensures get_previous_balances recognizes both 'Need to Pay' and 'Not Paid'."""
        mock_creds = MagicMock()
        mock_sheets_svc = MagicMock()
        mock_drive_svc = MagicMock()

        with patch('modules.TutoringCalculator.apis.drive_sheets_api.get_drive_service', return_value=mock_drive_svc), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_sheets_service', return_value=mock_sheets_svc), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_or_create_year_folder', return_value='folder_123'):

            mock_drive_svc.files().list().execute.return_value = {
                'files': [{'id': 'prev_sheet_id', 'name': '09.07.26 - 09.13.26 CALCULATED'}]
            }

            # Row columns: [Status, Student Name, Hours, Rate, Subtotal, PrevBal, TotalBalance]
            mock_sheets_svc.spreadsheets().values().get().execute.return_value = {
                'values': [
                    ['Need to Pay', 'Elijah Dinh', '2', '$60', '$120', '$0', '$120.00'],
                    ['Not Paid', 'Ellie Hoang', '1', '$60', '$60', '$0', '$60.00'],
                    ['Paid', 'Michael Brower', '3', '$60', '$180', '$0', '$0.00'],
                    ['', 'Amelie Meeker', '0', '$60', '$0', '$0', '$0.00'],
                ]
            }

            balances = get_previous_balances(mock_creds, "09.14.26", "09.20.26")
            self.assertEqual(balances.get('Elijah Dinh'), 120.0)
            self.assertEqual(balances.get('Elijah'), 120.0)
            self.assertEqual(balances.get('Ellie Hoang'), 60.0)
            self.assertEqual(balances.get('Ellie'), 60.0)
            self.assertNotIn('Michael Brower', balances)
            self.assertNotIn('Amelie Meeker', balances)

    def test_update_sheet_pay_status_hours_zero_not_marked(self):
        """Verifies that if hours = 0, status is NOT marked as Need to Pay / Not Paid."""
        mock_creds = MagicMock()
        mock_sheets_svc = MagicMock()

        with patch('modules.TutoringCalculator.apis.drive_sheets_api.get_sheets_service', return_value=mock_sheets_svc):
            # Row index starts at 5:
            # Row 5: Elijah - 2.0 hrs, blank status -> should become 'Need to Pay'
            # Row 6: Ellie - 0.0 hrs, blank status -> should STAY blank (not marked)
            # Row 7: Michael - 0.0 hrs, previously marked 'Need to Pay' -> should be CLEARED
            # Row 8: Amelie - 0.0 hrs, previously marked 'Not Paid' -> should be CLEARED
            # Row 9: Jack - 3.0 hrs, already 'Paid' -> untouched
            mock_sheets_svc.spreadsheets().values().get().execute.return_value = {
                'values': [
                    ['', 'Elijah Dinh', '2.0'],
                    ['', 'Ellie Hoang', '0.0'],
                    ['Need to Pay', 'Michael Brower', '0'],
                    ['Not Paid', 'Amelie Meeker', '0.0'],
                    ['Paid', 'Jack Glandorf', '3.0']
                ]
            }

            batch_update_mock = mock_sheets_svc.spreadsheets().values().batchUpdate()
            batch_update_mock.execute.return_value = {}

            res = update_sheet_pay_status(mock_creds, 'test_sheet_id')
            self.assertEqual(res['status'], 'success')

            # Inspect the batch update payload
            call_args = mock_sheets_svc.spreadsheets().values().batchUpdate.call_args
            self.assertIsNotNone(call_args)
            body = call_args[1].get('body') or call_args[0][0]
            updates = body.get('data', [])

            # Row 5 (Elijah, hrs > 0, blank) -> 'Need to Pay'
            # Row 7 (Michael, hrs == 0, 'Need to Pay') -> cleared ''
            # Row 8 (Amelie, hrs == 0, 'Not Paid') -> cleared ''
            # Row 6 (Ellie, hrs == 0, blank) -> MUST NOT BE in updates!
            updates_by_range = {u['range']: u['values'][0][0] for u in updates}

            self.assertEqual(updates_by_range.get('B5'), 'Need to Pay')
            self.assertNotIn('B6', updates_by_range, "Ellie (0 hrs, blank) should not be marked as Need to Pay")
            self.assertEqual(updates_by_range.get('B7'), '', "Michael (0 hrs, pre-existing Need to Pay) should be cleared")
            self.assertEqual(updates_by_range.get('B8'), '', "Amelie (0 hrs, pre-existing Not Paid) should be cleared")
            self.assertNotIn('B9', updates_by_range, "Jack (already Paid) should not be modified")

    def test_update_sheet_hours_and_balances_clears_zero_hour_status(self):
        """Verifies update_sheet_hours_and_balances clears status for 0-hour students if previously marked."""
        mock_creds = MagicMock()
        mock_sheets_svc = MagicMock()

        with patch('modules.TutoringCalculator.apis.drive_sheets_api.get_sheets_service', return_value=mock_sheets_svc):
            # student_rows read from B5:C
            # Row 5: Elijah - status 'Need to Pay', 2.0 hrs
            # Row 6: Ellie - status 'Need to Pay', 0.0 hrs -> should clear B6
            # Row 7: Michael - status '', 0.0 hrs -> remains ''
            mock_sheets_svc.spreadsheets().values().get().execute.side_effect = [
                # First get for B5:C
                {
                    'values': [
                        ['Need to Pay', 'Elijah Dinh'],
                        ['Need to Pay', 'Ellie Hoang'],
                        ['', 'Michael Brower'],
                    ]
                },
                # Second get for FORMATTED_VALUE C5:H7
                {
                    'values': [
                        ['Elijah Dinh', '2.0', '$60', '$120.00', '$0.00', '$120.00'],
                        ['Ellie Hoang', '0.0', '$60', '$0.00', '$0.00', '$0.00'],
                        ['Michael Brower', '0.0', '$60', '$0.00', '$0.00', '$0.00'],
                    ]
                },
                # Third get for H summary
                {'values': [['$120.00']]}
            ]

            mock_sheets_svc.spreadsheets().values().batchUpdate().execute.return_value = {}

            hours_by_student = {'Elijah Dinh': 2.0, 'Ellie Hoang': 0.0, 'Michael Brower': 0.0}
            prev_balances = {}

            res = update_sheet_hours_and_balances(mock_creds, 'test_sheet', hours_by_student, prev_balances)
            self.assertEqual(res['status'], 'success')

            call_args = mock_sheets_svc.spreadsheets().values().batchUpdate.call_args
            body = call_args[1].get('body') or call_args[0][0]
            updates = body.get('data', [])

            updates_by_range = {u['range']: u['values'] for u in updates}
            # Column D (hours) and G (balance) updated
            self.assertIn('D5:D7', updates_by_range)
            self.assertIn('G5:G7', updates_by_range)
            # B6 (Ellie, 0 hrs, had 'Need to Pay') should be cleared
            self.assertIn('B6', updates_by_range)
            self.assertEqual(updates_by_range['B6'], [['']])
            # B5 (Elijah, 2 hrs) and B7 (Michael, already blank) should NOT have status clear updates
            self.assertNotIn('B5', updates_by_range)
            self.assertNotIn('B7', updates_by_range)

    def test_calendar_hours_sunday_to_monday_spanning_event(self):
        """
        Tests the boundary condition:
        An event starts Sunday night at 23:00 PST and ends Monday morning at 01:00 PST.
        - Week 1 (Mon 09.14 - Sun 09.20): MUST count the event (start time is Sun 23:00 <= range_end).
        - Week 2 (Mon 09.21 - Sun 09.27): MUST EXCLUDE the event (start time is Sun 23:00 < range_start).
        """
        mock_creds = MagicMock()
        mock_cal_svc = MagicMock()

        spanning_event = {
            'summary': 'Elijah Tutoring',
            'colorId': None,
            # Sunday 2026-09-20 23:00:00 PST to Monday 2026-09-21 01:00:00 PST
            'start': {'dateTime': '2026-09-20T23:00:00-07:00'},
            'end': {'dateTime': '2026-09-21T01:00:00-07:00'}
        }

        monday_event = {
            'summary': 'Ellie Tutoring',
            'colorId': None,
            # Monday 2026-09-21 16:00:00 PST to 17:30:00 PST (1.5 hrs)
            'start': {'dateTime': '2026-09-21T16:00:00-07:00'},
            'end': {'dateTime': '2026-09-21T17:30:00-07:00'}
        }

        with patch('modules.TutoringCalculator.apis.calendar_api.get_calendar_service', return_value=mock_cal_svc), \
             patch('modules.TutoringCalculator.apis.calendar_api.resolve_calendar_id', return_value='cal_123'):

            # Test Week 1: Mon 09.14.26 to Sun 09.20.26
            # Google Calendar API returns spanning_event because it overlaps
            mock_cal_svc.events().list().execute.return_value = {
                'items': [spanning_event]
            }
            week1_hours = calculate_tutoring_hours(
                mock_creds, "09.14.26", "09.20.26",
                sheet_student_names=['Elijah Dinh', 'Ellie Hoang']
            )
            # Spanning event started on Sunday 09.20, so it belongs to Week 1 (2.0 hrs)
            self.assertEqual(week1_hours.get('Elijah Dinh'), 2.0)
            self.assertEqual(week1_hours.get('Elijah'), 2.0)

            # Test Week 2: Mon 09.21.26 to Sun 09.27.26
            # Google Calendar API returns spanning_event (ended Monday 01:00 > timeMin) AND monday_event
            mock_cal_svc.events().list().execute.return_value = {
                'items': [spanning_event, monday_event]
            }
            week2_hours = calculate_tutoring_hours(
                mock_creds, "09.21.26", "09.27.26",
                sheet_student_names=['Elijah Dinh', 'Ellie Hoang']
            )
            # Spanning event MUST BE EXCLUDED from Week 2 because its start time is before Monday 00:00 PST!
            self.assertNotIn('Elijah Dinh', week2_hours, "Spanning event should not be double-counted in Week 2")
            self.assertNotIn('Elijah', week2_hours)
            # Monday event must be included
            self.assertEqual(week2_hours.get('Ellie Hoang'), 1.5)
            self.assertEqual(week2_hours.get('Ellie'), 1.5)

    def test_multiple_sheets_detection_and_blocking(self):
        """Verifies that finding multiple sheets is detected and blocks send-texts."""
        from modules.TutoringCalculator.apis.drive_sheets_api import find_current_week_sheets, find_current_week_sheet
        mock_creds = MagicMock()
        mock_drive_svc = MagicMock()

        file1 = {'id': 'sheet_1', 'name': '09.14.26 - 09.20.26 CALCULATED'}
        file2 = {'id': 'sheet_2', 'name': '09.14.26 - 09.20.26'}

        with patch('modules.TutoringCalculator.apis.drive_sheets_api.get_drive_service', return_value=mock_drive_svc), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_or_create_year_folder', return_value='folder_123'):

            mock_drive_svc.files().list().execute.return_value = {
                'files': [file1, file2]
            }

            all_sheets = find_current_week_sheets(mock_creds, "09.14.26", "09.20.26")
            self.assertEqual(len(all_sheets), 2)
            self.assertEqual(all_sheets[0]['name'], '09.14.26 - 09.20.26 CALCULATED')
            self.assertEqual(all_sheets[1]['name'], '09.14.26 - 09.20.26')

            first_sheet = find_current_week_sheet(mock_creds, "09.14.26", "09.20.26")
            self.assertEqual(first_sheet['id'], 'sheet_1')

    def test_run_calc_orchestration_send_email_default_true(self):
        """Verifies run_calc_orchestration defaults to sending email when send_email is not passed (cron mode)."""
        from flask import Flask
        from modules.TutoringCalculator.routes import run_calc_orchestration

        app = Flask(__name__)
        mock_creds = MagicMock()

        with app.test_request_context('/tutoring/run-calc', method='POST'), \
             patch('modules.TutoringCalculator.routes.require_google_creds', return_value=(mock_creds, None, None)), \
             patch('modules.TutoringCalculator.routes.copy_template_sheet', return_value={'sheet_id': 's1', 'sheet_url': 'http://sheet', 'year_folder_id': 'y1'}), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_student_names_from_sheet', return_value=['Elijah']), \
             patch('modules.TutoringCalculator.routes.calculate_tutoring_hours', return_value={'Elijah': 2.0}), \
             patch('modules.TutoringCalculator.routes.fetch_previous_balances', return_value={}), \
             patch('modules.TutoringCalculator.routes.update_sheet_hours_and_balances', return_value={'status': 'success', 'updated_students': [], 'total_balance': '$120.00'}), \
             patch('modules.TutoringCalculator.routes.send_calculation_email', return_value={'status': 'sent', 'email_id': 'msg_123'}) as mock_email:

            resp, code = run_calc_orchestration()
            self.assertEqual(code, 200)
            data = resp.get_json()
            self.assertTrue(data['send_email'])
            self.assertEqual(data['email_status'], 'sent')
            mock_email.assert_called_once()

    def test_run_calc_orchestration_send_email_false(self):
        """Verifies run_calc_orchestration skips sending email when send_email=false is passed (UI mode)."""
        from flask import Flask
        from modules.TutoringCalculator.routes import run_calc_orchestration

        app = Flask(__name__)
        mock_creds = MagicMock()

        with app.test_request_context('/tutoring/run-calc?send_email=false', method='POST'), \
             patch('modules.TutoringCalculator.routes.require_google_creds', return_value=(mock_creds, None, None)), \
             patch('modules.TutoringCalculator.routes.copy_template_sheet', return_value={'sheet_id': 's1', 'sheet_url': 'http://sheet', 'year_folder_id': 'y1'}), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_student_names_from_sheet', return_value=['Elijah']), \
             patch('modules.TutoringCalculator.routes.calculate_tutoring_hours', return_value={'Elijah': 2.0}), \
             patch('modules.TutoringCalculator.routes.fetch_previous_balances', return_value={}), \
             patch('modules.TutoringCalculator.routes.update_sheet_hours_and_balances', return_value={'status': 'success', 'updated_students': [], 'total_balance': '$120.00'}), \
             patch('modules.TutoringCalculator.routes.send_calculation_email') as mock_email:

            resp, code = run_calc_orchestration()
            self.assertEqual(code, 200)
            data = resp.get_json()
            self.assertFalse(data['send_email'])
            self.assertEqual(data['email_status'], 'skipped')
            mock_email.assert_not_called()

    def test_copy_template_sheet_skips_if_approved_exists(self):
        """Verifies copy_template_sheet returns already_approved and does not copy template if approved sheet exists."""
        from modules.TutoringCalculator.apis.drive_sheets_api import copy_template_sheet
        mock_creds = MagicMock()
        mock_drive_svc = MagicMock()
        mock_sheets_svc = MagicMock()

        approved_file = {'id': 'approved_sheet_id', 'name': '09.14.26 - 09.20.26'}

        with patch('modules.TutoringCalculator.apis.drive_sheets_api.get_drive_service', return_value=mock_drive_svc), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_sheets_service', return_value=mock_sheets_svc), \
             patch('modules.TutoringCalculator.apis.drive_sheets_api.get_or_create_year_folder', return_value='folder_123'):

            mock_drive_svc.files().list().execute.return_value = {
                'files': [approved_file]
            }

            res = copy_template_sheet(mock_creds, "09.14.26", "09.20.26")
            self.assertEqual(res['status'], 'already_approved')
            self.assertTrue(res['already_approved'])
            self.assertEqual(res['sheet_id'], 'approved_sheet_id')
            self.assertEqual(res['title'], '09.14.26 - 09.20.26')
            # Verify copy was never called
            mock_drive_svc.files().copy.assert_not_called()

    def test_run_calc_orchestration_skips_if_already_approved(self):
        """Verifies run_calc_orchestration gracefully returns status='skipped' if sheet is already approved."""
        from flask import Flask
        from modules.TutoringCalculator.routes import run_calc_orchestration

        app = Flask(__name__)
        mock_creds = MagicMock()

        with app.test_request_context('/tutoring/run-calc', method='POST'), \
             patch('modules.TutoringCalculator.routes.require_google_creds', return_value=(mock_creds, None, None)), \
             patch('modules.TutoringCalculator.routes.copy_template_sheet', return_value={
                 'status': 'already_approved',
                 'already_approved': True,
                 'sheet_id': 'appr_1',
                 'sheet_url': 'http://sheet',
                 'title': '09.14.26 - 09.20.26',
                 'year_folder_id': 'y1'
             }), \
             patch('modules.TutoringCalculator.routes.calculate_tutoring_hours') as mock_calc, \
             patch('modules.TutoringCalculator.routes.send_calculation_email') as mock_email:

            resp, code = run_calc_orchestration()
            self.assertEqual(code, 200)
            data = resp.get_json()
            self.assertEqual(data['status'], 'skipped')
            self.assertTrue(data['already_approved'])
            self.assertEqual(data['sheet_id'], 'appr_1')
            mock_calc.assert_not_called()
            mock_email.assert_not_called()



    def test_tutoring_api_routes_registered(self):
        """Verifies that /api/tutoring/... endpoints are properly registered on the blueprint."""
        from flask import Flask
        from modules.TutoringCalculator.routes import tutoring_bp

        app = Flask(__name__)
        app.register_blueprint(tutoring_bp)
        client = app.test_client()

        # Test /api/tutoring/dates endpoint
        resp = client.get('/api/tutoring/dates')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('start_date', data)
        self.assertIn('end_date', data)

        # Test /api/tutoring/text-logs endpoint
        with patch('modules.TutoringCalculator.routes.read_text_logs', return_value='[Log test]'):
            resp = client.get('/api/tutoring/text-logs')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data.decode('utf-8'), '[Log test]')

        # Test /api/tutoring/status endpoint without Google credentials
        with patch('modules.TutoringCalculator.routes.get_credentials', return_value=None):
            resp = client.get('/api/tutoring/status')
            self.assertEqual(resp.status_code, 200)
            status_data = resp.get_json()
            self.assertFalse(status_data['is_authenticated'])
            self.assertIn('dates', status_data)
            self.assertIn('start_date', status_data['dates'])


if __name__ == '__main__':
    unittest.main()



