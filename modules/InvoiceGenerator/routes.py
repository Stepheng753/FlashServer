import io
from flask import Blueprint, jsonify, render_template, request, send_file, abort
from .db import (
    init_db,
    get_senders,
    get_sender_by_id,
    add_sender,
    update_sender,
    set_default_sender,
    delete_sender,
    get_clients,
    get_client_by_id,
    add_client,
    update_client,
    delete_client,
    get_all_presets,
    get_preset_by_id,
    get_presets_by_client,
    add_preset,
    update_preset,
    delete_preset,
    generate_next_invoice_number,
    get_invoices,
    get_invoice_by_id,
    create_invoice,
    update_invoice,
    update_invoice_status,
    duplicate_invoice,
    delete_invoice,
    get_invoices_summary,
    format_phone,
    process_recurring_invoices,
    get_recurring_presets
)
from .pdf import generate_invoice_pdf

invoice_bp = Blueprint('invoices', __name__, template_folder='.')

# Initialize DB when module loads
init_db()


# ---------------------------------------------------------------------------
# PAGE VIEWS
# ---------------------------------------------------------------------------

@invoice_bp.route("/invoices", methods=["GET"])
def invoices_page():
    """Renders the main interactive Invoicing Console & Management UI."""
    return render_template("invoices.html")


@invoice_bp.route("/invoices/<int:invoice_id>/preview", methods=["GET"])
def invoice_preview_page(invoice_id):
    """Renders a clean, print-ready HTML preview on-demand from stored invoice data."""
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        abort(404, description="Invoice not found.")

    if invoice.get("sender_info") and invoice["sender_info"].get("phone"):
        invoice["sender_info"]["formatted_phone"] = format_phone(invoice["sender_info"]["phone"])
    if invoice.get("client_info") and invoice["client_info"].get("phone"):
        invoice["client_info"]["formatted_phone"] = format_phone(invoice["client_info"]["phone"])

    return render_template("invoice_print.html", invoice=invoice, items=invoice.get("items", []))


# ---------------------------------------------------------------------------
# DASHBOARD SUMMARY & NEXT INVOICE NUMBER
# ---------------------------------------------------------------------------

@invoice_bp.route("/api/invoices/summary", methods=["GET"])
def api_get_summary():
    """Returns aggregated metrics for the dashboard summary cards with optional filters."""
    status = request.args.get("status")
    client_id = request.args.get("client_id")
    sender_id = request.args.get("sender_id")
    search = request.args.get("search")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    summary = get_invoices_summary(
        status=status,
        client_id=client_id,
        sender_id=sender_id,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify(summary)


@invoice_bp.route("/api/invoices/next-number", methods=["GET"])
def api_get_next_number():
    """Returns the next auto-incremented invoice number for the current year."""
    next_num = generate_next_invoice_number()
    return jsonify({"next_number": next_num})


# ---------------------------------------------------------------------------
# SENDER PROFILES API
# ---------------------------------------------------------------------------

@invoice_bp.route("/api/invoices/senders", methods=["GET"])
def api_get_senders():
    """Lists all sender profiles (companies / business entities)."""
    return jsonify(get_senders())


@invoice_bp.route("/api/invoices/senders/<int:sender_id>", methods=["GET"])
def api_get_sender(sender_id):
    """Retrieves a single sender profile."""
    sender = get_sender_by_id(sender_id)
    if not sender:
        return jsonify({"error": "Sender profile not found"}), 404
    return jsonify(sender)


@invoice_bp.route("/api/invoices/senders", methods=["POST"])
def api_add_sender():
    """Creates a new sender profile."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Sender name is required"}), 400

    new_id = add_sender(
        name=name,
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        website=data.get("website", ""),
        payment_instructions=data.get("payment_instructions", ""),
        default_notes=data.get("default_notes", ""),
        is_default=1 if data.get("is_default") else 0
    )
    return jsonify({"success": True, "sender_id": new_id}), 201


@invoice_bp.route("/api/invoices/senders/<int:sender_id>", methods=["PUT"])
def api_update_sender(sender_id):
    """Updates an existing sender profile."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Sender name is required"}), 400

    success = update_sender(
        sender_id=sender_id,
        name=name,
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        website=data.get("website", ""),
        payment_instructions=data.get("payment_instructions", ""),
        default_notes=data.get("default_notes", ""),
        is_default=1 if data.get("is_default") else 0
    )
    if not success:
        return jsonify({"error": "Sender profile not found"}), 404
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/senders/<int:sender_id>/default", methods=["PATCH"])
def api_set_default_sender(sender_id):
    """Sets the designated sender profile as default."""
    success = set_default_sender(sender_id)
    if not success:
        return jsonify({"error": "Sender profile not found"}), 404
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/senders/<int:sender_id>", methods=["DELETE"])
def api_delete_sender(sender_id):
    """Deletes a sender profile."""
    success = delete_sender(sender_id)
    if not success:
        return jsonify({"error": "Sender profile not found"}), 404
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# CLIENTS API
# ---------------------------------------------------------------------------

@invoice_bp.route("/api/invoices/clients", methods=["GET"])
def api_get_clients():
    """Lists all saved clients."""
    return jsonify(get_clients())


@invoice_bp.route("/api/invoices/clients/<int:client_id>", methods=["GET"])
def api_get_client(client_id):
    """Retrieves a single client."""
    client = get_client_by_id(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404
    return jsonify(client)


@invoice_bp.route("/api/invoices/clients", methods=["POST"])
def api_add_client():
    """Creates a new client."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Client name is required"}), 400

    new_id = add_client(
        name=name,
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        notes=data.get("notes", "")
    )
    return jsonify({"success": True, "client_id": new_id}), 201


@invoice_bp.route("/api/invoices/clients/<int:client_id>", methods=["PUT"])
def api_update_client(client_id):
    """Updates an existing client."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Client name is required"}), 400

    success = update_client(
        client_id=client_id,
        name=name,
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        notes=data.get("notes", "")
    )
    if not success:
        return jsonify({"error": "Client not found"}), 404
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/clients/<int:client_id>", methods=["DELETE"])
def api_delete_client(client_id):
    """Deletes a client and cascades to their presets."""
    success = delete_client(client_id)
    if not success:
        return jsonify({"error": "Client not found"}), 404
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# CLIENT PRESETS API
# ---------------------------------------------------------------------------

@invoice_bp.route("/api/invoices/presets", methods=["GET"])
def api_get_all_presets():
    """Lists all presets across all clients."""
    return jsonify(get_all_presets())


@invoice_bp.route("/api/invoices/presets/detail/<int:preset_id>", methods=["GET"])
def api_get_preset_detail(preset_id):
    """Returns a single preset by ID."""
    p = get_preset_by_id(preset_id)
    if not p:
        return jsonify({"error": "Preset not found"}), 404
    return jsonify(p)


@invoice_bp.route("/api/invoices/presets/<int:client_id>", methods=["GET"])
def api_get_client_presets(client_id):
    """Lists reusable recurring invoice presets for a given client."""
    return jsonify(get_presets_by_client(client_id))


@invoice_bp.route("/api/invoices/presets", methods=["POST"])
def api_add_preset():
    """Saves a recurring preset for a client."""
    data = request.get_json(force=True, silent=True) or {}
    client_id = data.get("client_id")
    preset_name = (data.get("preset_name") or "").strip()

    if not client_id or not preset_name:
        return jsonify({"error": "client_id and preset_name are required"}), 400

    new_id = add_preset(
        client_id=client_id,
        preset_name=preset_name,
        default_due_days=data.get("default_due_days", 14),
        items=data.get("items", []),
        notes=data.get("notes", ""),
        discount_amount=data.get("discount_amount", 0.0),
        tax_rate=data.get("tax_rate", 0.0),
        payment_instructions=data.get("payment_instructions", ""),
        is_recurring=1 if data.get("is_recurring") else 0,
        recurrence_type=data.get("recurrence_type", "monthly"),
        recurrence_day=data.get("recurrence_day", 1),
        recurrence_start_date=data.get("recurrence_start_date", ""),
        sender_id=data.get("sender_id"),
        auto_status=data.get("auto_status", "draft")
    )
    return jsonify({"success": True, "preset_id": new_id}), 201


@invoice_bp.route("/api/invoices/presets/<int:preset_id>", methods=["PUT"])
def api_update_preset(preset_id):
    """Updates an existing preset including line items and recurrence settings."""
    data = request.get_json(force=True, silent=True) or {}
    preset_name = (data.get("preset_name") or "").strip()
    if not preset_name:
        return jsonify({"error": "preset_name is required"}), 400

    success = update_preset(
        preset_id=preset_id,
        preset_name=preset_name,
        default_due_days=data.get("default_due_days", 14),
        items=data.get("items", []),
        notes=data.get("notes", ""),
        discount_amount=data.get("discount_amount", 0.0),
        tax_rate=data.get("tax_rate", 0.0),
        payment_instructions=data.get("payment_instructions", ""),
        is_recurring=1 if data.get("is_recurring") else 0,
        recurrence_type=data.get("recurrence_type", "monthly"),
        recurrence_day=data.get("recurrence_day", 1),
        recurrence_start_date=data.get("recurrence_start_date", ""),
        sender_id=data.get("sender_id"),
        auto_status=data.get("auto_status", "draft")
    )
    if not success:
        return jsonify({"error": "Preset not found"}), 404
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/presets/<int:preset_id>", methods=["DELETE"])
def api_delete_preset(preset_id):
    """Deletes a preset."""
    success = delete_preset(preset_id)
    if not success:
        return jsonify({"error": "Preset not found"}), 404
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/recurring/run", methods=["GET", "POST"])
def api_run_recurring():
    """
    Endpoint triggered by daily cron job to evaluate recurring invoice presets
    and generate invoices whose recurrence rule matches the target date.
    Accepts optional ?date=YYYY-MM-DD query parameter or JSON body for manual triggers / testing.
    """
    target_date = request.args.get("date")
    if not target_date and request.is_json:
        target_date = (request.get_json(silent=True) or {}).get("date")

    result = process_recurring_invoices(target_date=target_date)
    return jsonify(result)


@invoice_bp.route("/api/invoices/recurring", methods=["GET"])
def api_get_recurring_presets():
    """Lists all active recurring invoice presets."""
    presets = get_recurring_presets()
    return jsonify(presets)


# ---------------------------------------------------------------------------
# INVOICES API
# ---------------------------------------------------------------------------

@invoice_bp.route("/api/invoices", methods=["GET"])
def api_get_invoices():
    """
    Lists past invoices with optional search, status filtering, client, sender,
    and date range filters.
    """
    status = request.args.get("status")
    client_id = request.args.get("client_id")
    sender_id = request.args.get("sender_id")
    search = request.args.get("search")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    sort_by = request.args.get("sort_by", "issue_date")
    sort_order = request.args.get("sort_order", "desc")

    invoices = get_invoices(
        status=status,
        client_id=client_id,
        sender_id=sender_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return jsonify(invoices)


@invoice_bp.route("/api/invoices/<int:invoice_id>", methods=["GET"])
def api_get_invoice(invoice_id):
    """Retrieves full invoice details with line items and historical snapshots."""
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    return jsonify(invoice)


@invoice_bp.route("/api/invoices", methods=["POST"])
def api_create_invoice():
    """Creates a new invoice and line items."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        new_id = create_invoice(data)
        created = get_invoice_by_id(new_id)
        return jsonify({
            "success": True,
            "invoice_id": new_id,
            "invoice_number": created.get("invoice_number") if created else None
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@invoice_bp.route("/api/invoices/<int:invoice_id>", methods=["PUT"])
def api_update_invoice(invoice_id):
    """Updates an invoice and replaces its line items."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        success = update_invoice(invoice_id, data)
        if not success:
            return jsonify({"error": "Invoice not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@invoice_bp.route("/api/invoices/<int:invoice_id>/status", methods=["PATCH"])
def api_update_invoice_status(invoice_id):
    """Updates invoice status (draft, sent, paid, overdue, void)."""
    data = request.get_json(force=True, silent=True) or {}
    status = data.get("status")
    if not status:
        return jsonify({"error": "status is required"}), 400

    success = update_invoice_status(invoice_id, status)
    if not success:
        return jsonify({"error": "Invalid status or invoice not found"}), 400
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/<int:invoice_id>/duplicate", methods=["POST"])
def api_duplicate_invoice(invoice_id):
    """Clones an invoice into a fresh draft with today's date and next invoice #."""
    new_id = duplicate_invoice(invoice_id)
    if not new_id:
        return jsonify({"error": "Invoice not found"}), 404
    created = get_invoice_by_id(new_id)
    return jsonify({
        "success": True,
        "invoice_id": new_id,
        "invoice_number": created.get("invoice_number") if created else None
    }), 201


@invoice_bp.route("/api/invoices/<int:invoice_id>", methods=["DELETE"])
def api_delete_invoice(invoice_id):
    """Permanently deletes an invoice record and its items."""
    success = delete_invoice(invoice_id)
    if not success:
        return jsonify({"error": "Invoice not found"}), 404
    return jsonify({"success": True})


@invoice_bp.route("/api/invoices/<int:invoice_id>/pdf", methods=["GET"])
def api_download_pdf(invoice_id):
    """
    Renders pure-Python ReportLab vector PDF in-memory and streams it as a file download.
    No PDF is written to disk or stored.
    """
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        abort(404, description="Invoice not found.")

    pdf_buffer = generate_invoice_pdf(invoice)
    inv_num = invoice.get("invoice_number", f"invoice_{invoice_id}")
    client_name = invoice.get("client_name_snapshot", "Client")
    safe_client = "".join(c for c in client_name if c.isalnum() or c in (" ", "-", "_")).strip()
    filename = f"{inv_num} - {safe_client}.pdf" if safe_client else f"{inv_num}.pdf"

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )
