"""Müdafiə sənayesi sahəsi üçün nomenklatura nümunə (saxta) datası.

İstifadə:
    python manage.py seed_nomenclature            # kateqoriya, alt kateqoriya və nomenklaturanı yaradır
    python manage.py seed_nomenclature --assign   # + hər mövqeyi 1-3 təsadüfi təşkilata təyin edir (MSN xaric)

İdempotentdir: təkrar işlətsəniz dublikat yaranmır. Yalnız mülki/müdafiə xarakterli ümumi mövqelərdir
(qoruyucu vasitələr, optika, rabitə, PUA komponentləri, ehtiyat hissələri, materiallar, elektronika,
tibbi/təlim, sınaq avadanlığı) - real texniki xüsusiyyət və ya sursat/partlayıcı mövqeyi yoxdur.
"""
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from organizations.models import (
    Nomenclature, NomenclatureCategory, NomenclatureOperationType, NomenclatureSubcategory, Organization,
)

OPERATION_TYPES = ["İdxal", "İxrac", "ƏDV azad olma", "Satış", "İstehsal"]

# (kateqoriya, alt kateqoriya, ad, ölçü vahidi, əməliyyat növü, qeyd)
DATA = [
    # --- 1. Fərdi qoruyucu vasitələr
    ("Fərdi qoruyucu vasitələr", "Bronejiletlər və plitələr", "Taktiki bronejilet (qoruyucu jilet)", "ədəd", "İstehsal", "Sertifikatlı, seriyalı istehsal; ölçü qrupları S-XXL."),
    ("Fərdi qoruyucu vasitələr", "Bronejiletlər və plitələr", "Keramik-kompozit qoruyucu plitə", "ədəd", "İstehsal", "Jilet üçün dəyişdirilə bilən plitə."),
    ("Fərdi qoruyucu vasitələr", "Dəbilqələr və qoruyucu başlıqlar", "Ballistik qoruyucu dəbilqə", "ədəd", "İstehsal", "Daxili tənzimlənən ayaqqabı tipli bərkidici sistemlə."),
    ("Fərdi qoruyucu vasitələr", "Dəbilqələr və qoruyucu başlıqlar", "Eşitmə qoruyucu aktiv qulaqlıq", "cüt", "İdxal", "Səs-küy azaldan, rabitə dəstəkli."),
    ("Fərdi qoruyucu vasitələr", "Taktiki geyim və ləvazimat", "Çöl forması dəsti (kamuflyaj)", "komplekt", "Satış", "Gödəkçə + şalvar, rip-stop parça."),
    ("Fərdi qoruyucu vasitələr", "Taktiki geyim və ləvazimat", "Taktiki bel çantası 40 litr", "ədəd", "İxrac", "Su keçirməyən, MOLLE tipli bərkidicilər."),
    ("Fərdi qoruyucu vasitələr", "Taktiki geyim və ləvazimat", "Taktiki əlcək", "cüt", "Satış", "Möhkəmləndirilmiş ovuc hissəsi."),
    ("Fərdi qoruyucu vasitələr", "Taktiki geyim və ləvazimat", "Diz və dirsək qoruyucuları", "komplekt", "İdxal", "Sərt qabıqlı, tənzimlənən qayışlı."),
    # --- 2. Optik və optoelektron cihazlar
    ("Optik və optoelektron cihazlar", "Gecə görmə cihazları", "Gecə görmə monokulyarı", "ədəd", "İdxal", "Nəsil 3 elektron-optik çevirici, 1x böyütmə."),
    ("Optik və optoelektron cihazlar", "Gecə görmə cihazları", "Gecə görmə eynəyi (binokulyar)", "ədəd", "İdxal", "Dəbilqəyə bərkidilə bilən."),
    ("Optik və optoelektron cihazlar", "İstilik görüntüləyicilər", "Portativ istilik görüntüləyici kamera", "ədəd", "İdxal", "640x480 detektor, 30 Hz."),
    ("Optik və optoelektron cihazlar", "İstilik görüntüləyicilər", "İnfraqırmızı optik linza modulu", "ədəd", "ƏDV azad olma", "Germanium linza, 35 mm fokus məsafəsi."),
    ("Optik və optoelektron cihazlar", "Dürbün və məsafəölçənlər", "Hərbi dürbün 10x42", "ədəd", "Satış", "Su və toz keçirməyən korpus."),
    ("Optik və optoelektron cihazlar", "Dürbün və məsafəölçənlər", "Lazer məsafəölçən", "ədəd", "İdxal", "Ölçmə diapazonu 1500 m-ə qədər."),
    # --- 3. Rabitə və naviqasiya
    ("Rabitə və naviqasiya", "Radiostansiyalar", "Portativ taktiki radiostansiya (VHF/UHF)", "ədəd", "İstehsal", "Rəqəmsal rejim, IP67 qorunma sinfi."),
    ("Rabitə və naviqasiya", "Radiostansiyalar", "Şifrələnmiş rabitə modulu", "ədəd", "İstehsal", "Radiostansiyaya inteqrasiya olunan."),
    ("Rabitə və naviqasiya", "Antenalar və kabellər", "Mobil antenna sistemi", "komplekt", "İstehsal", "Teleskopik dayaq, nəqliyyat çantası ilə."),
    ("Rabitə və naviqasiya", "Antenalar və kabellər", "Sahə telefon kabeli (500 m rulon)", "rulon", "Satış", "Çöl şəraiti üçün möhkəmləndirilmiş izolyasiya."),
    ("Rabitə və naviqasiya", "Naviqasiya", "GNSS naviqasiya qəbuledicisi", "ədəd", "İdxal", "Çoxkanallı, GPS/GLONASS/Galileo."),
    ("Rabitə və naviqasiya", "Naviqasiya", "Rəqəmsal kompas və inklinometr", "ədəd", "İdxal", "Aşağı enerji istehlakı."),
    # --- 4. Pilotsuz uçuş aparatları (PUA) və komponentləri
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Gövdə və konstruksiya", "Karbon-plastik PUA gövdəsi", "ədəd", "İstehsal", "Yüngül konstruksiya, modul quruluşlu."),
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Gövdə və konstruksiya", "Qatlanan PUA qolu (karbon boru)", "ədəd", "İstehsal", "Sürətli qatlanma mexanizmi."),
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Elektrik və idarəetmə", "Fırçasız elektrik mühərriki (PUA üçün)", "ədəd", "İdxal", "Yüksək fırlanma momenti, 6S uyğun."),
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Elektrik və idarəetmə", "Uçuş nəzarətçisi (kontroller) modulu", "ədəd", "İdxal", "Rezerv sensorlu, avtopilot proqram təminatı ilə."),
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Elektrik və idarəetmə", "Li-Po akkumulyator 22000 mAh", "ədəd", "ƏDV azad olma", "6S, 22.2 V; daşınma zamanı xüsusi qablaşdırma."),
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Elektrik və idarəetmə", "Stabilizasiyalı gimbal kamera", "ədəd", "İdxal", "3 oxlu stabilizator, 4K video."),
    ("Pilotsuz uçuş aparatları (PUA) və komponentləri", "Yerüstü idarəetmə", "PUA yerüstü idarəetmə stansiyası", "komplekt", "İstehsal", "Planşet, antena və pult daxildir."),
    # --- 5. Xüsusi nəqliyyat vasitələri üçün ehtiyat hissələri
    ("Xüsusi nəqliyyat üçün ehtiyat hissələri", "Mühərrik və transmissiya", "Dizel mühərrik filtr dəsti", "komplekt", "Satış", "Yağ, yanacaq və hava filtrləri."),
    ("Xüsusi nəqliyyat üçün ehtiyat hissələri", "Mühərrik və transmissiya", "Ötürmə qutusu yağı (20 litr)", "litr", "İdxal", "Geniş temperatur diapazonu."),
    ("Xüsusi nəqliyyat üçün ehtiyat hissələri", "Şassi və asqı", "Hərbi təkər 14.00R20", "ədəd", "İdxal", "Dəmir yol keçməyən relyef üçün."),
    ("Xüsusi nəqliyyat üçün ehtiyat hissələri", "Şassi və asqı", "Əyləc kolodkası dəsti", "komplekt", "Satış", "Ağır texnika üçün."),
    ("Xüsusi nəqliyyat üçün ehtiyat hissələri", "Elektrik avadanlığı", "Akkumulyator 12V 190Ah", "ədəd", "Satış", "Soyuq hava şəraitində işə salma dəstəyi."),
    ("Xüsusi nəqliyyat üçün ehtiyat hissələri", "Elektrik avadanlığı", "Zirehli çoxqatlı şüşə panel", "m²", "İstehsal", "Nəqliyyat vasitəsi pəncərələri üçün, 38 mm."),
    # --- 6. Xammal və materiallar
    ("Xammal və materiallar", "Metal və ərintilər", "Yüksək möhkəmlikli polad təbəqə (3 mm)", "ton", "İdxal", "Qaynaq oluna bilən, sertifikatlı."),
    ("Xammal və materiallar", "Metal və ərintilər", "Alüminium ərinti profili", "kq", "İdxal", "Aviasiya sinifli, anodlaşdırılmış."),
    ("Xammal və materiallar", "Kompozit və polimerlər", "Karbon lif parça", "m²", "İdxal", "200 q/m², epoksid qatranla uyğun."),
    ("Xammal və materiallar", "Kompozit və polimerlər", "Poliüretan kompozit lövhə", "kq", "İstehsal", "Zərbə sönümləndirici qatlar üçün."),
    ("Xammal və materiallar", "Tekstil", "Aramid lifli parça", "metr", "İdxal", "Yanmaya davamlı, yüngül."),
    ("Xammal və materiallar", "Tekstil", "Kamuflyaj parça (rip-stop)", "metr", "İxrac", "İnfraqırmızı spektrdə kamuflyaj xassəli."),
    # --- 7. Elektronika və komponentlər
    ("Elektronika və komponentlər", "Çap lövhələri və mikrosxemlər", "Çap elektron lövhə (PCB, 4 qatlı)", "ədəd", "İxrac", "Sənaye sinifli, qızıl örtüklü kontaktlar."),
    ("Elektronika və komponentlər", "Çap lövhələri və mikrosxemlər", "Mikrokontroller çipi (ARM tipli)", "ədəd", "İdxal", "Geniş temperatur diapazonu (-40...+85 °C)."),
    ("Elektronika və komponentlər", "Sensorlar", "İnersial ölçmə modulu (IMU)", "ədəd", "İdxal", "6 oxlu, yüksək dəqiqlikli."),
    ("Elektronika və komponentlər", "Sensorlar", "Təzyiq və temperatur sensoru", "ədəd", "İdxal", "Sənaye interfeysli (I2C/SPI)."),
    ("Elektronika və komponentlər", "Enerji təchizatı", "DC-DC gərginlik çeviricisi 24V/12V", "ədəd", "İstehsal", "Qısa qapanmadan qorumalı."),
    ("Elektronika və komponentlər", "Enerji təchizatı", "Günəş panelli portativ enerji stansiyası", "komplekt", "Satış", "Çöl şəraiti üçün, 500 Wh."),
    # --- 8. Tibbi və təlim təchizatı
    ("Tibbi və təlim təchizatı", "Hərbi tibbi ləvazimat", "Fərdi ilk yardım dəsti", "komplekt", "Satış", "Sarğı, turnike, dərman qutusu daxildir."),
    ("Tibbi və təlim təchizatı", "Hərbi tibbi ləvazimat", "Qanaxmanı dayandıran turnike", "ədəd", "ƏDV azad olma", "Tək əllə tətbiq oluna bilən."),
    ("Tibbi və təlim təchizatı", "Hərbi tibbi ləvazimat", "Qatlanan evakuasiya xərəyi", "ədəd", "İxrac", "Yüngül alüminium çərçivə."),
    ("Tibbi və təlim təchizatı", "Təlim simulyatorları", "Sürücülük təlim simulyatoru", "komplekt", "İxrac", "Xüsusi texnika sürücüləri üçün, 3 ekranlı."),
    ("Tibbi və təlim təchizatı", "Təlim simulyatorları", "Çöl hospital çadırı 24 m²", "ədəd", "İstehsal", "Sürətli qurulan, isitmə sistemi ilə."),
    # --- 9. Sınaq və ölçü avadanlığı
    ("Sınaq və ölçü avadanlığı", "Ölçü cihazları", "Rəqəmsal osiloskop 100 MHz", "ədəd", "İdxal", "4 kanallı, USB interfeysli."),
    ("Sınaq və ölçü avadanlığı", "Ölçü cihazları", "Spektr analizatoru", "ədəd", "İdxal", "9 kHz - 6 GHz diapazon."),
    ("Sınaq və ölçü avadanlığı", "Sınaq stendləri", "Vibrasiya sınaq stendi", "ədəd", "İstehsal", "Elektron blokların davamlılıq sınağı üçün."),
    ("Sınaq və ölçü avadanlığı", "Sınaq stendləri", "Kalibrləmə dəsti (ölçü cihazları)", "komplekt", "Satış", "Etalon məlumat kartları ilə."),
]


class Command(BaseCommand):
    help = "Müdafiə sənayesi üzrə nomenklatura nümunə datasını yaradır (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--assign", action="store_true",
                            help="Hər mövqeyi 1-3 təsadüfi təşkilata təyin et (Nazirlik xaric).")

    @transaction.atomic
    def handle(self, *args, **opts):
        ops = {n: NomenclatureOperationType.objects.get_or_create(name=n)[0] for n in OPERATION_TYPES}
        cats, subs = {}, {}
        created = 0
        items = []
        for cat, sub, name, unit, op, note in DATA:
            if cat not in cats:
                cats[cat] = NomenclatureCategory.objects.get_or_create(name=cat)[0]
            if (cat, sub) not in subs:
                subs[(cat, sub)] = NomenclatureSubcategory.objects.get_or_create(category=cats[cat], name=sub)[0]
            obj, was_created = Nomenclature.objects.get_or_create(
                name=name, category=cats[cat], operation_type=ops[op],
                defaults={"subcategory": subs[(cat, sub)], "unit": unit, "note": note},
            )
            created += int(was_created)
            items.append(obj)

        self.stdout.write(self.style.SUCCESS(
            f"Kateqoriya: {len(cats)}, alt kateqoriya: {len(subs)}, nomenklatura: {len(DATA)} (yeni yaradılan: {created})"
        ))

        if opts["assign"]:
            orgs = list(Organization.objects.filter(is_active=True).exclude(code=Organization.CODE_MSN))
            if not orgs:
                self.stdout.write(self.style.WARNING("Təyin etmək üçün təşkilat tapılmadı."))
                return
            rng = random.Random(42)  # hər dəfə eyni nəticə
            for obj in items:
                obj.organizations.add(*rng.sample(orgs, k=min(len(orgs), rng.randint(1, 3))))
            self.stdout.write(self.style.SUCCESS(f"{len(items)} mövqe {len(orgs)} təşkilat arasında bölündü."))
