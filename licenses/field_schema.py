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
    ("istehsal", "İstehsal (köhnə)"),
    ("xususi_lisenziya", "Xüsusi Lisenziya"),
    ("umumi_lisenziya", "Ümumi Lisenziya"),
    ("xususi_satis", "Xüsusi Satış"),
    ("gomrukden_azadolma", "Gömrükdən Azadolma"),
    ("edvden_azadolma", "ƏDV-dən Azadolma"),
)

# Bax seed_modules_shell.py -> meta ("1 illik ..." / "Müddətsiz"): idxal/ixrac və ƏDV güzəşt
# (gömrükdən azadolma / ƏDV-dən azadolma) 1 illikdir (təsdiqlənəndə bitmə tarixi avtomatik
# +1 il qoyulur); istehsal və xüsusi satış isə müddətsizdir (bitmə tarixi boş qalır).
# Bax: licenses/models.py -> PermitDocument.save()
EXPIRING_DOC_TYPES = {"idxal", "ixrac", "gomrukden_azadolma", "edvden_azadolma"}

# --- 'İstehsal lisenziyası' üçün "Lisenziya anketi"-ndəki 'Lisenziya tipi' sahəsinin seçimləri ---
LICENSE_TYPE_CHOICES = (
    ("yeni", "Yeni lisenziya"),
    ("yeniden_resmilesdirme", "Yenidən rəsmiləşdirmə"),
)
ACTIVITY_TYPE_CHOICES = (
    ("herbi_texnika", "Hərbi texnika"),
    ("doyus_teyinatli", "Döyüş təyinatlı"),
    ("silah", "Silah"),

)
SATIS_TYPE_CHOICES = (
    ("daxili_satis", "Daxili satış"),
    ("idxal", "İdxal"),
    ("ixrac", "İxrac"),

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

# --- "Lisenziya" (Xüsusi/Ümumi) - istinad maddəsindəki bəndlər (checkbox siyahısı) ---
# "İcazələr haqqında" Qanunun lisenziyaya aid maddəsinin bəndləri. İstifadəçi bunları
# formda/Word şablonunda checkbox kimi işarələyir. Hüquqi mətn dəyişərsə və ya bənd
# sayı artarsa, YALNIZ bu siyahını yeniləmək kifayətdir (key unikal olmalıdır) -
# kateqoriya hesablaması (bax compute_lisenziya_kateqoriya) avtomatik uyğunlaşır.
ISTINAD_MADDESI_BENDLERI = [
    {"key": "bend_6_1", "group": "6", "group_label": "Döyüş təyinatlı hərbi texnikanın və hərbi silahın:",
     "number": "6.1.", "label": "layihələndirilməsi"},
    {"key": "bend_6_2", "group": "6", "group_label": "Döyüş təyinatlı hərbi texnikanın və hərbi silahın:",
     "number": "6.2.", "label": "istehsalı və sınaqdan keçirilməsi"},
    {"key": "bend_6_3", "group": "6", "group_label": "Döyüş təyinatlı hərbi texnikanın və hərbi silahın:",
     "number": "6.3.", "label": "quraşdırılması, montajı, təmiri və texniki xidmət göstərilməsi"},
    {"key": "bend_6_4", "group": "6", "group_label": "Döyüş təyinatlı hərbi texnikanın və hərbi silahın:",
     "number": "6.4.", "label": "saxlanılması"},
    {"key": "bend_6_5", "group": "6", "group_label": "Döyüş təyinatlı hərbi texnikanın və hərbi silahın:",
     "number": "6.5.", "label": "utilizasiyası"},
    {"key": "bend_7_1", "group": "7", "group_label": "Döyüş sursatının:",
     "number": "7.1.", "label": "layihələndirilməsi"},
    {"key": "bend_7_2", "group": "7", "group_label": "Döyüş sursatının:",
     "number": "7.2.", "label": "istehsalı və sınaqdan keçirilməsi"},
    {"key": "bend_7_3", "group": "7", "group_label": "Döyüş sursatının:",
     "number": "7.3.", "label": "təmiri və texniki xidmət göstərilməsi"},
    {"key": "bend_7_4", "group": "7", "group_label": "Döyüş sursatının:",
     "number": "7.4.", "label": "saxlanılması"},
    {"key": "bend_7_5", "group": "7", "group_label": "Döyüş sursatının:",
     "number": "7.5.", "label": "utilizasiyası"},
]

LISENZIYA_KATEQORIYA_LABELS = {
    "umumi_lisenziya": "Ümumi Lisenziya",
    "xususi_lisenziya": "Xüsusi Lisenziya",
}


def compute_lisenziya_kateqoriya(selected_bend_keys) -> str:
    """İstinad maddəsində (6.1-6.5 və 7.1-7.5 yarım-bəndləri) işarələnmiş
    seçimlərə görə lisenziyanın kateqoriyasını ('umumi_lisenziya' /
    'xususi_lisenziya') təyin edir. İstifadəçi bunu seçmir - sistem avtomatik
    hesablayır (bax PermitDocument.save, licenses/models.py):

      - Bütün 10 yarım-bənd işarələnibsə (tətbiq sahəsi məhdudlaşdırılmayıb) -> Ümumi Lisenziya
      - Yarım-bəndlərdən heç olmasa biri işarələnməyibsə (məhdudlaşdırılıb)  -> Xüsusi Lisenziya
    """
    all_keys = {b["key"] for b in ISTINAD_MADDESI_BENDLERI}
    selected = {k for k in (selected_bend_keys or [])}
    if all_keys and all_keys.issubset(selected):
        return "umumi_lisenziya"
    return "xususi_lisenziya"

# --- "Fayl yüklə" rejimi üçün tələb olunan sənədlər ---
_IXRAC_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_sureti", "label": "Müqavilənin surəti (malların çeşid siyahısı ilə birlikdə)", "required": True,
     "max_size_mb": 10},
    {"key": "muqavile_tercumesi",
     "label": "Rus dilindən başqa xarici dildə olan müqavilənin imza və möhürlə təsdiqlənmiş tərcüməsi",
     "required": True, "max_size_mb": 10},
    {"key": "istifadeci_sertifikati", "label": "Son istifadəçi sertifikatının əsli", "required": True,
     "max_size_mb": 10},
    {"key": "istifadeci_sertifikati_tercumesi",
     "label": "Rus dilindən başqa xarici dildə olan son istifadəçi sertifikatının imza və möhürlə təsdiqlənmiş tərcüməsi",
     "required": True, "max_size_mb": 10},
    {"key": "iqtisadi_elaqeler_materiali",
     "label": "Mallar və xarici iqtisadi əlaqələr haqqında imza və möhürlə təsdiqlənmiş material", "required": True,
     "max_size_mb": 10},
    {"key": "menshe_sertifikati", "label": "İxrac olunan malın mənşə sertifikatının surəti", "required": True,
     "max_size_mb": 10},
    {"key": "vergi_qeydiyyati", "label": "Vergi orqanında qeydiyyat haqqında şəhadətnamənin surəti", "required": True,
     "max_size_mb": 10},
    {"key": "dovlet_rusumu", "label": "Dövlət rüsumunun ödənildiyini təsdiqləyən sənəd", "required": True,
     "max_size_mb": 10},
]

_IDXAL_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_sureti", "label": "Müqavilənin surəti (malların çeşid siyahısı ilə birlikdə)", "required": True,
     "max_size_mb": 10},
    {"key": "muqavile_tercumesi",
     "label": "Rus dilindən başqa xarici dildə olan müqavilənin imza və möhürlə təsdiqlənmiş tərcüməsi",
     "required": True, "max_size_mb": 10},
    {"key": "gondericinin_sertifikati", "label": "Göndərici tərəfin son istifadəçi öhdəliyi sənədi", "required": True,
     "max_size_mb": 10},
    {"key": "gondericinin_sertifikati_tercumesi",
     "label": "Rus dilindən başqa xarici dildə olan həmin sənədin imza və möhürlə təsdiqlənmiş tərcüməsi",
     "required": True, "max_size_mb": 10},
    {"key": "iqtisadi_elaqeler_materiali",
     "label": "Mallar və xarici iqtisadi əlaqələr haqqında imza və möhürlə təsdiqlənmiş material", "required": True,
     "max_size_mb": 10},
    {"key": "menshe_sertifikati", "label": "İdxal olunan malın mənşə sertifikatının surəti", "required": True,
     "max_size_mb": 10},
    {"key": "vergi_qeydiyyati", "label": "Vergi orqanında qeydiyyat haqqında şəhadətnamənin surəti", "required": True,
     "max_size_mb": 10},
    {"key": "dovlet_rusumu", "label": "Dövlət rüsumunun ödənildiyini təsdiqləyən sənəd", "required": True,
     "max_size_mb": 10},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) rejimi üçün sahələr ---
# İdxal/İxrac üçün eynidir.
_FORM_FIELDS = [
    {
        "key": "icaze_nomresi",
        "label": "İcazə nömrəsi",
        "type": "text",
        "required": True,
        "auto": True,
    },
    {
        "key": "mehsul",
        "label": "Malın adı / qismən fəaliyyət növü",
        "type": "text",
        "required": True,
    },
    {
        "key": "terefler",
        "label": "Tərəflər (Alıcı / Satıcı müqavilə tərəfləri)",
        "type": "text",
        "required": True,
    },
    {
        "key": "fealiyyet_sahesi",
        "label": "Fəaliyyət sahəsi (Hərbi texnika / silah sənayesi və s.)",
        "type": "text",
        "required": True,
    },
    {
        "key": "tesdiq_olunan_say",
        "label": "Təsdiq olunmuş say (avtomatik)",
        "type": "number",
        "required": False,
        "auto": True,
    },
    {
        "key": "faktiki_miqdar",
        "label": "Faktiki idxal/ixrac (avtomatik)",
        "type": "number",
        "required": False,
        "auto": True,
    },
    {
        "key": "qaliq",
        "label": "Qalıq",
        "type": "number",
        "required": False,
        "auto": True,
    },
    {
        "key": "istifade_meqsedi",
        "label": "İstifadə məqsədi",
        "type": "text",
        "required": True,
    },
    {
        "key": "verilme_tarixi",
        "label": "Verilmə tarixi",
        "type": "date",
        "required": True,
    },
    {
        "key": "muddet",
        "label": "Müddət",
        "type": "text",
        "readonly": True,
        "required": True,
        "value": "1 il",
    },
    {
        "key": "status",
        "label": "Status",
        "type": "select",
        "required": True,
        "options": STATUS_CHOICES,
    },
]

# --- "Fayl yüklə" rejimi - İstehsal lisenziyası (Image 2) ---
_ISTEHSAL_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "tesis_senedi", "label": "Təsis sənədi (nizamnamə)", "required": True, "max_size_mb": 10},
    {"key": "voen_sureti", "label": "VÖEN şəhadətnaməsinin surəti", "required": True, "max_size_mb": 10},
    {"key": "fealiyyet_senedi", "label": "Müəssisənin fəaliyyəti barədə sənəd", "required": True, "max_size_mb": 10},
    {"key": "isci_terkibi_senedi", "label": "Müəssisənin işçi tərkibi barədə sənəd (Ərizəyə əlavə)", "required": True,
     "max_size_mb": 10},
    {"key": "vesiqe_sureti", "label": "Səlahiyyətli şəxsin şəxsiyyət vəsiqəsinin surəti", "required": True,
     "max_size_mb": 10},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) - İstehsal lisenziyası (Image 3) ---
_ISTEHSAL_FORM_FIELDS = [
    {"key": "lisenziya_nomresi", "label": "Lisenziya nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "mehsulun_novu", "label": "Məhsulun növü", "type": "text", "required": True},
    {"key": "lisenziya_tipi", "label": "Lisenziya tipi", "type": "select", "required": True,
     "options": LICENSE_TYPE_CHOICES},
    {"key": "fealiyyet_sahesi", "label": "Fəaliyyət sahəsi", "type": "select", "required": True,
     "options": ACTIVITY_TYPE_CHOICES},
    {"key": "subyekt_adi", "label": "Subyekt adı", "type": "text", "required": False, "auto": True},
    {"key": "istinad_maddesi", "label": "İstinad maddəsi (İcazələr haqqında Qanun - bənd)", "type": "text",
     "readonly": True, "required": True, "value": '"İcazələr haqqında Qanun",VI-VII bəndlər'},
    {"key": "verilme_tarixi", "label": "Verilmə tarixi", "type": "date", "required": True},
    {"key": "muddet", "label": "Müddət", "type": "text", "readonly": True, "required": True, "value": 'Müddətsiz'},
    {"key": "status", "label": "Status", "type": "select", "required": True, "options": STATUS_CHOICES},
]

# --- "Lisenziya" (əvvəlki "İstehsal") - "Xüsusi Lisenziya" və "Ümumi Lisenziya" ---
#
# ARTIQ TƏK SXEM: Xüsusi və Ümumi Lisenziyanın sahələri eynidir - fərq YALNIZ
# istinad maddəsindəki hansı bəndlərin işarələndiyindən asılı olaraq sistemin
# avtomatik təyin etdiyi kateqoriyadır (bax compute_lisenziya_kateqoriya və
# licenses/models.py -> PermitDocument.save()). Ona görə "yeni lisenziya"
# müraciəti tək formadır, istifadəçi Xüsusi/Ümumi arasında seçim eləmir.
#
# Bu formada ARTIQ YOXDUR (istifadəçi doldurmur, sistem özü idarə edir):
#   - "Verilmə tarixi"  -> yalnız lisenziya İMZALANDIQDAN sonra düşür
#                          (bax LicenseCertificateView.sign -> PermitDocument.issue_date)
#   - "Müddət"          -> bu lisenziya növü həmişə müddətsizdir (bax pdf.py/certificate_pdf.py)
#   - "Status"          -> təsdiq axınının nəticəsidir (gözləyir/aktiv/rədd - bax
#                          PermitDocument.approve_stage / reject), anketdə sahə deyil
_LISENZIYA_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (imzalanmış)", "required": True, "max_size_mb": 10},
    {"key": "tesis_senedi", "label": "Təsis sənədi (nizamnamə)", "required": True, "max_size_mb": 10},
    {"key": "voen_sureti", "label": "VÖEN şəhadətnaməsinin surəti", "required": True, "max_size_mb": 10},
    {"key": "fealiyyet_senedi", "label": "Müəssisənin fəaliyyəti barədə sənəd", "required": True, "max_size_mb": 10},
    {"key": "isci_terkibi_senedi", "label": "Müəssisənin işçi tərkibi barədə sənəd (Ərizəyə əlavə)", "required": True,
     "max_size_mb": 10},
    {"key": "vesiqe_sureti", "label": "Səlahiyyətli şəxsin şəxsiyyət vəsiqəsinin surəti", "required": True,
     "max_size_mb": 10},
]

_LISENZIYA_FORM_FIELDS = [
    {"key": "lisenziya_nomresi", "label": "Lisenziya nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "mehsulun_novu", "label": "Məhsulun növü", "type": "text", "required": True},
    {"key": "lisenziya_tipi", "label": "Lisenziya tipi", "type": "select", "required": True,
     "options": LICENSE_TYPE_CHOICES},
    {"key": "fealiyyet_sahesi", "label": "Fəaliyyət sahəsi", "type": "select", "required": True,
     "options": ACTIVITY_TYPE_CHOICES},
    {"key": "subyekt_adi", "label": "Subyekt adı", "type": "text", "required": False, "auto": True},
    {
        "key": "istinad_maddesi_bendleri",
        "label": "İstinad maddəsi (\"İcazələr haqqında\" Qanun) - bəndlər",
        "type": "checkbox_list",
        "required": True,
        "options": ISTINAD_MADDESI_BENDLERI,
    },
    {
        "key": "kateqoriya",
        "label": "Lisenziya kateqoriyası",
        "type": "text",
        "readonly": True,
        "auto": True,
        "computed": True,
        "required": False,
        "help_text": "Bütün bəndlər işarələnibsə \"Ümumi Lisenziya\", əks halda \"Xüsusi Lisenziya\" "
                     "- sistem tərəfindən avtomatik hesablanır, redaktə oluna bilməz.",
    },
]

# Köhnə adlar geriyə uyğunluq üçün saxlanılıb (bəzi importlar bunlara istinad edə bilər).
_XUSUSI_LISENZIYA_FILE_FIELDS = _LISENZIYA_FILE_FIELDS
_XUSUSI_LISENZIYA_FORM_FIELDS = _LISENZIYA_FORM_FIELDS
_UMUMI_LISENZIYA_FILE_FIELDS = _LISENZIYA_FILE_FIELDS
_UMUMI_LISENZIYA_FORM_FIELDS = _LISENZIYA_FORM_FIELDS

# --- "Fayl yüklə" rejimi - Xüsusi satış icazə sənədi (Image 2) ---
_XUSUSI_SATIS_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (möhürlü)", "required": True, "max_size_mb": 10},
    {"key": "mallarin_siyahisi", "label": "Malların siyahısı / nomenklaturası", "required": True, "max_size_mb": 10},
    {"key": "istehsal_prosesi_melumati", "label": "Malların istehsal prosesi barədə məlumat", "required": True,
     "max_size_mb": 10},
    {"key": "istehsal_idxal_hisseleri_melumati", "label": "Malların istehsal və idxal olunan hissələri barədə məlumat",
     "required": True, "max_size_mb": 10},
    {"key": "texniki_gostericiler", "label": "Malların texniki göstəriciləri", "required": True, "max_size_mb": 10},
    {"key": "texnoloji_konstruksiya_senedleri", "label": "Malların texnoloji konstruksiya sənədləri", "required": True,
     "max_size_mb": 10},
    {"key": "beynelxalq_standart_senedi", "label": "Malların beynəlxalq standartlara uyğunluğu barədə sənəd",
     "required": True, "max_size_mb": 10},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) - Xüsusi satış icazə sənədi (Image 3) ---
_XUSUSI_SATIS_FORM_FIELDS = [
    {"key": "icaze_nomresi", "label": "İcazə nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "istinad_maddesi", "label": "İstinad maddəsi", "type": "text", "readonly": True, "required": True,
     "value": '292 nömrəli Fərman'},
    {"key": "satis_novu", "label": "Satış növü (Daxili satış / İdxal / İxrac)", "type": "select", "required": True,
     "options": SATIS_TYPE_CHOICES},
    {"key": "malin_tesviri", "label": "Malın təsviri", "type": "text", "required": True},
    {"key": "muqavile_nomresi", "label": "Müqavilə nömrəsi", "type": "text", "required": True},
    {"key": "muddet", "label": "Müddət", "type": "text", "readonly": True, "required": True, "value": 'Müddətsiz'},
    {"key": "selahiyyetli_organ", "label": "Səlahiyyətli orqan", "type": "text", "required": False, "auto": False},
]

# --- "Fayl yüklə" rejimi - Gömrükdən Azadolma icazə sənədi ---
_GOMRUKDEN_AZADOLMA_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (möhürlü)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_sureti", "label": "Müqavilənin surəti", "required": True, "max_size_mb": 100},
    {"key": "invoys_sureti", "label": "3.	İdxal olunan malın invoice-nin sürəti", "required": True,
     "max_size_mb": 10},
]

# --- "Fayl yüklə" rejimi - ƏDV-dən Azadolma icazə sənədi ---
_EDVDEN_AZADOLMA_FILE_FIELDS = [
    {"key": "muraciet_mektubu", "label": "Müraciət məktubu (möhürlü)", "required": True, "max_size_mb": 10},
    {"key": "muqavile_sureti", "label": "Müqavilənin surəti", "required": True, "max_size_mb": 100},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) - Gömrükdən Azadolma icazə sənədi ---
_GOMRUKDEN_AZADOLMA_FORM_FIELDS = [
    {"key": "guzest_nomresi", "label": "Güzəşt nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "senedin_novu", "label": "Sənəd növü", "type": "text", "required": True},
    {"key": "mehsulun_kodu", "label": "Məhsulun kodu (XİF MN üzrə kod / HS Code)", "type": "text", "required": True},
    {"key": "baslangic_tarixi", "label": "Başlanğıc tarixi (Sənədin qüvvəyə mindiyi gün)", "type": "date",
     "required": True},
    {"key": "bitme_tarixi", "label": "Bitmə tarixi (+1 il, 365 gün sonra)", "type": "date", "required": False,
     "auto": True},
    {"key": "techizatci", "label": "Təchizatçı", "type": "text", "required": True, "auto": True},
    {"key": "status", "label": "Status", "type": "select", "required": True, "options": STATUS_CHOICES},
]

# --- "Elektron müraciət forması" (Lisenziya anketi) - ƏDV-dən Azadolma icazə sənədi ---
_EDVDEN_AZADOLMA_FORM_FIELDS = [
    {"key": "guzest_nomresi", "label": "Güzəşt nömrəsi", "type": "text", "required": True, "auto": True},
    {"key": "senedin_novu", "label": "Sənəd növü", "type": "text", "required": True},
    {"key": "mehsulun_kodu", "label": "Məhsulun kodu (XİF MN üzrə kod / HS Code)", "type": "text", "required": True},
    {"key": "baslangic_tarixi", "label": "Başlanğıc tarixi (Sənədin qüvvəyə mindiyi gün)", "type": "date",
     "required": True},
    {"key": "bitme_tarixi", "label": "Bitmə tarixi (+1 il, 365 gün sonra)", "type": "date", "required": False,
     "auto": True},
    {"key": "techizatci", "label": "Təchizatçı", "type": "text", "required": True, "auto": True},
    {"key": "status", "label": "Status", "type": "select", "required": True, "options": STATUS_CHOICES},
]

_SCHEMA_BY_DOC_TYPE = {
    "ixrac": {"file_fields": _IXRAC_FILE_FIELDS, "form_fields": _FORM_FIELDS},
    "idxal": {"file_fields": _IDXAL_FILE_FIELDS, "form_fields": _FORM_FIELDS},
    "istehsal": {"file_fields": _ISTEHSAL_FILE_FIELDS, "form_fields": _ISTEHSAL_FORM_FIELDS},
    "xususi_lisenziya": {"file_fields": _LISENZIYA_FILE_FIELDS, "form_fields": _LISENZIYA_FORM_FIELDS},
    "umumi_lisenziya": {"file_fields": _LISENZIYA_FILE_FIELDS, "form_fields": _LISENZIYA_FORM_FIELDS},
    "xususi_satis": {"file_fields": _XUSUSI_SATIS_FILE_FIELDS, "form_fields": _XUSUSI_SATIS_FORM_FIELDS},
    "gomrukden_azadolma": {"file_fields": _GOMRUKDEN_AZADOLMA_FILE_FIELDS,
                           "form_fields": _GOMRUKDEN_AZADOLMA_FORM_FIELDS},
    "edvden_azadolma": {"file_fields": _EDVDEN_AZADOLMA_FILE_FIELDS, "form_fields": _EDVDEN_AZADOLMA_FORM_FIELDS},
}


LISENZIYA_DOC_TYPES = {"xususi_lisenziya", "umumi_lisenziya"}


def get_schema(doc_type: str) -> dict:
    schema = _SCHEMA_BY_DOC_TYPE.get(doc_type, _SCHEMA_BY_DOC_TYPE["idxal"])
    return {
        "doc_type": doc_type,
        "file_fields": schema["file_fields"],
        "form_fields": schema["form_fields"],
    }