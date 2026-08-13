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
# Hər iki tip üçün eynidir.
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


def get_schema(doc_type: str) -> dict:
    file_fields = _IXRAC_FILE_FIELDS if doc_type == "ixrac" else _IDXAL_FILE_FIELDS
    return {
        "doc_type": doc_type,
        "file_fields": file_fields,
        "form_fields": _FORM_FIELDS,
    }