"""
LicenseCertificate üçün PDF generasiyası.

Hazırda RƏSMİ VİZUAL ŞABLON yoxdur (istifadəçi sonra nümunə şəkil təqdim edəcək) - bu modul
sadə, oxunaqlı bir ilkin format istehsal edir: başlıq, əsas məlumatlar cədvəli, sonra lisenziya
anketinin bütün sahələri (label: value) cədvəl şəklində. Əsl şablon gələndə YALNIZ bu fayl
(builder funksiyası) dəyişdirilməlidir - çağıran tərəf (views.py) toxunulmadan qalır.

QEYD (Unicode şrift): ReportLab-ın daxili "Helvetica" şrifti Azərbaycan hərflərini (ə, ğ, ı,
ş, ö, ü, ç, İ) əhatə etmir - bunları qara qutu kimi göstərir. Ona görə DejaVu Sans (sərbəst
lisenziyalı, Latin Extended dəstəkli) şriftini repo daxilində (licenses/fonts/) daşıyırıq və
server hansı şriftlərin quraşdırıldığından asılı olmadan işləməsi üçün ondan istifadə edirik.
"""
import io
import os

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from licenses.field_schema import get_schema

NAVY = colors.HexColor("#020624")
GOLD = colors.HexColor("#C9A24B")
MUTED = colors.HexColor("#64708A")
BORDER = colors.HexColor("#E5E7EF")

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_REGULAR = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
_fonts_registered = False


def _ensure_fonts_registered():
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, os.path.join(FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
    _fonts_registered = True


def _display_value(field, raw_value):
    if raw_value in (None, ""):
        return "-"
    if field.get("type") == "select":
        options = dict(field.get("options") or [])
        return options.get(raw_value, raw_value)
    if field.get("type") == "date":
        return str(raw_value)
    return str(raw_value)


def build_certificate_pdf(certificate) -> bytes:
    """LicenseCertificate obyektindən PDF bayt axını qaytarır (fayla yazmır)."""
    _ensure_fonts_registered()
    document = certificate.permit_document
    schema = get_schema(document.doc_type)["form_fields"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{certificate.number}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CertTitle", parent=styles["Title"], fontName=FONT_BOLD,
        textColor=NAVY, fontSize=18, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle", parent=styles["Normal"], fontName=FONT_REGULAR,
        textColor=MUTED, fontSize=10, spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "SectionTitle", parent=styles["Heading2"], fontName=FONT_BOLD,
        textColor=NAVY, fontSize=12, spaceBefore=14, spaceAfter=8,
    )

    story = [
        Paragraph("Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi", subtitle_style),
        Paragraph(f"{document.get_doc_type_display()} lisenziyası", title_style),
        Paragraph(
            f"Sənəd nömrəsi: {certificate.number} &nbsp;·&nbsp; Müraciət: {document.number} "
            f"&nbsp;·&nbsp; Yaradılıb: {timezone.localtime(certificate.created_at).strftime('%d.%m.%Y')}",
            subtitle_style,
        ),
    ]

    main_rows = [
        ["Müəssisə", document.applicant_name or "-"],
        ["VÖEN", document.voen or "-"],
        ["Verilmə tarixi", document.issue_date.strftime("%d.%m.%Y") if document.issue_date else "-"],
        ["Bitmə tarixi", document.expiry_date.strftime("%d.%m.%Y") if document.expiry_date else "-"],
    ]
    story.append(Paragraph("Əsas məlumatlar", section_style))
    story.append(_info_table(main_rows))

    story.append(Paragraph("Lisenziya anketi", section_style))
    if schema:
        field_rows = [
            [f["label"], _display_value(f, certificate.form_data.get(f["key"]))]
            for f in schema
        ]
        story.append(_info_table(field_rows))
    else:
        story.append(Paragraph(
            "Bu sənəd növü üçün anket sahələri təyin olunmayıb.",
            ParagraphStyle("Empty", parent=styles["Normal"], fontName=FONT_REGULAR),
        ))

    story.append(Spacer(1, 24))
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontName=FONT_REGULAR, textColor=MUTED, fontSize=8.5,
    )
    status_text = "Tamamlandı" if certificate.status == "tamamlandi" else "Qaralama"
    story.append(Paragraph(
        f"Status: {status_text} &nbsp;·&nbsp; Bu, sistemdə avtomatik generasiya olunmuş sənəddir.",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()


def _info_table(rows):
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        "CellLabel", parent=styles["Normal"], fontName=FONT_BOLD, fontSize=9.5, textColor=MUTED, leading=13,
    )
    value_style = ParagraphStyle(
        "CellValue", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=9.5, textColor=colors.black, leading=13,
    )
    wrapped_rows = [
        [Paragraph(str(label), label_style), Paragraph(str(value), value_style)]
        for label, value in rows
    ]
    table = Table(wrapped_rows, colWidths=[55 * mm, 105 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER),
    ]))
    return table