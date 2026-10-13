import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER


import re


def format_currency(value):
    """Formats float or int into $XX.XX currency format."""
    try:
        val = float(value)
        return f"${val:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_phone(phone):
    """Formats a phone number into +1 (XXX) XXX-XXXX."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return str(phone).strip()


def generate_invoice_pdf(invoice):
    """
    Generates a professional, print-ready PDF invoice from an invoice dictionary
    using ReportLab Platypus. Returns an in-memory BytesIO stream positioned at 0.
    """
    buffer = io.BytesIO()

    inv_num = invoice.get("invoice_number", "INV-DRAFT")
    client_name = invoice.get("client_name_snapshot") or "Valued Client"
    sender_name = invoice.get("sender_name_snapshot") or "Stephen Giang"
    pdf_title = f"{inv_num} - {client_name}"

    # Document setup: 0.5 inch margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=pdf_title,
        author=sender_name
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#2d567c")
    secondary_color = colors.HexColor("#548ec4")
    dark_text = colors.HexColor("#1f2937")
    muted_text = colors.HexColor("#4b5563")
    light_bg = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#e2e8f0")

    # Status color mapping
    status = (invoice.get("status") or "draft").lower()
    status_colors = {
        "paid": colors.HexColor("#059669"),
        "sent": colors.HexColor("#2563eb"),
        "overdue": colors.HexColor("#dc2626"),
        "draft": colors.HexColor("#d97706"),
        "void": colors.HexColor("#6b7280")
    }
    status_color = status_colors.get(status, colors.HexColor("#4b5563"))

    style_sender_name = ParagraphStyle(
        "SenderName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color
    )

    style_sender_info = ParagraphStyle(
        "SenderInfo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=muted_text
    )

    style_title = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        alignment=TA_RIGHT,
        textColor=primary_color
    )

    style_meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT,
        textColor=muted_text
    )

    style_meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT,
        textColor=dark_text
    )

    style_section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=primary_color
    )

    style_client_info = ParagraphStyle(
        "ClientInfo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_text
    )

    style_th = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    style_th_right = ParagraphStyle(
        "TableHeaderRight",
        parent=style_th,
        alignment=TA_RIGHT
    )

    style_td = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=dark_text
    )

    style_td_right = ParagraphStyle(
        "TableCellRight",
        parent=style_td,
        alignment=TA_RIGHT
    )

    style_total_label = ParagraphStyle(
        "TotalLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        alignment=TA_RIGHT,
        textColor=muted_text
    )

    style_total_val = ParagraphStyle(
        "TotalVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        alignment=TA_RIGHT,
        textColor=dark_text
    )

    style_grand_total_label = ParagraphStyle(
        "GrandTotalLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        alignment=TA_RIGHT,
        textColor=primary_color
    )

    style_grand_total_val = ParagraphStyle(
        "GrandTotalVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        alignment=TA_RIGHT,
        textColor=primary_color
    )

    style_box_content = ParagraphStyle(
        "BoxContent",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=dark_text
    )

    story = []

    # -----------------------------------------------------------------------
    # 1. HEADER ROW: SENDER (LEFT) & INVOICE META (RIGHT)
    # -----------------------------------------------------------------------
    sender_name = invoice.get("sender_name_snapshot") or "Stephen Giang"
    sender_info = invoice.get("sender_info") or {}

    sender_lines = [f"<b>{sender_name}</b>"]
    if sender_info.get("address"):
        for addr_part in sender_info["address"].split("\n"):
            if addr_part.strip():
                sender_lines.append(addr_part.strip())
    if sender_info.get("email"):
        sender_lines.append(sender_info["email"].strip())
    if sender_info.get("phone"):
        sender_lines.append(format_phone(sender_info["phone"]))
    if sender_info.get("website"):
        sender_lines.append(sender_info["website"].strip())

    left_sender_p = Paragraph("<br/>".join(sender_lines), style_sender_info)

    # Right meta table: INVOICE, Number, Status (only if paid), Issue Date, Due Date
    inv_num = invoice.get("invoice_number", "INV-DRAFT")
    issue_date = invoice.get("issue_date", "")
    due_date = invoice.get("due_date", "")
    status_label = status.upper()

    meta_rows = [
        [Paragraph("<b>INVOICE</b>", style_title)],
        [Paragraph(f"<b>Invoice #:</b> {inv_num}", style_meta_val)],
    ]
    if status == "paid":
        meta_rows.append([Paragraph(f"<b>Status:</b> <font color='{status_color.hexval()}'><b>{status_label}</b></font>", style_meta_val)])

    meta_rows.extend([
        [Paragraph(f"<b>Date:</b> {issue_date}", style_meta_val)],
        [Paragraph(f"<b>Due Date:</b> {due_date}", style_meta_val)],
    ])
    meta_table = Table(meta_rows, colWidths=[240])
    meta_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))

    header_table = Table(
        [[left_sender_p, meta_table]],
        colWidths=[300, 240]
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=0, spaceAfter=14))

    # -----------------------------------------------------------------------
    # 2. BILL TO SECTION
    # -----------------------------------------------------------------------
    client_name = invoice.get("client_name_snapshot") or "Valued Client"
    client_info = invoice.get("client_info") or {}

    client_lines = [f"<b>{client_name}</b>"]
    if client_info.get("address"):
        for addr_part in client_info["address"].split("\n"):
            if addr_part.strip():
                client_lines.append(addr_part.strip())
    if client_info.get("email"):
        client_lines.append(client_info["email"].strip())
    if client_info.get("phone"):
        client_lines.append(format_phone(client_info["phone"]))

    bill_to_content = [
        Paragraph("<b>BILL TO:</b>", style_section_heading),
        Spacer(1, 4),
        Paragraph("<br/>".join(client_lines), style_client_info)
    ]

    bill_to_table = Table([[bill_to_content]], colWidths=[540])
    bill_to_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light_bg),
        ("BOX", (0, 0), (-1, -1), 1, border_color),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))
    story.append(bill_to_table)

    story.append(Spacer(1, 16))

    # -----------------------------------------------------------------------
    # 3. LINE ITEMS TABLE
    # -----------------------------------------------------------------------
    items = invoice.get("items") or []
    # Printable table width: 540 pt (8.5 * 72 - 72 = 540 pt)
    # Col widths: Description 320, Qty 60, Unit Price 80, Amount 80
    table_data = [
        [
            Paragraph("Description", style_th),
            Paragraph("Qty / Hrs", style_th_right),
            Paragraph("Rate", style_th_right),
            Paragraph("Amount", style_th_right)
        ]
    ]

    if not items:
        table_data.append([
            Paragraph("<i>No line items provided.</i>", style_td),
            Paragraph("1.0", style_td_right),
            Paragraph(format_currency(0), style_td_right),
            Paragraph(format_currency(0), style_td_right)
        ])
    else:
        for it in items:
            desc = it.get("description", "")
            qty = it.get("quantity", 1.0)
            # format qty clean if integer
            qty_str = f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}"
            unit_p = format_currency(it.get("unit_price", 0.0))
            amt = format_currency(it.get("amount", 0.0))

            table_data.append([
                Paragraph(desc, style_td),
                Paragraph(qty_str, style_td_right),
                Paragraph(unit_p, style_td_right),
                Paragraph(amt, style_td_right)
            ])

    items_table = Table(
        table_data,
        colWidths=[320, 60, 80, 80]
    )

    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
    ]

    # Alternate row background
    for r_idx in range(1, len(table_data)):
        if r_idx % 2 == 0:
            t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), light_bg))

    items_table.setStyle(TableStyle(t_style))
    story.append(items_table)

    story.append(Spacer(1, 14))

    # -----------------------------------------------------------------------
    # 4. TOTALS SUMMARY TABLE
    # -----------------------------------------------------------------------
    subtotal = float(invoice.get("subtotal", 0.0))
    discount = float(invoice.get("discount_amount", 0.0))
    tax_rate = float(invoice.get("tax_rate", 0.0))
    total_amount = float(invoice.get("total_amount", 0.0))

    totals_rows = [
        [Paragraph("Subtotal:", style_total_label), Paragraph(format_currency(subtotal), style_total_val)]
    ]

    if discount > 0:
        totals_rows.append([
            Paragraph("Discount:", style_total_label),
            Paragraph(f"-{format_currency(discount)}", style_total_val)
        ])

    if tax_rate > 0:
        discounted_sub = max(0.0, subtotal - discount)
        tax_amt = discounted_sub * (tax_rate / 100.0)
        totals_rows.append([
            Paragraph(f"Tax ({tax_rate}%):", style_total_label),
            Paragraph(format_currency(tax_amt), style_total_val)
        ])

    totals_rows.append([
        Paragraph("<b>Total Due:</b>", style_grand_total_label),
        Paragraph(f"<b>{format_currency(total_amount)}</b>", style_grand_total_val)
    ])

    totals_table = Table(totals_rows, colWidths=[120, 100])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, -2), (1, -2), 0.5, border_color),
        ("BACKGROUND", (0, -1), (1, -1), light_bg),
        ("TOPPADDING", (0, -1), (1, -1), 6),
        ("BOTTOMPADDING", (0, -1), (1, -1), 6),
    ]))

    # Wrap totals in a 540-width table aligned right
    totals_container = Table(
        [[Spacer(1, 1), totals_table]],
        colWidths=[320, 220]
    )
    totals_container.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 0)
    ]))
    story.append(totals_container)

    story.append(Spacer(1, 14))

    # -----------------------------------------------------------------------
    # 5. PAYMENT INSTRUCTIONS & NOTES
    # -----------------------------------------------------------------------
    payment_inst = invoice.get("payment_instructions") or ""
    notes = invoice.get("notes") or ""

    bottom_blocks = []
    if payment_inst.strip():
        inst_formatted = "<br/>".join([line.strip() for line in payment_inst.split("\n") if line.strip()])
        bottom_blocks.append(
            Table(
                [[
                    Paragraph("<b>PAYMENT INSTRUCTIONS</b>", style_section_heading)
                ], [
                    Paragraph(inst_formatted, style_box_content)
                ]],
                colWidths=[540]
            )
        )
        bottom_blocks[-1].setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), light_bg),
            ("BOX", (0, 0), (-1, -1), 1, border_color),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
        ]))

    if notes.strip():
        notes_formatted = "<br/>".join([line.strip() for line in notes.split("\n") if line.strip()])
        notes_table = Table(
            [[
                Paragraph("<b>NOTES & TERMS</b>", style_section_heading)
            ], [
                Paragraph(notes_formatted, style_box_content)
            ]],
            colWidths=[540]
        )
        notes_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
        ]))
        if bottom_blocks:
            bottom_blocks.append(Spacer(1, 8))
        bottom_blocks.append(notes_table)

    if bottom_blocks:
        story.append(KeepTogether(bottom_blocks))

    # Footer note
    story.append(Spacer(1, 14))
    style_footer = ParagraphStyle(
        "FooterNote",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=muted_text
    )
    story.append(Paragraph("Thank you for your Business!", style_footer))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
