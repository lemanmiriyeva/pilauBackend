"""
LicenseCertificate üçün PDF generasiyası.

RƏSMİ ŞABLON: istifadəçinin təqdim etdiyi "ÜMUMİ LİSENZİYA" dövlət blankına (gerb, başlıq,
sahələr - Qeydiyyat nömrəsi, verən orqan, fəaliyyət növü, kimə verilib, imzalayan vəzifəli şəxs,
imza/M.Y. yeri) uyğun tərtib olunub. Dövlət gerbi (licenses/assets/az_emblem.png) həmin blankın
skanından təmizlənərək çıxarılıb - rəsmi dövlət rəmzi olduğu üçün Nazirliyin öz sənədlərində
sərbəst istifadə oluna bilər.

QEYD (Unicode şrift): ReportLab-ın daxili "Helvetica" şrifti Azərbaycan hərflərini (ə, ğ, ı,
ş, ö, ü, ç, İ) əhatə etmir - bunları qara qutu kimi göstərir. Ona görə DejaVu Sans (sərbəst
lisenziyalı, Latin Extended dəstəkli) şriftini repo daxilində (licenses/fonts/) daşıyırıq.
"""
import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from licenses.field_schema import get_schema

INK = colors.HexColor("#1A1A1A")
MUTED = colors.HexColor("#5A5A5A")
GOLD = colors.HexColor("#B8902E")
BORDER = colors.HexColor("#2B2B2B")
GREEN_OK = colors.HexColor("#1E7A3C")

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
EMBLEM_PATH = os.path.join(ASSETS_DIR, "az_emblem.png")

FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
_fonts_registered = False

PAGE_W, PAGE_H = A4
MARGIN = 24 * mm
FRAME_MARGIN = 10 * mm

MONTHS_AZ = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avqust", "sentyabr", "oktyabr", "noyabr", "dekabr",
]


def _ensure_fonts_registered():
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, os.path.join(FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
    _fonts_registered = True


def _display_value(field, raw_value):
    if raw_value in (None, ""):
        return ""
    if field.get("type") == "select":
        options = dict(field.get("options") or [])
        return options.get(raw_value, raw_value)
    return str(raw_value)


def _issuing_authority():
    """Lisenziyanı verən orqanın adı/ünvanı - MSN-in Organization qeydindən (code='msn') gəlir,
    tapılmasa sabit mətnə düşür. Bax Organization.CODE_MSN (organizations/models.py)."""
    try:
        from organizations.models import Organization
        org = Organization.objects.filter(code=Organization.CODE_MSN).first()
        if org:
            return org.full_name, (org.address or "Bakı şəhəri, Azərbaycan Respublikası")
    except Exception:
        pass
    return "Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi", "Bakı şəhəri, Azərbaycan Respublikası"


def _activity_description(document, schema):
    """Fəaliyyət növü sətri - anketdəki məhsul/fəaliyyət sahəsi kimi sahələrdən (varsa) və ya
    sənəd kateqoriyasından qurulur. Blankdakı çoxsətirli 'lisenziya verilən fəaliyyət növü'
    sahəsini doldurur."""
    parts = []
    priority_keys = ["mehsul", "mehsulun_novu", "fealiyyet_sahesi"]
    form_data = document.form_data or {}
    field_defs = {f["key"]: f for f in schema}
    for key in priority_keys:
        if form_data.get(key):
            parts.append(_display_value(field_defs.get(key, {}), form_data[key]))
    if not parts:
        parts.append(document.get_doc_type_display())
    return " / ".join(dict.fromkeys(parts))


def _applicant_block(document):
    """'Lisenziya verilib ...' sahəsi - müəssisənin adı, hüquqi ünvanı, VÖEN-i."""
    org = document.organization
    address = (org.address if org and org.address else "") or ""
    pieces = [document.applicant_name or "-"]
    if address:
        pieces.append(address)
    if document.voen:
        pieces.append(f"VÖEN {document.voen}")
    return ", ".join(pieces)


def _signer_info(document, certificate):
    """İmzalayan vəzifəli şəxs / vəzifəsi.

    Əsas mənbə: 'Təsdiq axını' ekranında bu sənəd növü (doc_type) üçün təyin edilmiş
    İmzalayan şəxs (workflow.DocumentWorkflowConfig.signer_user) - bax workflow/views.py
    WorkflowConfigView, frontend lisenziya-icazeleri/tesdiq-axini/page.js.

    Təyin olunmayıbsa (signer_user boşdursa), köhnə davranışa - faktiki 2-ci mərhələ
    təsdiqçisinə, o da yoxdursa sənədi 'Tamamlandı' edən şəxsə - geri düşür ki, köhnə
    sənədlər üçün sahə boş qalmasın."""
    from workflow.models import DocumentWorkflowConfig

    user = None
    config = DocumentWorkflowConfig.objects.filter(doc_type=document.doc_type).first()
    if config and config.signer_user_id:
        user = config.signer_user

    if not user:
        user = document.stage2_approved_by or certificate.completed_by

    if not user:
        return "", ""

    name = user.get_full_name() or user.username

    position_obj = getattr(user, "position", None)
    position = position_obj.name if position_obj else ""

    return name, position

def _label_style():
    return ParagraphStyle("field_label", fontName=FONT_REGULAR, fontSize=8, leading=10, textColor=MUTED)


def _value_style(align=TA_LEFT):
    return ParagraphStyle("field_value", fontName=FONT_REGULAR, fontSize=10.5, leading=15, textColor=INK, alignment=align)


class _Layout:
    """Blank şablonundakı 'etiket sətri -> dəyər (xətt üstündə) -> kiçik izah' naxışını
    ardıcıl aşağı doğru çəkən köməkçi. Hər addım `self.y`-i özü aşağı sürüşdürür."""

    def __init__(self, c):
        self.c = c
        self.y = PAGE_H - MARGIN

    def gap(self, amount):
        self.y -= amount

    def inline_label(self, text):
        self.c.setFont(FONT_REGULAR, 10.5)
        self.c.setFillColor(INK)
        self.c.drawString(MARGIN, self.y - 10, text)
        self.y -= 15

    def blank_value(self, value_text, caption=None, min_lines=1):
        width = PAGE_W - 2 * MARGIN
        vstyle = _value_style()
        para = Paragraph(value_text or "&nbsp;", vstyle)
        _, h = para.wrap(width, 1000)
        n_lines = max(min_lines, round(h / vstyle.leading))
        line_h = vstyle.leading

        para.drawOn(self.c, MARGIN, self.y - h)

        self.c.setStrokeColor(BORDER)
        self.c.setLineWidth(0.6)
        for i in range(n_lines):
            line_y = self.y - (i + 1) * line_h + 2
            self.c.line(MARGIN, line_y, PAGE_W - MARGIN, line_y)
        self.y -= n_lines * line_h

        if caption:
            cap = Paragraph(f"({caption})", _label_style())
            _, ch = cap.wrap(width, 200)
            cap.drawOn(self.c, MARGIN, self.y - ch)
            self.y -= ch + 3 * mm
        else:
            self.y -= 3 * mm


def build_certificate_pdf(certificate) -> bytes:
    """LicenseCertificate obyektindən rəsmi 'ÜMUMİ LİSENZİYA' formatında PDF bayt axını qaytarır."""
    _ensure_fonts_registered()
    document = certificate.permit_document
    schema = get_schema(document.doc_type)["form_fields"]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(certificate.number)

    # --- Dekorativ xarici çərçivə ---
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.4)
    c.rect(FRAME_MARGIN, FRAME_MARGIN, PAGE_W - 2 * FRAME_MARGIN, PAGE_H - 2 * FRAME_MARGIN)
    c.setLineWidth(0.5)
    inner = FRAME_MARGIN + 2.2 * mm
    c.rect(inner, inner, PAGE_W - 2 * inner, PAGE_H - 2 * inner)

    L = _Layout(c)
    L.y = PAGE_H - MARGIN - 2 * mm

    # --- Dövlət gerbi ---
    emblem_w = 26 * mm
    if os.path.exists(EMBLEM_PATH):
        from PIL import Image as PILImage
        with PILImage.open(EMBLEM_PATH) as im:
            ratio = im.height / im.width
        emblem_h = emblem_w * ratio
        c.drawImage(
            EMBLEM_PATH, (PAGE_W - emblem_w) / 2, L.y - emblem_h,
            width=emblem_w, height=emblem_h, mask="auto",
        )
        L.y -= emblem_h + 4 * mm

    # --- Başlıq (hərf-arası boşluqlu, blankdakı effektə bənzər) ---
    c.setFont(FONT_BOLD, 20)
    c.setFillColor(INK)
    title = "ÜMUMİ LİSENZİYA"
    letter_gap = 1.6
    total_w = sum(stringWidth(ch, FONT_BOLD, 20) + letter_gap for ch in title) - letter_gap
    x = (PAGE_W - total_w) / 2
    for ch in title:
        c.drawString(x, L.y - 16, ch)
        x += stringWidth(ch, FONT_BOLD, 20) + letter_gap
    L.y -= 22

    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    line_w = 70 * mm
    c.line((PAGE_W - line_w) / 2, L.y, (PAGE_W + line_w) / 2, L.y)
    L.y -= 10 * mm

    # --- Qeydiyyat nömrəsi + tarix (eyni sətirdə) ---
    issue_date = document.issue_date
    if issue_date:
        date_str = f'"{issue_date.day:02d}" {MONTHS_AZ[issue_date.month - 1]} {issue_date.year}-ci il'
    else:
        date_str = "___________________"

    c.setFont(FONT_REGULAR, 10.5)
    c.setFillColor(INK)
    label1 = "Qeydiyyat nömrəsi "
    c.drawString(MARGIN, L.y - 12, label1)
    lx = MARGIN + stringWidth(label1, FONT_REGULAR, 10.5)
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(lx + 2, L.y - 12, certificate.number)
    numw = stringWidth(certificate.number, FONT_BOLD, 10.5)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.line(lx, L.y - 14, lx + numw + 35 * mm, L.y - 14)

    c.setFont(FONT_REGULAR, 10.5)
    date_x = PAGE_W - MARGIN - stringWidth(date_str, FONT_REGULAR, 10.5)
    c.drawString(date_x, L.y - 12, date_str)
    L.y -= 22

    # --- Verən orqan ---
    authority_name, authority_address = _issuing_authority()
    L.blank_value(authority_name, "lisenziya verən orqanın adı")
    L.blank_value(authority_address, "lisenziya verən orqanın ünvanı")

    # --- Fəaliyyət növü ---
    activity = _activity_description(document, schema)
    L.blank_value(activity, "lisenziya verilən fəaliyyət növü (bütün alt növlər)", min_lines=3)

    c.setFont(FONT_REGULAR, 10.5)
    c.setFillColor(INK)
    c.drawString(MARGIN, L.y - 10, "həyata keçirməyə icazə verir.")
    L.y -= 16 * mm

    # --- Kimə verilib ---
    L.inline_label("Lisenziya verilib")
    L.blank_value(_applicant_block(document), None, min_lines=2)
    caption2 = (
        "hüquqi şəxsin, xarici hüquqi şəxsin filialının və nümayəndəliyinin adı və hüquqi "
        "ünvanı, fərdi sahibkarın soyadı, adı, atasının adı və fəaliyyət ünvanı, VÖEN"
    )
    cap_para = Paragraph(f"({caption2})", _label_style())
    _, ch = cap_para.wrap(PAGE_W - 2 * MARGIN, 200)
    cap_para.drawOn(c, MARGIN, L.y - ch)
    L.y -= ch + 8 * mm

    # --- İmzalayan vəzifəli şəxs / Vəzifəsi ---
    signer_name, signer_position = _signer_info(document, certificate)
    L.inline_label("Lisenziyanı imzalayan vəzifəli şəxs")
    L.blank_value(signer_name, "adı və soyadı")

    L.inline_label("Vəzifəsi")
    L.blank_value(signer_position, None)

    L.y -= 8 * mm

    # --- İmza + M.Y. (möhür yeri) ---
    sig_line_w = 60 * mm
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.line(MARGIN, L.y, MARGIN + sig_line_w, L.y)
    c.setFont(FONT_REGULAR, 8)
    c.setFillColor(MUTED)
    c.drawCentredString(MARGIN + sig_line_w / 2, L.y - 10, "(imza)")

    seal_cx = PAGE_W - MARGIN - 24 * mm
    seal_cy = L.y - 12 * mm
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(INK)
    c.drawString(PAGE_W - MARGIN - 60 * mm, L.y + 2, "M.Y.")
    c.setStrokeColor(colors.HexColor("#C9A24B"))
    c.setLineWidth(0.8)
    c.circle(seal_cx, seal_cy, 16 * mm, stroke=1, fill=0)

    if certificate.is_signed:
        method_label = "SİM İmza" if certificate.signature_method == "sima" else "Asan İmza"
        c.setFont(FONT_REGULAR, 7.5)
        c.setFillColor(GREEN_OK)
        c.drawCentredString(seal_cx, seal_cy + 4, "Elektron")
        c.drawCentredString(seal_cx, seal_cy - 4, "imzalanıb")
        c.drawCentredString(seal_cx, seal_cy - 12, f"({method_label})")

    # --- Alt qeyd ---
    c.setFont(FONT_REGULAR, 7)
    c.setFillColor(MUTED)
    c.drawCentredString(
        PAGE_W / 2, FRAME_MARGIN + 5 * mm,
        f"Bu sənəd PİLAU sistemi tərəfindən avtomatik yaradılıb - {certificate.number} - Müraciət: {document.number}",
    )

    c.showPage()
    c.save()
    return buffer.getvalue()