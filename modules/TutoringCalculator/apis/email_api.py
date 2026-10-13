import base64
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from ..config import NOTIFICATION_EMAIL


def format_currency_val(val):
    """Safely formats currency strings or numbers like '$ 180.00', '$ -', 0, 180.0 to clean '$180.00'."""
    if val is None:
        return "$0.00"
    val_str = str(val).strip()
    if not val_str or val_str in ('$ -', '-', '$ 0.00', '$0.00', '$ 0'):
        return "$0.00"
    if val_str.startswith('$'):
        num_part = val_str.replace('$', '').strip()
        return f"${num_part}"
    try:
        num = float(val_str.replace(',', '').strip())
        return f"${num:,.2f}"
    except (ValueError, TypeError):
        return val_str


def format_total_balance(total_balance):
    if not total_balance:
        return "N/A"
    return format_currency_val(total_balance)


def send_calculation_email(creds, sheet_id, sheet_url, year_folder_id, start_date_str, end_date_str, updated_students=None, total_balance=None):
    """
    Sends an email from and to stepheng753@gmail.com with subject 'Tutoring Pay Calculated'
    linking the new sheet ID, the pay year folder, and student hours with total balance.
    """
    try:
        service = build('gmail', 'v1', credentials=creds)

        recipient = NOTIFICATION_EMAIL
        subject = "Tutoring Pay Calculated"
        folder_url = f"https://drive.google.com/drive/folders/{year_folder_id}"
        total_balance_display = format_total_balance(total_balance)

        # Build student rows for HTML and text
        student_rows_html = ""
        student_rows_text = ""
        if updated_students:
            for s in updated_students:
                s_name = s.get('name') or s.get('student') or 'Student'
                s_hours = s.get('hours', 0)
                s_prev_bal = format_currency_val(s.get('remaining_balance', 0))
                s_subtotal = format_currency_val(s.get('subtotal', 0))
                s_total = format_currency_val(s.get('total', 0))

                student_rows_html += f"<li style='margin-bottom: 6px;'><b>{s_name}</b>: {s_hours} hrs (Subtotal: {s_subtotal} | Prior Balance: {s_prev_bal} | Total Due: <b>{s_total}</b>)</li>"
                student_rows_text += f"  * {s_name}: {s_hours} hrs (Subtotal: {s_subtotal} | Prior Balance: {s_prev_bal} | Total Due: {s_total})\n"

        # Plain-text alternative (helps avoid spam/unverified flags)
        text_body = f"""Tutoring Pay Calculated

Tutoring pay for the week {start_date_str} - {end_date_str} has been calculated.
The sheet has been initialized with CALCULATED in the title. Please review the sheet and remove CALCULATED from its title to approve sending text notifications.

- Calculated Sheet: {sheet_url} (ID: {sheet_id})
- Pay Year Folder: {folder_url}

Students Summary:
{student_rows_text}
Total Balance: {total_balance_display}

--
Automated message from Crossroads Tutoring Server.
"""

        # HTML formatted body
        html_body = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 650px;">
            <h2 style="color: #1a73e8; margin-bottom: 8px;">Tutoring Pay Calculated</h2>
            <p>Tutoring pay for the week <b>{start_date_str} - {end_date_str}</b> has been calculated.</p>
            <p>The sheet has been initialized with <b>CALCULATED</b> in the title. Please review the sheet and remove CALCULATED from its title to approve sending text notifications.</p>
            
            <div style="margin: 20px 0; padding: 15px; background: #f1f3f4; border-radius: 8px;">
                <p style="margin: 6px 0;"><b>Calculated Sheet:</b> <a href="{sheet_url}" target="_blank">{sheet_url}</a><br><span style="font-size: 12px; color: #555;">(ID: {sheet_id})</span></p>
                <p style="margin: 6px 0;"><b>Pay Year Folder:</b> <a href="{folder_url}" target="_blank">{folder_url}</a></p>
            </div>

            {f"<h3 style='margin-bottom: 8px;'>Students Summary:</h3><ul style='padding-left: 20px; margin-top: 4px;'>{student_rows_html}</ul>" if student_rows_html else ""}
            
            <div style="margin-top: 18px; padding: 12px 18px; background: #e6f4ea; border-left: 4px solid #137333; border-radius: 4px;">
                <span style="font-size: 16px; font-weight: bold; color: #137333;">Total Balance: {total_balance_display}</span>
            </div>

            <hr style="border: none; border-top: 1px solid #ddd; margin: 25px 0 15px 0;">
            <p style="font-size: 12px; color: #777;">Automated message from Crossroads Tutoring Server.</p>
        </div>
        """

        message = MIMEMultipart('alternative')
        message['To'] = recipient
        message['From'] = f"Crossroads Tutoring <{recipient}>"
        message['Subject'] = subject
        message['Date'] = email.utils.formatdate(localtime=True)
        message['Message-ID'] = email.utils.make_msgid(domain='gmail.com')

        # Attach plain text first, then HTML (RFC standard for multipart/alternative)
        message.attach(MIMEText(text_body, 'plain', 'utf-8'))
        message.attach(MIMEText(html_body, 'html', 'utf-8'))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent_message = service.users().messages().send(userId='me', body={'raw': raw}).execute()
        print(f"Calculation email sent successfully: {sent_message.get('id')}")
        return {"status": "success", "email_id": sent_message.get('id')}

    except Exception as e:
        print(f"Error sending calculation email: {e}")
        return {"status": "error", "message": str(e)}

