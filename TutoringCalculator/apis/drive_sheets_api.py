import datetime
import re
from googleapiclient.discovery import build
from .. import config
from .calendar_api import parse_date_string


def get_drive_service(creds):
    return build('drive', 'v3', credentials=creds)


def get_sheets_service(creds):
    return build('sheets', 'v4', credentials=creds)


def parse_currency(val):
    """Parses a currency or numeric string like '$ 180.00' into a float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r'[^\d.-]', '', str(val).strip())
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def parse_hours(val):
    """Parses numeric hours string like '1.5' or 2 into a float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r'[^\d.-]', '', str(val).strip())
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0



def is_valid_student_name(val):
    """
    Validates if a cell in Column C represents an active student name.
    Stops processing when Column C no longer has text, is numeric (e.g. subtotal counts),
    or does not contain more than 5 characters.
    """
    if val is None:
        return False
    val_str = str(val).strip()
    if not val_str:
        return False
    # Must have more than 5 characters (first + last name)
    if len(val_str) <= 5:
        return False
    # Must contain alphabetic characters (exclude numeric counts like '6')
    if not any(c.isalpha() for c in val_str):
        return False
    # Exclude common total/summary labels
    if val_str.lower() in ['total', 'totals', 'subtotal', 'subtotals']:
        return False
    return True


def get_or_create_year_folder(drive_service, year_str):
    """Finds or creates the year folder inside PAY_PARENT_FOLDER_ID."""
    parent_folder = config.PAY_PARENT_FOLDER_ID
    query = (
        f"name='{year_str}' and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false and "
        f"'{parent_folder}' in parents"
    )
    res = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = res.get('files', [])
    if files:
        return files[0]['id']

    # Create folder if it doesn't exist
    meta = {
        'name': year_str,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder]
    }
    folder = drive_service.files().create(body=meta, fields='id').execute()
    return folder['id']


def find_file_in_folder(drive_service, file_name, folder_id):
    """Finds a file by exact name inside a specific parent folder."""
    query = f"name='{file_name}' and trashed=false and '{folder_id}' in parents"
    res = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = res.get('files', [])
    return files[0] if files else None


def copy_template_sheet(creds, start_date_str, end_date_str):
    """
    Copies the Student Pay template into the year folder, renames it with 'CALCULATED',
    and updates cells C1 and D1 with start_date and end_date.
    """
    drive_service = get_drive_service(creds)
    sheets_service = get_sheets_service(creds)

    start_date = parse_date_string(start_date_str)
    end_date = parse_date_string(end_date_str)
    year_str = str(start_date.year)

    start_fmt = start_date.strftime("%m.%d.%y")
    end_fmt = end_date.strftime("%m.%d.%y")

    new_file_name = f"{start_fmt} - {end_fmt} CALCULATED"
    year_folder_id = get_or_create_year_folder(drive_service, year_str)

    # Check if an approved sheet (without 'CALCULATED') already exists for this week
    base_name = f"{start_fmt} - {end_fmt}"
    query = (
        f"name contains '{base_name}' and "
        f"mimeType='application/vnd.google-apps.spreadsheet' and "
        f"trashed=false and "
        f"'{year_folder_id}' in parents"
    )
    res = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    existing_sheets = res.get('files', [])
    approved_sheets = [f for f in existing_sheets if 'CALCULATED' not in f.get('name', '').upper()]

    if approved_sheets:
        approved_sheet = approved_sheets[0]
        return {
            "status": "already_approved",
            "already_approved": True,
            "message": f"Approved sheet '{approved_sheet.get('name')}' already exists for billing week {base_name}. Calculation skipped to preserve manual approval.",
            "sheet_id": approved_sheet.get('id'),
            "sheet_url": f"https://docs.google.com/spreadsheets/d/{approved_sheet.get('id')}/edit",
            "title": approved_sheet.get('name'),
            "year_folder_id": year_folder_id
        }

    # If an existing file with the same name exists, delete it first to avoid duplicates
    existing = find_file_in_folder(drive_service, new_file_name, year_folder_id)
    if existing:
        try:
            drive_service.files().delete(fileId=existing['id']).execute()
        except Exception as e:
            print(f"Could not remove existing file: {e}")

    # Copy template into the year folder
    copy_meta = {
        'name': new_file_name,
        'parents': [year_folder_id]
    }
    copied_file = drive_service.files().copy(
        fileId=config.TEMPLATE_SHEET_ID,
        body=copy_meta,
        fields='id, name'
    ).execute()
    sheet_id = copied_file['id']

    # Update C1 with start_fmt and D1 with end_fmt
    sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range='C1:D1',
        valueInputOption='USER_ENTERED',
        body={'values': [[start_fmt, end_fmt]]}
    ).execute()

    return {
        "status": "success",
        "sheet_id": sheet_id,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
        "title": new_file_name,
        "year_folder_id": year_folder_id
    }


def get_previous_week_dates(start_date_str):
    start_date = parse_date_string(start_date_str)
    prev_start = start_date - datetime.timedelta(days=7)
    prev_end = prev_start + datetime.timedelta(days=6)
    return prev_start.strftime("%m.%d.%y"), prev_end.strftime("%m.%d.%y"), str(prev_start.year)


def get_previous_balances(creds, current_start_str, current_end_str):
    """
    Finds previous week's sheet and returns student first names with remaining unpaid balances.
    """
    drive_service = get_drive_service(creds)
    sheets_service = get_sheets_service(creds)

    prev_start_fmt, prev_end_fmt, prev_year_str = get_previous_week_dates(current_start_str)

    year_folder_id = get_or_create_year_folder(drive_service, prev_year_str)

    query = (
        f"name contains '{prev_start_fmt}' and "
        f"name contains '{prev_end_fmt}' and "
        f"mimeType='application/vnd.google-apps.spreadsheet' and "
        f"trashed=false and "
        f"'{year_folder_id}' in parents"
    )
    res = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = res.get('files', [])

    if not files:
        return {}

    prev_sheet_id = files[0]['id']

    # Read rows from row 5 down (columns B to H)
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=prev_sheet_id,
        range='B5:H'
    ).execute()
    rows = result.get('values', [])

    balances = {}
    for row in rows:
        if len(row) < 2:
            break
        status = row[0].strip() if len(row) > 0 else ''
        student_name = row[1].strip() if len(row) > 1 else ''
        if not is_valid_student_name(student_name):
            break

        total_balance_raw = row[6] if len(row) > 6 else 0

        if status.lower() in ['need to pay', 'not paid'] and student_name:
            first_name = student_name.split()[0].capitalize()
            bal = parse_currency(total_balance_raw)
            balances[student_name] = bal
            balances[first_name] = bal

    return balances


def get_student_names_from_sheet(creds, sheet_id=None):
    """
    Reads active student names from Column C (starting at row 5) of the given sheet
    (or master template if sheet_id is None).
    """
    sheets_service = get_sheets_service(creds)
    target_id = sheet_id or config.TEMPLATE_SHEET_ID
    if not target_id:
        return []

    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=target_id,
            range='C5:C'
        ).execute()
        student_rows = result.get('values', [])
        names = []
        for row in student_rows:
            if not row or not row[0].strip():
                break
            full_name = row[0].strip()
            if not is_valid_student_name(full_name):
                break
            names.append(full_name)
        return names
    except Exception as e:
        print(f"Error fetching student names from sheet {target_id}: {e}")
        return []


def update_sheet_hours_and_balances(creds, sheet_id, hours_by_student, previous_balances):
    """
    Updates Column D (# Hours) matching student full names and first names,
    and updates Column G (Remaining Balance) with prior balances.
    Stops processing when Column C no longer has text or is not more than 5 characters,
    preventing overwriting of subtotal / formula rows.
    """
    sheets_service = get_sheets_service(creds)

    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='B5:C'
    ).execute()
    student_rows = result.get('values', [])

    hours_data = []
    balance_data = []
    raw_students = []
    status_clear_updates = []

    for idx, row in enumerate(student_rows, start=5):
        if not row:
            break

        status = row[0].strip() if len(row) > 0 else ''
        full_name = row[1].strip() if len(row) > 1 else ''

        if not full_name or not is_valid_student_name(full_name):
            break

        first_name = full_name.split()[0].capitalize()

        # Match by full name first, then fallback to first name
        hrs = hours_by_student.get(full_name, hours_by_student.get(first_name, 0.0))
        rem_balance = previous_balances.get(full_name, previous_balances.get(first_name, 0.0))

        hours_data.append([hrs])
        balance_data.append([rem_balance])
        raw_students.append({
            "name": full_name,
            "first_name": first_name,
            "hours": hrs,
            "remaining_balance": rem_balance
        })

        # If hours = 0, do not mark status as Need to Pay / Not Paid; clear it if already set
        if hrs <= 0 and status.lower() in ['need to pay', 'not paid']:
            status_clear_updates.append({"range": f"B{idx}", "values": [[""]]})

    total_rows = len(raw_students)
    if total_rows > 0:
        batch_data = [
            {
                "range": f"D5:D{4 + total_rows}",
                "values": hours_data
            },
            {
                "range": f"G5:G{4 + total_rows}",
                "values": balance_data
            }
        ]
        if status_clear_updates:
            batch_data.extend(status_clear_updates)

        batch_body = {
            "valueInputOption": "USER_ENTERED",
            "data": batch_data
        }
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body=batch_body
        ).execute()

    # Re-read C5:H{4 + total_rows} with FORMATTED_VALUE to get evaluated totals directly from Google Sheets
    updated_students = []
    try:
        calculated_range = f"C5:H{4 + total_rows}"
        calc_res = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=calculated_range,
            valueRenderOption='FORMATTED_VALUE'
        ).execute()
        calc_rows = calc_res.get('values', [])
        for r in calc_rows:
            if not r or not r[0].strip():
                continue
            s_name = r[0].strip()
            if not is_valid_student_name(s_name):
                break
            s_hours = r[1].strip() if len(r) > 1 else '0'
            s_rate = r[2].strip() if len(r) > 2 else '$0.00'
            s_subtotal = r[3].strip() if len(r) > 3 else '$0.00'
            s_prev_bal = r[4].strip() if len(r) > 4 else '$0.00'
            s_total = r[5].strip() if len(r) > 5 else '$0.00'

            updated_students.append({
                "student": s_name,
                "name": s_name,
                "first_name": s_name.split()[0].capitalize(),
                "hours": s_hours,
                "rate": s_rate,
                "subtotal": s_subtotal,
                "remaining_balance": s_prev_bal,
                "total": s_total
            })
    except Exception as e:
        print(f"Error fetching calculated student rows: {e}")
        # Fallback to local data if formatted fetch fails
        for s in raw_students:
            updated_students.append({
                "student": s["name"],
                "name": s["name"],
                "first_name": s["first_name"],
                "hours": s["hours"],
                "remaining_balance": s["remaining_balance"],
                "total": f"${s['hours'] * 60:.2f}"
            })

    # Fetch total balance from the summary row (last row of Column H)
    total_balance_str = ""
    summary_row = 4 + total_rows + 1
    try:
        h_res = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"H{summary_row}"
        ).execute()
        vals = h_res.get('values', [])
        if vals and vals[0] and vals[0][0] is not None:
            total_balance_str = str(vals[0][0]).strip()
    except Exception as e:
        print(f"Error fetching Column H summary: {e}")

    # Fallback to last non-empty row in H5:H if needed
    if not total_balance_str:
        try:
            h_all = sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range="H5:H"
            ).execute().get('values', [])
            if h_all and h_all[-1] and h_all[-1][0] is not None:
                total_balance_str = str(h_all[-1][0]).strip()
        except Exception:
            pass

    return {
        "status": "success",
        "sheet_id": sheet_id,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
        "updated_students": updated_students,
        "total_balance": total_balance_str
    }


def update_sheet_pay_status(creds, sheet_id):
    """
    Converts blank student statuses in Column B to 'Need to Pay' for active students
    who have hours > 0.
    If hours == 0, does not mark the status as 'Need to Pay' / 'Not Paid',
    and clears any existing 'Need to Pay' / 'Not Paid' status.
    """
    sheets_service = get_sheets_service(creds)

    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='B5:D'
    ).execute()
    rows = result.get('values', [])

    status_updates = []
    updated_count = 0

    for idx, row in enumerate(rows, start=5):
        status = row[0].strip() if len(row) > 0 else ''
        student_name = row[1].strip() if len(row) > 1 else ''
        hours_raw = row[2] if len(row) > 2 else 0

        if not is_valid_student_name(student_name):
            break

        hrs = parse_hours(hours_raw)

        if student_name:
            if hrs > 0 and not status:
                status_updates.append({"range": f"B{idx}", "values": [["Need to Pay"]]})
                updated_count += 1
            elif hrs <= 0 and status.lower() in ['need to pay', 'not paid']:
                # If hours are 0, do not mark as Not Paid / Need to Pay; clear if set
                status_updates.append({"range": f"B{idx}", "values": [[""]]})

    if status_updates:
        batch_body = {
            "valueInputOption": "USER_ENTERED",
            "data": status_updates
        }
        sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body=batch_body
        ).execute()

    return {
        "status": "success",
        "sheet_id": sheet_id,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
        "updated_count": updated_count
    }


def get_sheet_details(creds, sheet_id):
    """Fetches sheet title and metadata."""
    drive_service = get_drive_service(creds)
    meta = drive_service.files().get(fileId=sheet_id, fields='id, name, parents').execute()
    return meta


def get_pending_text_recipients(creds, sheet_id):
    """
    Checks sheet title for CALCULATED.
    If CALCULATED is present, returns pending approval status.
    If approved (no CALCULATED), returns list of students with Total Balance > 0 and blank status.
    """
    meta = get_sheet_details(creds, sheet_id)
    title = meta.get('name', '')

    if 'CALCULATED' in title.upper():
        return {
            "is_pending_review": True,
            "title": title,
            "message": f"Sheet '{title}' still contains CALCULATED in the title. Remove CALCULATED to approve before sending texts.",
            "recipients": []
        }

    sheets_service = get_sheets_service(creds)
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range='B5:L'
    ).execute()
    rows = result.get('values', [])

    recipients = []
    for idx, row in enumerate(rows, start=5):
        if len(row) < 2:
            break

        status = row[0].strip() if len(row) > 0 else ''
        student = row[1].strip() if len(row) > 1 else ''

        if not is_valid_student_name(student):
            break

        total_balance_raw = row[6] if len(row) > 6 else 0
        phone = row[9].strip() if len(row) > 9 else ''
        text_msg = row[10].strip() if len(row) > 10 else ''

        total_balance = parse_currency(total_balance_raw)

        # Condition: Total balance > 0 and Status is blank
        if student and not status and total_balance > 0 and phone and text_msg:
            recipients.append({
                "row_num": idx,
                "student": student,
                "total_balance": total_balance,
                "phone": phone,
                "text": text_msg
            })

    return {
        "is_pending_review": False,
        "title": title,
        "recipients": recipients
    }


def find_current_week_sheets(creds, start_date_str, end_date_str):
    """Finds all existing Google Sheets matching the week date range inside the year folder."""
    drive_service = get_drive_service(creds)
    start_date = parse_date_string(start_date_str)
    end_date = parse_date_string(end_date_str)
    year_folder_id = get_or_create_year_folder(drive_service, str(start_date.year))

    base_name = f"{start_date.strftime('%m.%d.%y')} - {end_date.strftime('%m.%d.%y')}"
    query = (
        f"name contains '{base_name}' and "
        f"mimeType='application/vnd.google-apps.spreadsheet' and "
        f"trashed=false and "
        f"'{year_folder_id}' in parents"
    )
    res = drive_service.files().list(q=query, spaces='drive', fields='files(id, name, webViewLink)').execute()
    return res.get('files', [])


def find_current_week_sheet(creds, start_date_str, end_date_str):
    """Finds the first existing Google Sheet matching the week date range inside the year folder."""
    files = find_current_week_sheets(creds, start_date_str, end_date_str)
    return files[0] if files else None


