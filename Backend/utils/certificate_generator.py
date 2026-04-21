from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import qr
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import hashlib
import json
import os
import socket
from datetime import datetime


# =====================================================
# 🌐 AUTO-DETECT LOCAL NETWORK IP
# =====================================================

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =====================================================
# 🔐 HASH GENERATION (Tamper Protection)
# =====================================================

def generate_hash(data: dict):
    important_fields = {
        "claim_id":   data.get("claim_id"),
        "name":       data.get("patta_holder_name"),
        "scheme":     data.get("eligible_scheme"),
        "validation": data.get("validation_status"),
        "area":       data.get("total_area_claimed"),
    }
    serialized = json.dumps(important_fields, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


# =====================================================
# 🏛 WATERMARK FUNCTION
# =====================================================

def add_watermark(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 60)
    canvas_obj.setFillColorRGB(0.9, 0.9, 0.9)
    canvas_obj.translate(300, 400)
    canvas_obj.rotate(45)
    canvas_obj.drawCentredString(0, 0, "OFFICIAL")
    canvas_obj.restoreState()


# =====================================================
# 📄 MAIN CERTIFICATE GENERATOR
# =====================================================

def generate_claim_certificate(data: dict, file_path: str, base_url: str = None):

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # ✅ Auto-detect local network IP (e.g. 192.168.29.179)
    # Works on any machine — no hardcoding needed
    local_ip = get_local_ip()
    claim_id = data.get("claim_id", "")

    # ✅ Both URLs built from the same dynamic IP
    effective_base_url = f"http://{local_ip}:8080"
    verification_url   = f"http://{local_ip}:8080/verify/{claim_id}"

    print(f"🌐 Base URL:            {effective_base_url}")
    print(f"🔳 QR verification URL: {verification_url}")

    # Generate certificate hash
    certificate_hash = generate_hash(data)
    data["certificate_hash"] = certificate_hash

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()
    title_style    = styles["Heading1"]
    subtitle_style = styles["Heading2"]
    normal_style   = styles["Normal"]

    # -------------------------------------------------
    # 🏛 HEADER
    # -------------------------------------------------
    elements.append(Paragraph("<b>Government of India</b>", title_style))
    elements.append(Paragraph("Ministry of Tribal Affairs", normal_style))
    elements.append(Paragraph("Forest Rights Act Digital Portal", normal_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph("<b>FRA Digital Claim Certificate</b>", subtitle_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elements.append(Spacer(1, 0.3 * inch))

    # -------------------------------------------------
    # 📄 APPLICANT DETAILS TABLE
    # -------------------------------------------------
    table_data = [
        ["Applicant Name",     data.get("patta_holder_name", "")],
        ["Claim ID",           data.get("claim_id", "")],
        ["State",              data.get("state", "")],
        ["District",           data.get("district", "")],
        ["Village",            data.get("village_name", "")],
        ["Age",                str(data.get("age", ""))],
        ["Gender",             data.get("gender", "")],
        ["Land Use",           data.get("land_use", "")],
        ["Total Area",         data.get("total_area_claimed", "")],
        ["Eligible Scheme",    data.get("eligible_scheme", "")],
        ["Validation Status",  data.get("validation_status", "")],
        ["Certificate Status", data.get("certificate_status", "ACTIVE")],
    ]

    table = Table(table_data, colWidths=[2.7 * inch, 3.3 * inch])
    table.setStyle(TableStyle([
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.whitesmoke),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.5 * inch))

    # -------------------------------------------------
    # 🔐 CERTIFICATE METADATA
    # -------------------------------------------------
    issued_time = datetime.utcnow().strftime("%d-%m-%Y %H:%M UTC")

    elements.append(Paragraph("<b>Digital Certificate Information</b>", subtitle_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Issued On: {issued_time}", normal_style))
    elements.append(Paragraph(f"Certificate Hash: {certificate_hash}", normal_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        "This certificate is digitally generated and protected using cryptographic hashing "
        "to prevent tampering. Verification can be performed using the QR code below.",
        normal_style,
    ))
    elements.append(Spacer(1, 0.5 * inch))

    # -------------------------------------------------
    # 🔳 QR CODE — points to network IP, not localhost
    # -------------------------------------------------
    qr_code = qr.QrCodeWidget(verification_url)
    bounds = qr_code.getBounds()
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]

    qr_drawing = Drawing(
        120, 120,
        transform=[120.0 / w, 0, 0, 120.0 / h, 0, 0],
    )
    qr_drawing.add(qr_code)

    elements.append(qr_drawing)
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("<b>Scan QR to Verify Authenticity</b>", normal_style))
    elements.append(Paragraph(
        f"Or visit: <font color='blue'>{verification_url}</font>",
        normal_style
    ))

    # -------------------------------------------------
    # 🏛 FOOTER
    # -------------------------------------------------
    elements.append(Spacer(1, 0.7 * inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(
        "Issued under FRA Digital Governance & Verification System",
        normal_style,
    ))

    # BUILD WITH WATERMARK
    doc.build(elements, onFirstPage=add_watermark, onLaterPages=add_watermark)

    return certificate_hash