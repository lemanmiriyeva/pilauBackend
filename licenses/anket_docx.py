"""
Lisenziya/İdxal-İxrac və s. sənəd yaratma formalarındakı "2. Anket" bölməsi üçün
Word (.docx) şablon generasiyası və doldurulmuş şablonun geri oxunması.

Axın:
  1. İstifadəçi "Şablonu yüklə" düyməsini basır -> build_anket_template() bir .docx
     yaradır: cədvəldə "Sahə adı | Dəyər" sütunları var. VÖEN və Müəssisənin adı
     artıq API-dən bilindiyi üçün əvvəlcədən doldurulur, "auto"/"readonly" sahələr
     də (məs. "Müddət") sabit dəyərləri ilə doldurulur - istifadəçi yalnız qalan
     boş sətirləri doldurur.
  2. İstifadəçi Word-də doldurub geri yükləyir -> parse_anket_template() cədvəli
     oxuyub sətir başlıqlarını (Sahə adı) schema-dakı form_fields-in "label"/"key"
     dəyərləri ilə uyğunlaşdırır və {field_key: deyer} formasında qaytarır.

QEYD: Uyğunlaşdırma mətn əsaslıdır (normallaşdırılmış müqayisə) - Word sənədində
sətir sırası və ya əlavə boşluqlar problem yaratmır, AMMA sətrin birinci sütunu
(Sahə adı) mümkün qədər orijinal etiketə (və ya field key-inə) yaxın olmalıdır.

"checkbox_list" tipli sahələr (məs. "İstinad maddəsi" bəndləri, 6.1-6.5 / 7.1-7.5)
üçün hər bir yarım-bənd öz sətrində ƏSL, Word-də KLİKLƏNƏ BİLƏN checkbox
content control kimi göstərilir (Word 2010+ "Check Box Content Control" - ☐/☒
xanaya sadəcə yazı yazmır, istifadəçi üzərinə klikləyəndə avtomatik dəyişir,
sənədin qorunmasına (Protect Document) ehtiyac yoxdur). Bənd qrupları (6-cı və
7-ci maddələr) sətrin yuxarısında qalın başlıq kimi görünür, checkbox-lar isə
yalnız 6.1-6.5 / 7.1-7.5 yarım-bəndləri üçündür.

"select" (açılan siyahı) tipli sahələr (məs. "Lisenziya tipi", "Fəaliyyət
sahəsi") də eyni səbəbdən ƏSL Word "Drop-Down List Content Control" kimi
göstərilir - istifadəçi xananın üzərinə klikləyib seçim edir, sərbəst mətn
yazmır. Seçim edildikdə Word xananın görünən mətnini seçilmiş variantın
adı ilə avtomatik əvəz edir, ona görə geri oxunanda adi mətn kimi tanınır.

"computed" (sistem tərəfindən avtomatik hesablanan, məs. "Lisenziya
kateqoriyası") sahələr şablonda GÖSTƏRİLMİR - onların dəyəri yalnız sənəd
göndəriləndən sonra bəndlərə əsasən müəyyən olunur.
"""

import io
import random
import re

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

_CHECKBOX_UNCHECKED = "\u2610"  # ☐
_CHECKBOX_CHECKED = "\u2612"  # ☒
_CHECKED_MARKS = (_CHECKBOX_CHECKED, "☑", "✓", "✔", "x", "X", "V", "v", "+")

_DROPDOWN_PLACEHOLDER = "-- Seçin --"


def _normalize_label(text):
    """Azərbaycan hərflərini latın uyğunları ilə əvəz edib, boşluq/durğu işarələrini
    tək alt xəttə çevirərək müqayisə üçün "normal" mətn açarı yaradır."""
    text = (text or "").strip().lower()
    translit = str.maketrans({
        "ə": "e", "ö": "o", "ü": "u", "ç": "c", "ş": "s", "ğ": "g", "ı": "i",
    })
    text = text.translate(translit)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _cell_text(cell):
    """Xananın BÜTÜN mətnini qaytarır - adi paraqraflardan olduğu kimi, həm də
    content control-ların (checkbox/dropdown) içindəki mətndən. python-docx-un
    öz `cell.text` xassəsi yalnız <w:p> altındakı birbaşa <w:r>-ları oxuyur və
    <w:sdt> (content control) içindəki mətni GÖRMÜR - ona görə bunu əl ilə,
    xananın bütün <w:t> alt elementlərini gəzərək toplayırıq."""
    parts = []
    for node in cell._tc.iter(qn('w:t')):
        if node.text:
            parts.append(node.text)
    return "".join(parts)


def _new_sdt_id():
    return str(random.randint(10 ** 8, 10 ** 9 - 1))


def _insert_checkbox_control(cell, checked=False):
    """Verilmiş cədvəl xanasına əsl, Word-də (2010+) birbaşa klikləyərək
    işarələnə bilən checkbox content control əlavə edir. Sənədin qorunmasına
    (Protect Document -> Filling in forms) ehtiyac yoxdur."""

    cell.text = ""
    paragraph = cell.paragraphs[0]
    p_el = paragraph._p

    sdt = OxmlElement('w:sdt')
    sdt_pr = OxmlElement('w:sdtPr')

    id_el = OxmlElement('w:id')
    id_el.set(qn('w:val'), _new_sdt_id())
    sdt_pr.append(id_el)

    checkbox_el = OxmlElement('w14:checkbox')

    checked_el = OxmlElement('w14:checked')
    checked_el.set(qn('w14:val'), '1' if checked else '0')
    checkbox_el.append(checked_el)

    checked_state = OxmlElement('w14:checkedState')
    checked_state.set(qn('w14:val'), '2612')
    checked_state.set(qn('w14:font'), 'MS Gothic')
    checkbox_el.append(checked_state)

    unchecked_state = OxmlElement('w14:uncheckedState')
    unchecked_state.set(qn('w14:val'), '2610')
    unchecked_state.set(qn('w14:font'), 'MS Gothic')
    checkbox_el.append(unchecked_state)

    sdt_pr.append(checkbox_el)
    sdt.append(sdt_pr)

    sdt_content = OxmlElement('w:sdtContent')
    r = OxmlElement('w:r')
    r_pr = OxmlElement('w:rPr')
    r_fonts = OxmlElement('w:rFonts')
    r_fonts.set(qn('w:ascii'), 'MS Gothic')
    r_fonts.set(qn('w:eastAsia'), 'MS Gothic')
    r_fonts.set(qn('w:hAnsi'), 'MS Gothic')
    r_fonts.set(qn('w:hint'), 'eastAsia')
    r_pr.append(r_fonts)
    r.append(r_pr)
    t = OxmlElement('w:t')
    t.text = _CHECKBOX_CHECKED if checked else _CHECKBOX_UNCHECKED
    r.append(t)
    sdt_content.append(r)
    sdt.append(sdt_content)

    p_el.append(sdt)


def _insert_dropdown_control(cell, options, selected_display=None):
    """Verilmiş cədvəl xanasına əsl Word "Drop-Down List" content control
    əlavə edir. `options`: (value, display_label) cütlüklərinin siyahısı."""

    cell.text = ""
    paragraph = cell.paragraphs[0]
    p_el = paragraph._p

    sdt = OxmlElement('w:sdt')
    sdt_pr = OxmlElement('w:sdtPr')

    id_el = OxmlElement('w:id')
    id_el.set(qn('w:val'), _new_sdt_id())
    sdt_pr.append(id_el)

    dropdown_el = OxmlElement('w:dropDownList')

    placeholder_item = OxmlElement('w:listItem')
    placeholder_item.set(qn('w:displayText'), _DROPDOWN_PLACEHOLDER)
    placeholder_item.set(qn('w:value'), _DROPDOWN_PLACEHOLDER)
    dropdown_el.append(placeholder_item)

    for value, display in options:
        item = OxmlElement('w:listItem')
        item.set(qn('w:displayText'), display)
        item.set(qn('w:value'), value)
        dropdown_el.append(item)

    sdt_pr.append(dropdown_el)
    sdt.append(sdt_pr)

    sdt_content = OxmlElement('w:sdtContent')
    r = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.text = selected_display or _DROPDOWN_PLACEHOLDER
    r.append(t)
    sdt_content.append(r)
    sdt.append(sdt_content)

    p_el.append(sdt)


def _merge_as_header(cells, text):
    """İki xananı bir sətirdə birləşdirib qalın başlıq mətni yazır (bənd
    qrupunun - "6." / "7." maddəsinin - başlığı üçün)."""
    merged = cells[0].merge(cells[1])
    merged.text = ""
    run = merged.paragraphs[0].add_run(text)
    run.bold = True


def build_anket_template(schema, applicant_name="", voen="", title="Lisenziya anketi"):
    """schema: get_schema(doc_type) nəticəsi (dict, 'form_fields' açarı ilə).
    Qaytarır: BytesIO (.docx məzmunu)."""

    document = Document()

    document.add_heading(title, level=1)

    intro = document.add_paragraph(
        "Bu sənəd sistem tərəfindən avtomatik yaradılıb. Aşağıdakı cədvəldə "
        "\"Dəyər\" sütununda boş qalan sətirləri doldurun (checkbox/açılan "
        "siyahı sahələrinin üzərinə klikləyib seçim edin) və sənədi olduğu "
        "formatda (Word/.docx) geri yükləyin - sistem dəyərləri avtomatik "
        "anketə köçürəcək."
    )
    intro.italic = True

    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"

    header_cells = table.rows[0].cells
    header_cells[0].text = "Sahə adı"
    header_cells[1].text = "Dəyər"

    # VÖEN və müəssisə adı - "Müraciətçi məlumatları" bölümündən, API-dən artıq bəllidir.
    voen_row = table.add_row().cells
    voen_row[0].text = "VÖEN"
    voen_row[1].text = voen or ""

    if applicant_name:
        name_row = table.add_row().cells
        name_row[0].text = "Müəssisənin adı"
        name_row[1].text = applicant_name

    for field in schema.get("form_fields", []):
        # Sistem tərəfindən avtomatik hesablanan sahələr (məs. "Lisenziya
        # kateqoriyası") şablonda görünmür - istifadəçi bunları doldurmur.
        if field.get("computed"):
            continue

        field_type = field.get("type")

        if field_type == "checkbox_list":
            last_group = None
            for opt in field.get("options", []):
                group = opt.get("group") if isinstance(opt, dict) else None
                group_label = opt.get("group_label") if isinstance(opt, dict) else None

                if group is not None and group != last_group:
                    header_cells = table.add_row().cells
                    _merge_as_header(header_cells, f"{group}. {group_label}")
                    last_group = group

                opt_key = opt["key"] if isinstance(opt, dict) else opt[0]
                opt_number = opt.get("number", "") if isinstance(opt, dict) else ""
                opt_label = opt["label"] if isinstance(opt, dict) else opt[1]

                row = table.add_row().cells
                row[0].text = f"{opt_number} {opt_label}".strip()
                _insert_checkbox_control(row[1], checked=False)
            continue

        if field_type == "select" and field.get("options"):
            row = table.add_row().cells
            row[0].text = field.get("label", field.get("key", ""))
            _insert_dropdown_control(row[1], list(field["options"]))
            continue

        row = table.add_row().cells
        label = field.get("label", field.get("key", ""))
        row[0].text = label
        # "auto"/"readonly" sahələrin sabit dəyəri varsa, əvvəlcədən doldururuq -
        # istifadəçi bunları yenidən yazmasın deyə.
        fixed_value = field.get("value")
        row[1].text = str(fixed_value) if fixed_value not in (None, "") else ""

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def parse_anket_template(file_obj, schema):
    """file_obj: yüklənmiş .docx faylı (Django UploadedFile və ya BytesIO).
    schema: get_schema(doc_type) nəticəsi.

    Qaytarır: {"values": {field_key: deyer, ...}, "voen": "..." | None,
    "matched_count": N}."""

    document = Document(file_obj)

    if not document.tables:
        return {"values": {}, "voen": None, "matched_count": 0}

    table = document.tables[0]

    # Sahə etiketlərini (label/key) normallaşdırıb axtarış üçün lüğət qururuq.
    field_lookup = {}
    field_by_key = {}
    # checkbox_list sahələr üçün ayrıca lüğət: "nömrə + bənd etiketi" (normallaşmış) -> (field_key, option_key)
    checkbox_lookup = {}
    checkbox_field_keys = set()
    for field in schema.get("form_fields", []):
        if field.get("computed"):
            continue  # sistem hesablayır, şablonda sətri yoxdur
        field_by_key[field["key"]] = field
        if field.get("type") == "checkbox_list":
            checkbox_field_keys.add(field["key"])
            for opt in field.get("options", []):
                opt_key = opt["key"] if isinstance(opt, dict) else opt[0]
                opt_number = opt.get("number", "") if isinstance(opt, dict) else ""
                opt_label = opt["label"] if isinstance(opt, dict) else opt[1]
                norm = _normalize_label(f"{opt_number} {opt_label}")
                if norm:
                    checkbox_lookup[norm] = (field["key"], opt_key)
                # nömrəsiz variant da (ehtiyat üçün) - istifadəçi sətri əl ilə
                # dəyişdirib nömrəni silmiş ola bilər.
                norm_no_number = _normalize_label(opt_label)
                if norm_no_number:
                    checkbox_lookup.setdefault(norm_no_number, (field["key"], opt_key))
            continue
        for candidate in (field.get("label"), field.get("key")):
            norm = _normalize_label(candidate)
            if norm:
                field_lookup[norm] = field["key"]

    values = {}
    checked_bends = {key: [] for key in checkbox_field_keys}
    voen_value = None

    for row in table.rows[1:]:  # ilk sətir header - keçirik
        cells = row.cells

        if len(cells) < 2:
            continue

        raw_label = _cell_text(cells[0]).strip()
        raw_value = _cell_text(cells[1]).strip()

        if not raw_label or not raw_value:
            continue

        # "6. Döyüş təyinatlı hərbi texnikanın və hərbi silahın:" kimi qrup
        # başlığı sətirləri (2 xana birləşdirilib, hər ikisi eyni mətni
        # göstərir) - bunlar məlumat daşımır, keçirik.
        if raw_label == raw_value:
            continue

        # Template generasiyasında "select" sahələrin etiketinə köhnə
        # versiyalarda " (seçim: ...)" əlavə olunurdu - uyğunlaşdırmadan
        # əvvəl bunu atırıq (geriyə uyğunluq üçün saxlanılıb).
        raw_label = re.sub(r"\s*\(seçim:.*?\)\s*$", "", raw_label, flags=re.IGNORECASE)

        norm_label = _normalize_label(raw_label)

        if norm_label == "voen":
            voen_value = raw_value
            continue

        if norm_label in ("muessisenin_adi", "musessisenin_adi", "muraciet_edenin_adi"):
            continue  # applicant_name ayrıca idarə olunur, anket sahəsi deyil

        # Açılan siyahıda (dropdown) heç nə seçilməyibsə, defolt placeholder
        # görünür - bunu boş sahə kimi qəbul edirik (sistemin özü "tələb
        # olunur" xətası kimi tutsun).
        if raw_value == _DROPDOWN_PLACEHOLDER:
            continue

        # checkbox_list sətri olub-olmadığını yoxlayırıq (məs. "6.1. layihələndirilməsi").
        checkbox_match = checkbox_lookup.get(norm_label)
        if not checkbox_match:
            for norm_candidate, pair in checkbox_lookup.items():
                if norm_candidate and (norm_candidate in norm_label or norm_label in norm_candidate):
                    checkbox_match = pair
                    break
        if checkbox_match:
            field_key, option_key = checkbox_match
            is_checked = any(mark in raw_value for mark in _CHECKED_MARKS)
            if is_checked:
                checked_bends[field_key].append(option_key)
            continue

        matched_key = field_lookup.get(norm_label)

        if not matched_key:
            # Tam uyğunluq tapılmadısa, qismən uyğunluğa (substring) cəhd edirik.
            for norm_candidate, key in field_lookup.items():
                if norm_candidate and (norm_candidate in norm_label or norm_label in norm_candidate):
                    matched_key = key
                    break

        if matched_key:
            field = field_by_key.get(matched_key)
            options = field.get("options") if field else None
            if options:
                # "select" sahə - Word-də istifadəçinin dropdown-dan seçdiyi
                # görünən mətni (display label) option key-inə çeviririk
                # (məs. "Silah" -> "silah"), tapılmasa xam mətni saxlayırıq.
                norm_value = _normalize_label(raw_value)
                option_key = next(
                    (opt_key for opt_key, opt_label in options if _normalize_label(opt_label) == norm_value
                     or opt_key == raw_value),
                    None,
                )
                values[matched_key] = option_key or raw_value
            else:
                values[matched_key] = raw_value

    for field_key, checked_keys in checked_bends.items():
        values[field_key] = checked_keys

    return {"values": values, "voen": voen_value, "matched_count": len(values)}