"""
İdxal / İxrac icazə sənədi üçün sahə sxemi.

Bu fayl "tək mənbə" rolunu oynayır: hər iki rejim üçün (Fayl yüklə / Elektron
müraciət forması) tələb olunan sahələr burada təyin olunur və API vasitəsilə
frontend-ə ötürülür. Sahələri dəyişmək/əlavə etmək üçün yalnız bu faylı
redaktə etmək kifayətdir - frontend formu avtomatik uyğunlaşır.
"""

DOC_TYPES = (
    ("ixrac", "İxrac"),
    ("idxal", "İdxal"),
    ("istehsal", "İstehsal"),
    ("xususi_satis", "Xüsusi Satış"),
)

# --- 'İstehsal lisenziyası' üçün "Lisenziya anketi"-ndəki 'Lisenziya tipi' sahəsinin seçimləri ---
LICENSE_TYPE_CHOICES = (
    ("yeni", "Yeni lisenziya"),
    ("yeniden_resmilesdirme", "Yenidən rəsmiləşdirmə"),
)

STATUS_CHOICES = (
    ("gozleyir", "Gözlənilir"),
    ("aktiv", "Aktiv"),
    ("bitmis", "Bitmiş"),
    ("legv", "Ləğv edilib"),
    ("dayandirilib", "Dayandırılıb"),
)

SUBMISSION_MODES = (
    ("file", "Fayl yüklə"),
    ("form", "Elektron müraciət forması"),
)

# --- "Fayl yüklə" rejimi üçün tələb olunan sənədlər ---
_IXRAC_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_sureti", "label": "Müqavilənin surəti (malların çeşid siyahısı ilə birlikdə)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_tercumesi", "label": "Rus dilindən başqa xarici dildə olan müqavilənin imza və möhürlə təsdiqlənmiş tərcüməsi", "required": True, "max_size_mb": 10},
    {"key": "istifadeci_sertifikati", "label": "Son istifadəçi sertifikatının əsli", "required": True, "max_size_mb": 10},
    {"key": "istifadeci_sertifikati_tercumesi", "label": "Rus dilindən başqa xarici dildə olan son istifadəçi sertifikatının imza və möhürlə təsdiqlənmiş tərcüməsi", "required": True, "max_size_mb": 10},
    {"key": "iqtisadi_elaqeler_materiali", "label": "Mallar və xarici iqtisadi əlaqələr haqqında imza və möhürlə təsdiqlənmiş material", "required": True, "max_size_mb": 10},
    {"key": "menshe_sertifikati", "label": "İxrac olunan malın mənşə sertifikatının surəti", "required": True, "max_size_mb": 10},
    {"key": "vergi_qeydiyyati", "label": "Vergi orqanında qeydiyyat haqqında şəhadətnamənin surəti", "required": True, "max_size_mb": 10},
    {"key": "dovlet_rusumu", "label": "Dövlət rüsumunun ödənildiyini təsdiqləyən sənəd", "required": True, "max_size_mb": 10},
]

_IDXAL_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_sureti", "label": "Müqavilənin surəti (malların çeşid siyahısı ilə birlikdə)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_tercumesi", "label": "Rus dilindən başqa xarici dildə olan müqavilənin imza və möhürlə təsdiqlənmiş tərcüməsi", "required": True, "max_size_mb": 10},
    {"key": "gondericinin_sertifikati", "label": "Göndərici tərəfin son istifadəçi öhdəliyi sənədi", "required": True, "max_size_mb": 10},
    {"key": "gondericinin_sertifikati_tercumesi", "label": "Rus dilindən başqa xarici dildə olan həmin sənədin imza və möhürlə təsdiqlənmiş tərcüməsi", "required": True, "max_size_mb": 10},
    {"key": "iqtisadi_elaqeler_materiali", "label": "Mallar və xarici iqtisadi əlaqələr haqqında imza və möhürlə təsdiqlənmiş material", "required": True, "max_size_mb": 10},
    {"key": "menshe_sertifikati", "label": "İdxal olunan malın mənşə sertifikatının surəti", "required": True, "max_size_mb": 10},
    {"key": "vergi_qeydiyyati", "label": "Vergi orqanında qeydiyyat haqqında şəhadətnamənin surəti", "required": True, "max_size_mb": 10},
    {"key": "dovlet_rusumu", "label": "Dövlət rüsumunun ödənildiyini təsdiqləyən sənəd", "required": True, "max_size_mb": 10},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) rejimi üçün sahələr ---
# İdxal/İxrac üçün eynidir.
_FORM_FIELDS = [
    {"key": "icaze_nomresi", "label": "İcazə nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "mehsul", "label": "Malın adı / qismən fəaliyyət növü", "type": "text", "required": True},
    {"key": "terefler", "label": "Tərəflər (Alıcı / Satıcı müqavilə tərəfləri)", "type": "text", "required": True},
    {"key": "fealiyyet_sahesi", "label": "Fəaliyyət sahəsi (Hərbi texnika / silah sənayesi və s.)", "type": "text", "required": True},
    {"key": "tesdiq_olunan_say", "label": "Təsdiq olunmuş say (avtomatik)", "type": "number", "required": False, "auto": True},
    {"key": "faktiki_miqdar", "label": "Faktiki idxal/ixrac (avtomatik)", "type": "number", "required": False, "auto": True},
    {"key": "qaliq", "label": "Qalıq", "type": "number", "required": False, "auto": True},
    {"key": "istifade_meqsedi", "label": "İstifadə məqsədi", "type": "text", "required": True},
    {"key": "verilme_tarixi", "label": "Verilmə tarixi", "type": "date", "required": True},
    {"key": "muddet", "label": "Müddət", "type": "text", "required": True},
    {"key": "status", "label": "Status", "type": "select", "required": True, "options": STATUS_CHOICES},
]

# --- "Fayl yüklə" rejimi - İstehsal lisenziyası (Image 2) ---
_ISTEHSAL_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "tesis_senedi", "label": "Təsis sənədi (nizamnamə)", "required": True, "max_size_mb": 10},
    {"key": "voen_sureti", "label": "VÖEN şəhadətnaməsinin surəti", "required": True, "max_size_mb": 10},
    {"key": "fealiyyet_senedi", "label": "Müəssisənin fəaliyyəti barədə sənəd", "required": True, "max_size_mb": 10},
    {"key": "isci_terkibi_senedi", "label": "Müəssisənin işçi tərkibi barədə sənəd (Ərizəyə əlavə)", "required": True, "max_size_mb": 10},
    {"key": "vesiqe_sureti", "label": "Səlahiyyətli şəxsin şəxsiyyət vəsiqəsinin surəti", "required": True, "max_size_mb": 10},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) - İstehsal lisenziyası (Image 3) ---
_ISTEHSAL_FORM_FIELDS = [
    {"key": "lisenziya_nomresi", "label": "Lisenziya nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "mehsulun_novu", "label": "Məhsulun növü", "type": "text", "required": True},
    {"key": "lisenziya_tipi", "label": "Lisenziya tipi", "type": "select", "required": True, "options": LICENSE_TYPE_CHOICES},
    {"key": "fealiyyet_sahesi", "label": "Fəaliyyət sahəsi", "type": "text", "required": True},
    {"key": "subyekt_adi", "label": "Subyekt adı", "type": "text", "required": False, "auto": True},
    {"key": "istinad_maddesi", "label": "İstinad maddəsi (İcazələr haqqında Qanun - bənd)", "type": "text", "required": True},
    {"key": "verilme_tarixi", "label": "Verilmə tarixi", "type": "date", "required": True},
    {"key": "muddet", "label": "Müddət", "type": "text", "required": True},
    {"key": "status", "label": "Status", "type": "select", "required": True, "options": STATUS_CHOICES},
]

# --- "Fayl yüklə" rejimi - Xüsusi satış icazə sənədi (Image 2) ---
_XUSUSI_SATIS_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (möhürlü)", "required": True, "max_size_mb": 10},
    {"key": "mallarin_siyahisi", "label": "Malların siyahısı / nomenklaturası", "required": True, "max_size_mb": 10},
    {"key": "istehsal_prosesi_melumati", "label": "Malların istehsal prosesi barədə məlumat", "required": True, "max_size_mb": 10},
    {"key": "istehsal_idxal_hisseleri_melumati", "label": "Malların istehsal və idxal olunan hissələri barədə məlumat", "required": True, "max_size_mb": 10},
    {"key": "texniki_gostericiler", "label": "Malların texniki göstəriciləri", "required": True, "max_size_mb": 10},
    {"key": "texnoloji_konstruksiya_senedleri", "label": "Malların texnoloji konstruksiya sənədləri", "required": True, "max_size_mb": 10},
    {"key": "beynelxalq_standart_senedi", "label": "Malların beynəlxalq standartlara uyğunluğu barədə sənəd", "required": True, "max_size_mb": 10},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) - Xüsusi satış icazə sənədi (Image 3) ---
_XUSUSI_SATIS_FORM_FIELDS = [
    {"key": "icaze_nomresi", "label": "İcazə nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "istinad_maddesi", "label": "İstinad maddəsi", "type": "text", "required": True},
    {"key": "satis_novu", "label": "Satış növü (Daxili satış / İdxal / İxrac)", "type": "text", "required": True},
    {"key": "malin_tesviri", "label": "Malın təsviri", "type": "text", "required": True},
    {"key": "muqavile_nomresi", "label": "Müqavilə nömrəsi", "type": "text", "required": True},
    {"key": "muddet", "label": "Müddət", "type": "text", "required": True},
    {"key": "selahiyyetli_organ", "label": "Səlahiyyətli orqan", "type": "text", "required": False, "auto": False},
]

_SCHEMA_BY_DOC_TYPE = {
    "ixrac": {"file_fields": _IXRAC_FILE_FIELDS, "form_fields": _FORM_FIELDS},
    "idxal": {"file_fields": _IDXAL_FILE_FIELDS, "form_fields": _FORM_FIELDS},
    "istehsal": {"file_fields": _ISTEHSAL_FILE_FIELDS, "form_fields": _ISTEHSAL_FORM_FIELDS},
    "xususi_satis": {"file_fields": _XUSUSI_SATIS_FILE_FIELDS, "form_fields": _XUSUSI_SATIS_FORM_FIELDS},
}


def get_schema(doc_type: str) -> dict:
    schema = _SCHEMA_BY_DOC_TYPE.get(doc_type, _SCHEMA_BY_DOC_TYPE["idxal"])
    return {
        "doc_type": doc_type,
        "file_fields": schema["file_fields"],
        "form_fields": schema["form_fields"],
    }