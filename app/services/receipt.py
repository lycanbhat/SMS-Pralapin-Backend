"""Receipt PDF generation (ReportLab primary, WeasyPrint fallback); A5, minimal layout."""
import io
import logging
import uuid
from datetime import datetime
from typing import Optional

from app.config import settings
from app.models.billing import Billing
from app.services.s3 import upload_receipt_to_s3

logger = logging.getLogger(__name__)

# Receipt context (student/branch info for header)
ReceiptContext = Optional[dict]  # student_name, class_name, branch_name


def _number_to_words_indian(n: float) -> str:
    """Convert number to words (Indian style). E.g. 52000 -> 'Rupees Fifty Two Thousand Only'."""
    n = int(round(n))
    if n == 0:
        return "Rupees Zero Only"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]

    def up_to_99(x: int) -> str:
        if x < 10:
            return ones[x]
        if x < 20:
            return teens[x - 10]
        t, o = divmod(x, 10)
        return (tens[t] + " " + ones[o]).strip()

    def up_to_999(x: int) -> str:
        if x < 100:
            return up_to_99(x)
        h, r = divmod(x, 100)
        return (ones[h] + " Hundred " + up_to_99(r)).strip() if r else (ones[h] + " Hundred").strip()

    def up_to_lakh(x: int) -> str:
        if x < 1000:
            return up_to_999(x)
        q, r = divmod(x, 1000)
        return (up_to_999(q) + " Thousand " + up_to_999(r)).strip() if r else (up_to_999(q) + " Thousand").strip()

    if n < 0:
        return "Rupees (Negative) Only"
    if n >= 100_000_00:  # 1 crore+
        c, r = divmod(n, 100_000_00)
        return ("Rupees " + up_to_lakh(c) + " Crore " + up_to_lakh(r) + " Only").strip()
    if n >= 100_000:  # 1 lakh+
        l, r = divmod(n, 100_000)
        return ("Rupees " + up_to_lakh(l) + " Lakh " + up_to_lakh(r) + " Only").strip()
    return "Rupees " + up_to_lakh(n) + " Only"


async def generate_receipt_pdf_bytes(billing: Billing, context: ReceiptContext = None) -> bytes | None:
    """Generate PDF receipt bytes (A5, minimal). context: student_name, class_name, branch_name."""
    pdf = _reportlab_pdf_bytes(billing, context)
    if pdf:
        return pdf
    try:
        from weasyprint import HTML
        html = _receipt_html(billing)
        return HTML(string=html).write_pdf()
    except (ImportError, OSError, Exception):
        return None


def _reportlab_pdf_bytes(billing: Billing, context: ReceiptContext = None) -> bytes | None:
    """
    Build receipt PDF using ReportLab, matching the provided design.

    Layout (A5 portrait, approximated to 100% of the sample):
      - Top: school logo (or name) on left, "Receipt #" and "Date" on right.
      - Next row: "Name of the Student : ...".
      - Next row: "Admission Number: ...   Class: ...   Branch: ...".
      - Centered title: "RECEIPT OF PAYMENT".
      - Fee structure table: header (Fee Structure | Amount), one row per component, then Total row.
      - "Amount in words: Rupees ... Only".
      - Notes / Authorised Signatory row (two columns).
      - Footer: school name / address.
    """
    try:
        from reportlab.lib.pagesizes import A5
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        return None
    try:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A5)
        w, h = A5
        # Page margin: 6mm on all sides (as requested)
        margin_x = 6 * mm
        margin_y = 6 * mm
        y = h - margin_y
        line_h = 6 * mm
        small_h = 4 * mm

        school_name = (settings.school_name or settings.app_name).strip()
        school_address = (settings.school_address or "").strip()
        logo_url = (settings.school_logo_url or "").strip()
        trust_logo_url = (getattr(settings, "trust_logo_url", "") or "").strip()
        trust_address = (getattr(settings, "trust_address", "") or "").strip()

        # Use consistent border color for all drawn borders/lines
        from reportlab.lib import colors as _rl_colors
        border_color = _rl_colors.HexColor("#707070")
        c.setStrokeColor(border_color)

        # === Header: Logo / school name, address, receipt box ===
        header_top = y
        if logo_url:
            try:
                import urllib.request
                with urllib.request.urlopen(logo_url, timeout=5) as resp:
                    img_data = resp.read()
                from reportlab.lib.utils import ImageReader
                img = ImageReader(io.BytesIO(img_data))
                iw, ih = img.getSize()
                max_h = 18 * mm
                max_w = 60 * mm
                scale = min(max_h / ih, max_w / iw)
                logo_h = ih * scale
                logo_w = iw * scale
                # Small inset from top/left inside header band
                logo_x = margin_x + 2 * mm
                logo_y = y - 2 * mm
                c.drawImage(
                    img,
                    logo_x,
                    logo_y - logo_h,
                    width=logo_w,
                    height=logo_h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                y_top = y
                y = y_top - logo_h - 6 * mm
            except Exception as e:
                logger.debug("Logo load failed, using school name: %s", e)
                c.setFont("Helvetica-Bold", 16)
                c.drawString(margin_x, y, school_name[:60])
                y -= line_h
        else:
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin_x + 2 * mm, y - 2 * mm, school_name[:60])
            y -= line_h + 2 * mm

        # Header right: Receipt # and Date (boxed)
        paid_at = billing.paid_at or datetime.utcnow()
        date_str = paid_at.strftime("%d/%m/%Y") if hasattr(paid_at, "strftime") else str(paid_at)
        receipt_no = str(getattr(billing, "id", ""))[-3:] or "-"
        box_w = 55 * mm
        box_h = 14 * mm
        box_x = w - margin_x - box_w
        box_y = (h - margin_y) - (logo_h if logo_url else 0) - 2 * mm
        c.setFont("Helvetica", 9)
        # Rectangle for Receipt # row, aligned with top header border
        c.setLineWidth(0.5)
        receipt_box_height = box_h / 2
        receipt_top = header_top
        receipt_bottom = receipt_top - receipt_box_height
        c.rect(box_x, receipt_bottom, box_w, receipt_box_height, stroke=1, fill=0)
        # Vertically center text in that rectangle
        baseline_receipt = (receipt_top + receipt_bottom) / 2 - 1.2 * mm
        c.drawString(box_x + 2 * mm, baseline_receipt, "Receipt #")
        c.drawRightString(box_x + box_w - 2 * mm, baseline_receipt, receipt_no)
        # Date row just below, with same style rectangle
        date_top = receipt_bottom
        date_bottom = date_top - receipt_box_height
        c.rect(box_x, date_bottom, box_w, receipt_box_height, stroke=1, fill=0)
        baseline_date = (date_top + date_bottom) / 2 - 1.2 * mm
        c.drawString(box_x + 2 * mm, baseline_date, "Date")
        c.drawRightString(box_x + box_w - 2 * mm, baseline_date, date_str)

        # Vertical divider between label and value for both rows
        col_x = box_x + box_w * 0.5
        c.line(col_x, header_top, col_x, header_top - 2 * receipt_box_height)

        # Address (under logo/name)
        header_bottom = y  # after address (or logo if no address)
        if school_address:
            c.setFont("Helvetica", 9)
            addr_line = school_address.replace("\n", " ").strip()[:110]
            if addr_line:
                c.drawString(margin_x + 2 * mm, y - 1 * mm, addr_line)
                y -= small_h
            y -= 3 * mm

        # Outer border around logo + address + receipt/date block
        header_bottom = min(header_bottom, y)
        c.rect(margin_x, header_bottom, w - 2 * margin_x, header_top - header_bottom, stroke=1, fill=0)

        # === Student details rows (bordered, aligned) ===
        if context:
            c.setFont("Helvetica", 10)

            # Row 1: Name of the Student (full-width box)
            row1_height = 8 * mm
            row1_top = y
            row1_bottom = row1_top - row1_height
            # Vertically center baseline in the row for ~10pt text
            baseline1 = (row1_top + row1_bottom) / 2 - 1.8 * mm
            if context.get("student_name"):
                c.setFont("Helvetica-Bold", 10)
                c.drawString(margin_x + 2 * mm, baseline1, "Name of the Student : ")
                c.setFont("Helvetica", 10)
                c.drawString(margin_x + 40 * mm, baseline1, str(context["student_name"])[:60])
            # Border for row 1
            c.setLineWidth(0.5)
            c.rect(margin_x, row1_bottom, w - 2 * margin_x, row1_height, stroke=1, fill=0)

            # Row 2: Admission Number | Class (two columns with borders)
            row2_height = 8 * mm
            row2_top = row1_bottom
            row2_bottom = row2_top - row2_height
            baseline2 = (row2_top + row2_bottom) / 2 - 1.8 * mm

            adm = str(context.get("admission_number", "")) if context.get("admission_number") else ""
            cls = str(context.get("class_name", "")) if context.get("class_name") else ""

            # Column boundary (middle of the row)
            col_class_x = margin_x + (w - 2 * margin_x) / 2

            # Admission Number (left cell)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margin_x + 2 * mm, baseline2, "Admission Number:")
            c.setFont("Helvetica", 10)
            c.drawString(margin_x + 2 * mm + c.stringWidth("Admission Number: ", "Helvetica-Bold", 10), baseline2, adm[:20])

            # Class (right cell)
            if cls:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(col_class_x + 2 * mm, baseline2, "Class:")
                c.setFont("Helvetica", 10)
                c.drawString(col_class_x + 2 * mm + c.stringWidth("Class: ", "Helvetica-Bold", 10), baseline2, cls[:20])

            # Outer box and column separator for row 2
            c.rect(margin_x, row2_bottom, w - 2 * margin_x, row2_height, stroke=1, fill=0)
            c.line(col_class_x, row2_bottom, col_class_x, row2_top)

            y = row2_bottom - 8 * mm

        # === Title ===
        c.setFont("Helvetica-Bold", 16)
        title = "RECEIPT OF PAYMENT"
        title_w = c.stringWidth(title, "Helvetica-Bold", 16)
        c.drawString((w - title_w) / 2, y, title)
        # Slight spacing below title (tighter than before)
        y -= line_h * 0.8

        # Horizontal line above table


        # === Components table: header + rows + total (with full borders) ===
        from reportlab.platypus import Table, TableStyle

        receipt_total = float(billing.amount_paid or 0)
        components = (context or {}).get("components")
        data = []
        if isinstance(components, list) and len(components) > 0:
            total_amt = sum(float(amt or 0) for _, amt in components)
            receipt_total = total_amt
            data.append(["Fee Structure", "Amount"])
            for name, amt in components:
                data.append([name or "", f"Rs.{float(amt or 0):,.2f}"])
        else:
            data.append(["Fee Structure", "Amount"])
            data.append([billing.fee_structure.name, f"Rs.{billing.amount_paid:,.2f}"])

        # Total row
        data.append(["Total", f"Rs.{receipt_total:,.2f}"])

        table_width = w - 2 * margin_x
        col_widths = [table_width * 0.7, table_width * 0.3]
        table = Table(data, colWidths=col_widths)
        style = TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                ("BOX", (0, 0), (-1, -1), 0.75, border_color),
                ("BACKGROUND", (0, 0), (-1, 0), _rl_colors.HexColor("#e0e0e0")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
        table.setStyle(style)
        tw, th = table.wrapOn(c, table_width, h)
        table.drawOn(c, margin_x, y - th)
        y -= th + 4 * mm

        # === Amount in words ===
        c.setFont("Helvetica", 9)
        words = _number_to_words_indian(receipt_total)
        max_w = w - 2 * margin_x
        for i in range(0, len(words), 50):
            chunk = words[i : i + 50]
            c.drawString(margin_x, y, chunk)
            y -= small_h
        y -= 4 * mm

        # === Notes / Authorised Signatory row ===
        c.setLineWidth(0.5)
        box_top = y
        box_bottom = box_top - 25 * mm
        mid_x = margin_x + (w - 2 * margin_x) / 2
        # outer box
        c.rect(margin_x, box_bottom, w - 2 * margin_x, box_top - box_bottom, stroke=1, fill=0)
        # vertical separator
        c.line(mid_x, box_bottom, mid_x, box_top)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_x + 2 * mm, box_top - 4 * mm, "Notes:")
        c.drawString(mid_x + 2 * mm, box_top - 4 * mm, "Authorised Signatory:")
        y = box_bottom - 8 * mm

        # === Footer: date & mode (small), then address/footer ===
        c.setFont("Helvetica", 8)
        c.drawString(margin_x, y, f"Date: {date_str}")
        payment_mode = getattr(billing, "payment_mode", "cash") or "cash"
        c.drawString(margin_x + 50 * mm, y, f"Mode: {payment_mode.capitalize()}")
        if payment_mode == "online" and getattr(billing, "transaction_number", None):
            c.drawString(margin_x + 100 * mm, y, f"Txn: {billing.transaction_number[:40]}")
        # Bottom section: trust logo (left) and address (right)
        y_logo = margin_y + 6 * mm
        if trust_logo_url:
            try:
                import urllib.request
                from reportlab.lib.utils import ImageReader

                with urllib.request.urlopen(trust_logo_url, timeout=5) as resp:
                    t_img_data = resp.read()
                    t_img = ImageReader(io.BytesIO(t_img_data))
                tw, th = t_img.getSize()
                max_h = 10 * mm
                max_w = 55 * mm
                t_scale = min(max_h / th, max_w / tw)
                logo_h2 = th * t_scale
                logo_w2 = tw * t_scale
                c.drawImage(
                    t_img,
                    margin_x,
                    y_logo - logo_h2 + 2 * mm,
                    width=logo_w2,
                    height=logo_h2,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception as e:
                logger.debug("Trust logo load failed: %s", e)

        # Trust / school address in two right-aligned lines (slightly lower than logo)
        c.setFont("Helvetica", 8)
        footer_source = trust_address or school_address or school_name
        footer_source = footer_source.strip()
        line1 = ""
        line2 = ""
        if "|" in footer_source:
            # Explicit manual split: "Line1|Line2"
            parts = [p.strip() for p in footer_source.split("|", 1)]
            line1 = parts[0]
            line2 = parts[1] if len(parts) > 1 else ""
        else:
            # Try to split on comma roughly mid-way for two lines
            n = len(footer_source)
            split_idx = footer_source.rfind(",", 0, n // 2)
            if split_idx == -1:
                split_idx = footer_source.find(",", n // 2)
            if split_idx != -1:
                line1 = footer_source[:split_idx].strip(" ,")
                line2 = footer_source[split_idx + 1 :].strip(" ,")
            else:
                line1 = footer_source
        y_addr = margin_y + 2 * mm
        if line2:
            c.drawRightString(w - margin_x, y_addr + small_h, line1[:100])
            c.drawRightString(w - margin_x, y_addr, line2[:100])
        else:
            c.drawRightString(w - margin_x, y_addr, line1[:100])
        c.save()
        return buf.getvalue()
    except Exception as e:
        logger.warning("ReportLab PDF failed: %s", e)
        return None


async def generate_receipt_pdf(billing: Billing, context: ReceiptContext = None) -> str | None:
    """Generate PDF, upload to S3, return URL. Uses same A5 layout when context provided."""
    url = await _generate_weasyprint(billing, context)
    if url:
        return url
    url = await _generate_reportlab(billing, context)
    return url


async def _generate_weasyprint(billing: Billing, context: ReceiptContext = None) -> str | None:
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return None
    try:
        html = _receipt_html(billing, context)
        pdf_bytes = HTML(string=html).write_pdf()
        key = f"receipts/{billing.student_id}/{billing.id}/{uuid.uuid4().hex}.pdf"
        return await _upload_or_none(key, pdf_bytes)
    except Exception as e:
        logger.warning("WeasyPrint PDF failed: %s", e)
        return None


async def _upload_or_none(key: str, pdf_bytes: bytes) -> str | None:
    try:
        return await upload_receipt_to_s3(key, pdf_bytes)
    except Exception as e:
        logger.warning("S3 upload failed: %s", e)
        return None


async def _generate_reportlab(billing: Billing, context: ReceiptContext = None) -> str | None:
    pdf_bytes = _reportlab_pdf_bytes(billing, context)
    if not pdf_bytes:
        return None
    key = f"receipts/{billing.student_id}/{billing.id}/{uuid.uuid4().hex}.pdf"
    return await _upload_or_none(key, pdf_bytes)


def _receipt_html(b: Billing, context: ReceiptContext = None) -> str:
    """Fallback HTML for WeasyPrint (simple layout with optional components table)."""
    school_name = (settings.school_name or settings.app_name).strip()
    school_address = (settings.school_address or "").strip()
    payment_mode = getattr(b, "payment_mode", "cash") or "cash"
    txn = getattr(b, "transaction_number", None) or ""
    paid_at = b.paid_at or datetime.utcnow()
    date_str = paid_at.strftime("%Y-%m-%d") if hasattr(paid_at, "strftime") else str(paid_at)
    ctx = context or {}
    student_line = f"<p>Student: {ctx.get('student_name', b.student_id)}</p>"
    class_line = f"<p>Class: {ctx.get('class_name', '')}</p>" if ctx.get("class_name") else ""
    branch_line = f"<p>Branch: {ctx.get('branch_name', '')}</p>" if ctx.get("branch_name") else ""
    comps = ctx.get("components") if isinstance(ctx.get("components"), list) else None
    if comps:
        rows = "".join(f"<tr><td>{n}</td><td class=\"right\">Rs.{a:,.2f}</td></tr>" for n, a in comps)
        total_amt = sum(a for _, a in comps)
        words = _number_to_words_indian(total_amt)
        table = f"""
        <table style="width:100%; border-collapse: collapse; margin: 8px 0;">
        <thead><tr><th style="text-align:left; border:0.5px solid #707070; background:#e0e0e0;">Component</th><th style="text-align:right; border:0.5px solid #707070; background:#e0e0e0;">Amount</th></tr></thead>
        <tbody>{rows}</tbody>
        <tfoot><tr class="bold"><td style="border:0.5px solid #707070; padding-top:4px;">Total</td><td class="right" style="border:0.5px solid #707070; padding-top:4px;">Rs.{total_amt:,.2f}</td></tr></tfoot>
        </table>"""
    else:
        table = f"<p>{b.fee_structure.name} <span class=\"right\">Rs.{b.amount_paid:,.2f}</span></p><p class=\"bold\">Total <span class=\"right\">Rs.{b.amount_paid:,.2f}</span></p>"
        words = _number_to_words_indian(b.amount_paid)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>Receipt</title>
    <style>
      body {{ font-family: sans-serif; padding: 20px; max-width: 420px; margin: 0 auto; }}
      .bold {{ font-weight: bold; }}
      .right {{ text-align: right; }}
    </style>
    </head>
    <body>
        <h2 style="margin-bottom: 4px;">{school_name}</h2>
        <p style="font-size: 0.9em; color: #444;">{school_address or ''}</p>
        {student_line}{class_line}{branch_line}
        <p class="bold" style="font-size: 1.2em; margin-top: 12px;">RECEIPT</p>
        {table}
        <p style="font-size: 0.9em;">{words}</p>
        <p style="font-size: 0.85em;">Date: {date_str} &middot; Mode: {payment_mode.capitalize()}</p>
        {f'<p style="font-size: 0.85em;">Txn: {txn}</p>' if payment_mode == 'online' and txn else ''}
        <p style="margin-top: 24px;">Authorized Signatory</p>
    </body>
    </html>
    """
