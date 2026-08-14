from permissions_module.models import Module

# --- Ust seviyye modullar ---
lisenziya, _ = Module.objects.get_or_create(
    key="lisenziya-senedler", parent=None,
    defaults={
        "title": "Lisenziya və icazə sənədləri",
        "description": "Lisenziyaların və sənədlərin yaradılması, statuslarının izlənməsi və təsdiqi.",
        "icon": "gavel",
        "order": 1,
    },
)

hesabatlar, _ = Module.objects.get_or_create(
    key="hesabatlar", parent=None,
    defaults={
        "title": "Hesabatlar",
        "description": "Dövri istehsalat və təchizat hesabatlarının formalaşdırılması.",
        "icon": "assessment",
        "order": 2,
    },
)

teskilatlar, _ = Module.objects.get_or_create(
    key="teskilatlar", parent=None,
    defaults={
        "title": "Təşkilatlar",
        "description": "Hüquqi şəxslərin yaradılması və onlarla bağlı icazələrin idarə edilməsi.",
        "icon": "apartment",
        "order": 3,
    },
)

inzibatci, _ = Module.objects.get_or_create(
    key="inzibatci-paneli", parent=None,
    defaults={
        "title": "İnzibatçı paneli",
        "description": "Modullar və sənədlər üçün təşkilat və şəxslərə icazələrin verilməsi.",
        "icon": "manage_accounts",
        "order": 4,
    },
)

# --- 'İnzibatçı paneli' altinda alt-modullar (Image 1) ---
Module.objects.get_or_create(
    key="istifadeciler", parent=inzibatci,
    defaults={
        "title": "İstifadəçilər",
        "description": "Sistemə yeni istifadəçilərin qeydiyyatı, mövcud istifadəçilərin redaktəsi.",
        "icon": "manage_accounts",
        "order": 1,
    },
)
Module.objects.get_or_create(
    key="icazelerin-idaresi", parent=inzibatci,
    defaults={
        "title": "İcazələrin idarə edilməsi",
        "description": "İstifadəçi və təşkilatlara modullara giriş icazələrinin verilməsi və idarə edilməsi.",
        "icon": "description",
        "order": 2,
    },
)

# --- 'Lisenziya' altinda alt-modullar ---
Module.objects.get_or_create(
    key="istehsal", parent=lisenziya,
    defaults={"title": "İstehsal lisenziyası", "meta": "Müddətsiz", "icon": "gavel", "order": 1},
)
Module.objects.get_or_create(
    key="xususi-satis", parent=lisenziya,
    defaults={"title": "Xüsusi satış icazə sənədi", "meta": "Müddətsiz", "icon": "local_shipping", "order": 2},
)
Module.objects.get_or_create(
    key="idxal-ixrac", parent=lisenziya,
    defaults={"title": "İdxal İxrac (İcazə sənədi)", "meta": "1 illik + Say/Kəmiyyat nəzarəti",
              "icon": "import_export", "order": 3},
)
Module.objects.get_or_create(
    key="edv-guzesti", parent=lisenziya,
    defaults={"title": "ƏDV Güzəşti (İcazə sənədi)", "meta": "1 illik + Maliyyə təsdiqi",
              "icon": "percent", "order": 4},
)

print("Modullar yaradıldı:", list(Module.objects.values_list("title", flat=True)))