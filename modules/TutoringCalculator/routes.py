import datetime
from flask import Blueprint, request, jsonify, redirect, url_for, Response, render_template
from .config import PST, NOTIFICATION_EMAIL, PAY_PARENT_FOLDER_ID
from .apis.google_auth import (
    get_credentials,
    initiate_oauth_flow,
    process_oauth_callback,
    get_redirect_uri
)
from .apis.calendar_api import calculate_tutoring_hours
from .apis.drive_sheets_api import (
    copy_template_sheet,
    get_previous_balances as fetch_previous_balances,
    update_sheet_hours_and_balances,
    update_sheet_pay_status,
    get_pending_text_recipients,
    get_sheet_details,
    find_current_week_sheet,
    find_current_week_sheets,
    get_or_create_year_folder,
    get_drive_service
)
from .apis.twilio_api import send_sms, get_text_logs as read_text_logs
from .apis.email_api import send_calculation_email

tutoring_bp = Blueprint('tutoring', __name__, template_folder='.')


def calculate_billing_dates():
    """
    Calculates previous Monday (if today is Monday, calculates the previous Monday 7 days back)
    and the following Sunday.
    """
    now = datetime.datetime.now(PST)
    today = now.date()
    weekday = today.weekday()  # Monday=0, Sunday=6

    days_since_prev_monday = 7 if weekday == 0 else weekday
    prev_monday = today - datetime.timedelta(days=days_since_prev_monday)
    prev_sunday = prev_monday + datetime.timedelta(days=6)

    return {
        "start_date": prev_monday.strftime("%m.%d.%y"),
        "end_date": prev_sunday.strftime("%m.%d.%y"),
        "start_date_full": prev_monday.isoformat(),
        "end_date_full": prev_sunday.isoformat()
    }


def require_google_creds():
    creds = get_credentials()
    if not creds:
        return None, jsonify({
            "status": "unauthenticated",
            "message": "Google credentials missing or expired. Please authorize at /login_oauth or /TutoringCalculator/login_oauth.",
            "auth_url": url_for('tutoring.login_oauth_route', _external=True)
        }), 401
    return creds, None, None


# --- PRIVACY POLICY ROUTE ---
@tutoring_bp.route("/privacy")
def privacy_route():
    from flask import render_template
    return render_template("privacy.html")


# --- OAUTH ROUTES ---

@tutoring_bp.route("/login_oauth")
def login_oauth_route():
    redirect_uri = get_redirect_uri()
    if 'code' in request.args:
        try:
            process_oauth_callback(redirect_uri, request.url)
            return redirect(url_for('tutoring.tutoring_dashboard'))
        except Exception as e:
            return jsonify({"status": "error", "message": f"OAuth callback failed: {str(e)}"}), 400

    try:
        auth_url = initiate_oauth_flow(redirect_uri, state='swagger')
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to initiate OAuth flow: {str(e)}"}), 500


# --- WEB DASHBOARD ROUTES ---

_YEAR_FOLDER_CACHE = {}


def resolve_year_folder_url(creds, year_str):
    """Retrieves and caches the Google Drive URL for the given calendar year folder."""
    if year_str in _YEAR_FOLDER_CACHE:
        return _YEAR_FOLDER_CACHE[year_str]
    if not creds or not creds.valid:
        return None
    try:
        drive_svc = get_drive_service(creds)
        y_id = get_or_create_year_folder(drive_svc, year_str)
        if y_id:
            url = f"https://drive.google.com/drive/folders/{y_id}"
            _YEAR_FOLDER_CACHE[year_str] = url
            return url
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to resolve year folder for {year_str}: {e}")
    return None


@tutoring_bp.route("/tutoring", methods=["GET"])
@tutoring_bp.route("/tutoring/dashboard", methods=["GET"])
def tutoring_dashboard():
    """Renders the interactive Crossroads Tutoring Billing & Operations Dashboard."""
    dates = calculate_billing_dates()
    pay_folder_url = f"https://drive.google.com/drive/folders/{PAY_PARENT_FOLDER_ID}" if PAY_PARENT_FOLDER_ID else "#"
    creds = get_credentials()
    is_authenticated = creds is not None and creds.valid
    
    current_year = str(datetime.datetime.now(PST).year)
    year_folder_url = resolve_year_folder_url(creds, current_year)
    
    return render_template(
        "tutoring.html",
        dates=dates,
        pay_folder_url=pay_folder_url,
        pay_parent_folder_id=PAY_PARENT_FOLDER_ID,
        is_authenticated=is_authenticated,
        current_year=current_year,
        year_folder_url=year_folder_url or pay_folder_url
    )


@tutoring_bp.route("/api/tutoring/status", methods=["GET"])
@tutoring_bp.route("/api/status", methods=["GET"])
@tutoring_bp.route("/tutoring/status", methods=["GET"])
def tutoring_status():
    """Returns live billing dates, Google auth state, current week sheet metadata, and Drive folders."""
    dates = calculate_billing_dates()
    creds = get_credentials()
    is_authenticated = creds is not None and creds.valid
    pay_folder_url = f"https://drive.google.com/drive/folders/{PAY_PARENT_FOLDER_ID}" if PAY_PARENT_FOLDER_ID else None
    
    current_year = str(datetime.datetime.now(PST).year)
    year_folder_url = resolve_year_folder_url(creds, current_year)

    check_sheet = request.args.get('check_sheet', '0') == '1'
    current_sheet = None
    current_sheets = []
    has_multiple_sheets = False
    if is_authenticated and check_sheet:
        try:
            sheet_files = find_current_week_sheets(creds, dates['start_date'], dates['end_date'])
            for sf in sheet_files:
                s_id = sf['id']
                s_name = sf['name']
                is_pending = "CALCULATED" in s_name.upper()
                current_sheets.append({
                    "id": s_id,
                    "name": s_name,
                    "sheet_url": f"https://docs.google.com/spreadsheets/d/{s_id}/edit",
                    "is_pending_review": is_pending,
                    "status_label": "Pending Review (CALCULATED)" if is_pending else "Approved"
                })

            if len(current_sheets) == 1:
                current_sheet = current_sheets[0]
            elif len(current_sheets) > 1:
                has_multiple_sheets = True
                current_sheet = current_sheets[0]
        except Exception as e:
            current_sheet = {"error": str(e)}

    return jsonify({
        "dates": dates,
        "is_authenticated": is_authenticated,
        "auth_url": url_for('tutoring.login_oauth_route', _external=True) if not is_authenticated else None,
        "pay_parent_folder_id": PAY_PARENT_FOLDER_ID,
        "pay_parent_folder_url": pay_folder_url,
        "current_year": current_year,
        "year_folder_url": year_folder_url or pay_folder_url,
        "current_sheet": current_sheet,
        "current_sheets": current_sheets,
        "has_multiple_sheets": has_multiple_sheets
    }), 200


# --- ONE-CLICK ORCHESTRATION ENDPOINTS ---

@tutoring_bp.route("/api/tutoring/run-calc", methods=["POST"])
@tutoring_bp.route("/api/run-calc", methods=["POST"])
@tutoring_bp.route("/tutoring/run-calc", methods=["POST"])
@tutoring_bp.route("/run-calc", methods=["POST"])
def run_calc_orchestration():
    """
    Executes the end-to-end Monday pay calculation run:
    1. Computes billing dates.
    2. Copies template sheet into Year folder named 'MM.DD.YY - MM.DD.YY CALCULATED'.
    3. Calculates Google Calendar hours.
    4. Retrieves previous week unpaid balances.
    5. Updates spreadsheet with hours and remaining balances.
    6. Sends email notification with summary metrics.
    """
    creds, err_resp, err_code = require_google_creds()
    if err_resp:
        return err_resp, err_code

    req_data = request.get_json(silent=True) or {}
    start_date = request.args.get('start_date') or req_data.get('start_date')
    end_date = request.args.get('end_date') or req_data.get('end_date')

    # send_email parameter: defaults to True so cron jobs without parameters automatically send emails
    send_email_raw = request.args.get('send_email') if 'send_email' in request.args else req_data.get('send_email', True)
    if isinstance(send_email_raw, str):
        send_email = send_email_raw.strip().lower() not in ('false', '0', 'no', 'none', 'off')
    else:
        send_email = bool(send_email_raw)

    if not start_date or not end_date:
        calc_dates = calculate_billing_dates()
        start_date = start_date or calc_dates['start_date']
        end_date = end_date or calc_dates['end_date']

    try:
        # 1. Copy Template
        copy_res = copy_template_sheet(creds, start_date, end_date)
        if copy_res.get("status") == "already_approved" or copy_res.get("already_approved"):
            year_folder_id = copy_res.get('year_folder_id')
            year_folder_url = f"https://drive.google.com/drive/folders/{year_folder_id}" if year_folder_id else None
            pay_folder_url = f"https://drive.google.com/drive/folders/{PAY_PARENT_FOLDER_ID}" if PAY_PARENT_FOLDER_ID else None
            return jsonify({
                "status": "skipped",
                "already_approved": True,
                "message": copy_res.get("message", f"An approved sheet already exists for {start_date} - {end_date}. Calculation skipped."),
                "sheet_id": copy_res.get("sheet_id"),
                "sheet_url": copy_res.get("sheet_url"),
                "sheet_title": copy_res.get("title"),
                "start_date": start_date,
                "end_date": end_date,
                "year_folder_id": year_folder_id,
                "year_folder_url": year_folder_url,
                "pay_parent_folder_url": pay_folder_url,
                "send_email": send_email,
                "email_status": "skipped",
                "email_error": None
            }), 200

        sheet_id = copy_res['sheet_id']
        sheet_url = copy_res['sheet_url']
        year_folder_id = copy_res.get('year_folder_id')

        # 2. Extract actual student names from the copied sheet & scrape matching calendar hours
        from .apis.drive_sheets_api import get_student_names_from_sheet
        sheet_students = get_student_names_from_sheet(creds, sheet_id)
        hours_by_student = calculate_tutoring_hours(creds, start_date, end_date, sheet_student_names=sheet_students)

        # 3. Retrieve Previous Unpaid Balances
        prev_balances = fetch_previous_balances(creds, start_date, end_date)

        # 4. Update Sheet with Hours and Balances
        update_res = update_sheet_hours_and_balances(creds, sheet_id, hours_by_student, prev_balances)

        # 5. Send Notification Email (if enabled)
        if send_email:
            if not year_folder_id:
                sheet_meta = get_sheet_details(creds, sheet_id)
                year_folder_id = sheet_meta.get('parents', [''])[0]

            email_res = send_calculation_email(
                creds=creds,
                sheet_id=sheet_id,
                sheet_url=sheet_url,
                year_folder_id=year_folder_id,
                start_date_str=start_date,
                end_date_str=end_date,
                updated_students=update_res.get('updated_students'),
                total_balance=update_res.get('total_balance')
            )
        else:
            email_res = {
                "status": "skipped",
                "message": "Email sending skipped via send_email=false parameter."
            }

        year_folder_url = f"https://drive.google.com/drive/folders/{year_folder_id}" if year_folder_id else None
        pay_folder_url = f"https://drive.google.com/drive/folders/{PAY_PARENT_FOLDER_ID}" if PAY_PARENT_FOLDER_ID else None

        return jsonify({
            "status": "success",
            "message": f"Successfully calculated tutoring billing for {start_date} - {end_date}." + (" Email notification sent." if send_email and email_res.get('status') in ('sent', 'success') else (" Email skipped." if not send_email else "")),
            "sheet_id": sheet_id,
            "sheet_url": sheet_url,
            "sheet_title": copy_res.get('title'),
            "start_date": start_date,
            "end_date": end_date,
            "total_balance": update_res.get('total_balance', '$0.00'),
            "updated_students": update_res.get('updated_students', []),
            "students_count": len(update_res.get('updated_students', [])),
            "hours_breakdown": hours_by_student,
            "year_folder_id": year_folder_id,
            "year_folder_url": year_folder_url,
            "pay_parent_folder_url": pay_folder_url,
            "send_email": send_email,
            "email_status": email_res.get('status'),
            "email_id": email_res.get('email_id'),
            "email_error": email_res.get('message') if email_res.get('status') == 'error' else None
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@tutoring_bp.route("/api/tutoring/run-send-texts", methods=["POST"])
@tutoring_bp.route("/api/tutoring/send-texts", methods=["POST"])
@tutoring_bp.route("/api/run-send-texts", methods=["POST"])
@tutoring_bp.route("/api/send-texts", methods=["POST"])
@tutoring_bp.route("/tutoring/run-send-texts", methods=["POST"])
@tutoring_bp.route("/run-send-texts", methods=["POST"])
@tutoring_bp.route("/send-texts", methods=["POST"])
def send_texts_route():
    """
    Dispatches SMS payment reminders via Twilio:
    1. Locates current week's sheet in Google Drive (if not supplied via sheet_id).
    2. SAFEGUARD: Aborts if sheet title still contains 'CALCULATED'.
    3. If approved, sends SMS to students with Total Balance > 0 and blank status.
    4. Updates spreadsheet status column to 'Need to Pay'.
    5. Returns audit summary, direct sheet URL, and recent text logs.
    """
    creds, err_resp, err_code = require_google_creds()
    if err_resp:
        return err_resp, err_code

    req_data = request.get_json(silent=True) or {}
    sheet_id = request.args.get('sheet_id') or req_data.get('sheet_id')

    try:
        # If sheet_id is not explicitly provided, auto-locate current week's sheet
        if not sheet_id:
            dates = calculate_billing_dates()
            sheet_files = find_current_week_sheets(creds, dates['start_date'], dates['end_date'])
            if not sheet_files:
                return jsonify({
                    "status": "error",
                    "message": f"No Google Sheet found for the current billing week ({dates['start_date']} - {dates['end_date']}). Please run calculations first."
                }), 404
            if len(sheet_files) > 1:
                names_str = ", ".join(f"'{f.get('name')}'" for f in sheet_files)
                return jsonify({
                    "status": "error",
                    "has_multiple_sheets": True,
                    "message": f"Multiple Google Sheets ({len(sheet_files)}) found for billing week {dates['start_date']} - {dates['end_date']} ({names_str}). SMS sending is disabled until duplicate sheets are resolved in Google Drive.",
                    "files": sheet_files
                }), 400
            sheet_id = sheet_files[0]['id']

        pending_data = get_pending_text_recipients(creds, sheet_id)
        sheet_title = pending_data.get('title', 'Google Sheet')
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

        # Stop if sheet title contains CALCULATED (Safety Gate)
        if pending_data.get('is_pending_review'):
            return jsonify({
                "status": "skipped",
                "is_pending_review": True,
                "message": pending_data.get('message', "Sheet title contains 'CALCULATED'. SMS sending aborted until human review is complete."),
                "sheet_id": sheet_id,
                "sheet_title": sheet_title,
                "sheet_url": sheet_url
            }), 200

        recipients = pending_data.get('recipients', [])
        if not recipients:
            logs = read_text_logs()
            return jsonify({
                "status": "success",
                "is_pending_review": False,
                "message": "No pending text recipients found (all students either paid, already notified, or zero balance).",
                "sent_count": 0,
                "results": [],
                "sheet_id": sheet_id,
                "sheet_title": sheet_title,
                "sheet_url": sheet_url,
                "recent_logs": logs
            }), 200

        sms_results = []
        for recipient in recipients:
            res = send_sms(
                to_phone=recipient['phone'],
                message_body=recipient['text'],
                student_name=recipient['student']
            )
            sms_results.append(res)

        # Convert statuses to Need to Pay
        update_sheet_pay_status(creds, sheet_id)
        logs = read_text_logs()

        return jsonify({
            "status": "success",
            "is_pending_review": False,
            "message": f"Successfully processed {len(sms_results)} text message reminder{'s' if len(sms_results) != 1 else ''}.",
            "sent_count": len(sms_results),
            "results": sms_results,
            "sheet_id": sheet_id,
            "sheet_title": sheet_title,
            "sheet_url": sheet_url,
            "recent_logs": logs
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- LOW-LEVEL STEPWISE ENDPOINTS ---

@tutoring_bp.route("/api/tutoring/dates", methods=["GET"])
@tutoring_bp.route("/api/dates", methods=["GET"])
@tutoring_bp.route("/dates", methods=["GET"])
def get_dates():
    dates = calculate_billing_dates()
    return jsonify(dates), 200


@tutoring_bp.route("/api/tutoring/copy-template", methods=["POST"])
@tutoring_bp.route("/api/copy-template", methods=["POST"])
@tutoring_bp.route("/copy-template", methods=["POST"])
def copy_template():
    creds, err_resp, err_code = require_google_creds()
    if err_resp:
        return err_resp, err_code

    req_data = request.get_json(silent=True) or {}
    start_date = request.args.get('start_date') or req_data.get('start_date')
    end_date = request.args.get('end_date') or req_data.get('end_date')

    if not start_date or not end_date:
        calc_dates = calculate_billing_dates()
        start_date = start_date or calc_dates['start_date']
        end_date = end_date or calc_dates['end_date']

    try:
        res = copy_template_sheet(creds, start_date, end_date)
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@tutoring_bp.route("/api/tutoring/calc-hours", methods=["GET"])
@tutoring_bp.route("/api/calc-hours", methods=["GET"])
@tutoring_bp.route("/calc-hours", methods=["GET"])
def calc_hours():
    creds, err_resp, err_code = require_google_creds()
    if err_resp:
        return err_resp, err_code

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        calc_dates = calculate_billing_dates()
        start_date = start_date or calc_dates['start_date']
        end_date = end_date or calc_dates['end_date']

    try:
        hours = calculate_tutoring_hours(creds, start_date, end_date)
        return jsonify(hours), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@tutoring_bp.route("/api/tutoring/previous-balances", methods=["GET"])
@tutoring_bp.route("/api/previous-balances", methods=["GET"])
@tutoring_bp.route("/previous-balances", methods=["GET"])
def previous_balances():
    creds, err_resp, err_code = require_google_creds()
    if err_resp:
        return err_resp, err_code

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date:
        calc_dates = calculate_billing_dates()
        start_date = calc_dates['start_date']
        end_date = calc_dates['end_date']

    try:
        balances = fetch_previous_balances(creds, start_date, end_date)
        return jsonify(balances), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@tutoring_bp.route("/api/tutoring/update-sheet", methods=["POST"])
@tutoring_bp.route("/api/update-sheet", methods=["POST"])
@tutoring_bp.route("/update-sheet", methods=["POST"])
def update_sheet():
    creds, err_resp, err_code = require_google_creds()
    if err_resp:
        return err_resp, err_code

    req_data = request.get_json(silent=True) or {}
    sheet_id = request.args.get('sheet_id') or req_data.get('sheet_id')
    action = request.args.get('action') or req_data.get('action')

    if not sheet_id or not action:
        return jsonify({"status": "error", "message": "Parameters 'sheet_id' and 'action' are required."}), 400

    if action == "update_hours":
        try:
            start_date = request.args.get('start_date') or req_data.get('start_date')
            end_date = request.args.get('end_date') or req_data.get('end_date')

            if not start_date or not end_date:
                from .apis.drive_sheets_api import get_sheets_service
                sheets_svc = get_sheets_service(creds)
                dates_res = sheets_svc.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range='C1:D1'
                ).execute().get('values', [[]])
                if dates_res and len(dates_res[0]) >= 2:
                    start_date = dates_res[0][0]
                    end_date = dates_res[0][1]

            if not start_date or not end_date:
                calc_dates = calculate_billing_dates()
                start_date = calc_dates['start_date']
                end_date = calc_dates['end_date']

            hours_by_student = calculate_tutoring_hours(creds, start_date, end_date)
            prev_balances = fetch_previous_balances(creds, start_date, end_date)

            res = update_sheet_hours_and_balances(creds, sheet_id, hours_by_student, prev_balances)

            send_email_raw = request.args.get('send_email') if 'send_email' in request.args else req_data.get('send_email', True)
            if isinstance(send_email_raw, str):
                send_email = send_email_raw.strip().lower() not in ('false', '0', 'no', 'none', 'off')
            else:
                send_email = bool(send_email_raw)

            if send_email:
                sheet_meta = get_sheet_details(creds, sheet_id)
                year_folder_id = sheet_meta.get('parents', [''])[0]
                send_calculation_email(
                    creds=creds,
                    sheet_id=sheet_id,
                    sheet_url=res.get('sheet_url'),
                    year_folder_id=year_folder_id,
                    start_date_str=start_date,
                    end_date_str=end_date,
                    updated_students=res.get('updated_students'),
                    total_balance=res.get('total_balance')
                )

            res["action"] = "update_hours"
            res["send_email"] = send_email
            return jsonify(res), 200

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    elif action == "update_pay_status":
        try:
            res = update_sheet_pay_status(creds, sheet_id)
            res["action"] = "update_pay_status"
            return jsonify(res), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": f"Unknown action: '{action}'. Must be 'update_hours' or 'update_pay_status'."}), 400


@tutoring_bp.route("/api/tutoring/text-logs", methods=["GET"])
@tutoring_bp.route("/api/text-logs", methods=["GET"])
@tutoring_bp.route("/text-logs", methods=["GET"])
def get_text_logs_route():
    logs = read_text_logs()
    return Response(logs, mimetype='text/plain'), 200
