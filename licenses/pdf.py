"""
Təsdiqlənmiş (status='aktiv') lisenziya/icazə sənədləri üçün rəsmi PDF sertifikat generasiyası.

İstifadə: `generate_permit_pdf(document)` bytes qaytarır, bunu çağıran (bax models.py ->
PermitDocument.save()) PermitDocument.certificate_pdf sahəsinə yazır - beləliklə PDF DB-yə
(media storage + FK) bağlanır və istifadəçi frontend-də (lisenziya-icazeleri/sened/[id]) ona
baxa/yükləyə bilir.

Dizayn tətbiqin naviqasiya rənglərinə (GOV.navy/gold, bax frontend components/theme/govColors.js)
uyğunlaşdırılıb ki, PDF sistemin "rəsmi bildiriş kartı" görünüşü ilə həmahəng olsun.
"""
import io
import os

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Frame

from licenses.field_schema import get_schema

# QEYD: reportlab-ın daxili "Helvetica" (base14) fontu Azərbaycan hərflərini (ə, ı, ş, ğ, ç, ö,
# ü, İ) DƏSTƏKLƏMİR - WinAnsiEncoding-də bu simvollar yoxdur, nəticədə PDF-də qara/boş
# kvadratlar çıxır. Bunun əvəzinə Unicode-a tam dəstək verən DejaVu Sans-ı (licenses/fonts/,
# repo-ya bundle edilib ki, server-in öz şrift dəstindən asılı olmasın) qeydiyyatdan keçiririk.
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

if FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, os.path.join(FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))

NAVY = colors.HexColor("#020624")
GOLD = colors.HexColor("#C9A24B")
TEXT_MUTED = colors.HexColor("#64708A")
TEXT_PRIMARY = colors.HexColor("#141B33")
CARD_BORDER = colors.HexColor("#E5E7EF")
PAGE_BG = colors.HexColor("#F3F4F8")

STATUS_LABELS = {
    "gozleyir": "Gözlənilir",
    "aktiv": "Aktiv",
    "bitmis": "Bitmiş",
    "legv": "Ləğv edilib",
    "dayandirilib": "Dayandırılıb",
}
STATUS_COLORS = {
    "aktiv": colors.HexColor("#1E7D32"),
    "bitmis": colors.HexColor("#B45309"),
    "legv": colors.HexColor("#B91C1C"),
    "dayandirilib": colors.HexColor("#B91C1C"),
    "gozleyir": TEXT_MUTED,
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def _wrapped_para(text, style, max_width):
    p = Paragraph(text or "-", style)
    _, h = p.wrap(max_width, 1000)
    return p, h


def generate_permit_pdf(document) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    label_style = ParagraphStyle(
        "label", fontName=FONT_BOLD, fontSize=8, leading=10,
        textColor=TEXT_MUTED, alignment=TA_LEFT,
    )
    value_style = ParagraphStyle(
        "value", fontName=FONT_REGULAR, fontSize=10.5, leading=14,
        textColor=TEXT_PRIMARY, alignment=TA_LEFT,
    )

    # ---------- Header (navy şərid) ----------
    header_h = 34 * mm
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - header_h, PAGE_W, header_h, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - header_h - 1.2 * mm, PAGE_W, 1.2 * mm, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 20)
    c.drawString(MARGIN, PAGE_H - 16 * mm, "PİLAU")
    c.setFont(FONT_REGULAR, 9)
    c.setFillColor(colors.HexColor("#9AA5C7"))
    c.drawString(MARGIN, PAGE_H - 21.5 * mm, "İdarəetmə platforması")

    c.setFont(FONT_BOLD, 9.5)
    c.setFillColor(GOLD)
    ministry_text = "AZƏRBAYCAN RESPUBLİKASININ MÜDAFİƏ SƏNAYESİ NAZİRLİYİ"
    tw = stringWidth(ministry_text, FONT_BOLD, 9.5)
    c.drawString(PAGE_W - MARGIN - tw, PAGE_H - 16 * mm, ministry_text)
    c.setFont(FONT_REGULAR, 8.5)
    c.setFillColor(colors.HexColor("#9AA5C7"))
    sub = document.get_doc_type_display() + " sənədi"
    tw2 = stringWidth(sub, FONT_REGULAR, 8.5)
    c.drawString(PAGE_W - MARGIN - tw2, PAGE_H - 21.5 * mm, sub)

    y = PAGE_H - header_h - 14 * mm

    # ---------- Başlıq + sənəd nömrəsi ----------
    c.setFillColor(TEXT_PRIMARY)
    c.setFont(FONT_BOLD, 16)
    title = document.title or document.get_doc_type_display()
    c.drawString(MARGIN, y, title)
    y -= 7 * mm

    c.setFont(FONT_REGULAR, 10.5)
    c.setFillColor(TEXT_MUTED)
    c.drawString(MARGIN, y, f"Sənəd nömrəsi: {document.number}")

    status_key = document.status
    status_label = STATUS_LABELS.get(status_key, status_key)
    status_color = STATUS_COLORS.get(status_key, TEXT_MUTED)
    badge_w = stringWidth(status_label, FONT_BOLD, 9) + 10 * mm
    c.setFillColor(status_color)
    c.roundRect(PAGE_W - MARGIN - badge_w, y - 3.2 * mm, badge_w, 7 * mm, 3.2 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 9)
    c.drawCentredString(PAGE_W - MARGIN - badge_w / 2, y - 0.8 * mm, status_label)
    y -= 12 * mm

    c.setStrokeColor(CARD_BORDER)
    c.setLineWidth(0.6)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 10 * mm

    def section_title(text, yy):
        c.setFont(FONT_BOLD, 9.5)
        c.setFillColor(GOLD)
        c.drawString(MARGIN, yy, text.upper())
        return yy - 7 * mm

    def two_col_field(label, value, yy, col=0):
        col_w = (PAGE_W - 2 * MARGIN - 8 * mm) / 2
        x = MARGIN + col * (col_w + 8 * mm)
        p_label, h1 = _wrapped_para(label, label_style, col_w)
        p_label.drawOn(c, x, yy - h1)
        p_value, h2 = _wrapped_para(str(value) if value not in (None, "") else "-", value_style, col_w)
        p_value.drawOn(c, x, yy - h1 - h2 - 1 * mm)
        return h1 + h2 + 1 * mm

    # ---------- Müraciətçi məlumatları ----------
    y = section_title("Müraciətçi məlumatları", y)
    row_h = max(
        two_col_field("Müraciətçi müəssisə", document.applicant_name, y, 0),
        two_col_field("VÖEN", document.voen, y, 1),
    )
    y -= row_h + 5 * mm
    row_h = max(
        two_col_field("Departament/Şöbə", document.department, y, 0),
        two_col_field("Vəzifə", document.position, y, 1),
    )
    y -= row_h + 5 * mm
    row_h = max(
        two_col_field("Telefon", document.phone, y, 0),
        two_col_field("Elektron poçt", document.email, y, 1),
    )
    y -= row_h + 9 * mm

    c.setStrokeColor(CARD_BORDER)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 10 * mm

    # ---------- Sənəd təfərrüatları (form_data - sxemdəki label-larla) ----------
    y = section_title("Sənəd təfərrüatları", y)
    try:
        schema = get_schema(document.doc_type)
        field_defs = {f["key"]: f for f in schema.get("form_fields", [])}
    except Exception:
        field_defs = {}

    entries = []
    for key, value in (document.form_data or {}).items():
        if key == "status":
            continue
        label = field_defs.get(key, {}).get("label", key.replace("_", " ").capitalize())
        entries.append((label, value))

    col = 0
    for label, value in entries:
        if y < 45 * mm:
            c.showPage()
            y = PAGE_H - MARGIN
            col = 0
        h = two_col_field(label, value, y, col)
        if col == 1:
            y -= h + 5 * mm
        col = 1 - col
    if col == 1:
        y -= 5 * mm  # tək qalan sol sütun sətri üçün boşluq

    y -= 5 * mm
    c.setStrokeColor(CARD_BORDER)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 10 * mm

    # ---------- Tarixlər ----------
    if y < 45 * mm:
        c.showPage()
        y = PAGE_H - MARGIN
    y = section_title("Etibarlılıq müddəti", y)
    issue_str = document.issue_date.strftime("%d.%m.%Y") if document.issue_date else "Status təsdiqləndikdən sonra görünəcək"
    expiry_str = document.expiry_date.strftime("%d.%m.%Y") if document.expiry_date else "Müddətsiz"
    row_h = max(
        two_col_field("Verilmə tarixi", issue_str, y, 0),
        two_col_field("Bitmə tarixi", expiry_str, y, 1),
    )
    y -= row_h + 9 * mm

    # ---------- Footer ----------
    footer_y = 14 * mm
    c.setStrokeColor(CARD_BORDER)
    c.line(MARGIN, footer_y + 6 * mm, PAGE_W - MARGIN, footer_y + 6 * mm)
    c.setFont(FONT_REGULAR, 7.5)
    c.setFillColor(TEXT_MUTED)
    generated = timezone.now().strftime("%d.%m.%Y %H:%M")
    c.drawString(MARGIN, footer_y, f"Bu sənəd PİLAU sistemi tərəfindən avtomatik yaradılıb - {generated}")
    right_text = "Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi"
    tw3 = stringWidth(right_text, FONT_REGULAR, 7.5)
    c.drawString(PAGE_W - MARGIN - tw3, footer_y, right_text)

    c.showPage()
    c.save()
    return buf.getvalue()