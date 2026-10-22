"""Verilmiş təşkilat siyahısını "Təşkilatlar" cədvəlinə əlavə edir.

İstifadə:
    python manage.py seed_organizations --dry-run   # nə olacağını göstərir, heç nə yazmır
    python manage.py seed_organizations             # əlavə edir

Təkrar işlədilə bilər: təşkilat VÖEN-ə görə axtarılır, bazada artıq varsa DƏYİŞDİRİLMİR
(ad/ünvan/üst təşkilat toxunulmaz qalır), yalnız olmayanlar əlavə olunur.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from organizations.models import Organization

# (tam ad, VÖEN, hüquqi ünvan)

# Lisenziyaları "lisenziyalarin_formasi.xlsx" faylında olan şirkətlər.
# Bazadakı mövcud qayda ilə eyni: Nazirliyin (code="msn") alt təşkilatı kimi əlavə olunur.
EXCEL_COMPANIES = [
    ('"6LSYSTEMS" Məhdud Məsuliyyətli Cəmiyyəti', "1308128831", 'Bakı şəhəri, Yasamal rayonu, Şəfayət Mehdiyev, ev 81'),
    ('"Techinco" Məhdud Məsuliyyətli Cəmiyyəti', "1406942831", 'Bakı şəhəri, Nəsimi rayonu, R. Rza, ev 75, Winter Park Plaza'),
    ('"İTX MOTORS" Məhdud Məsuliyyətli Cəmiyyəti', "1102978851", 'Bakı şəhəri, Qaradağ rayonu, Salyan şossesi, ev 15-ci km, 20'),
    ('"Bayraktar Texnoloji Azərbaycan" MMC', "1506112521", 'Bakı şəhəri, Nəsimi rayonu, Zərifə Əliyeva, ev 115'),
    ('"USH GROUP" Məhdud Məsuliyyətli Cəmiyyəti', "1504745421", 'Bakı şəhəri, Nərimanov rayonu, Əhməd Rəcəbli, ev 5A, m.60'),
    ('"SYNAPLINE TECHNOLOGIES" MMC', "1307258891", 'Bakı şəhəri, Yasamal rayonu, Mətbuat pr., ev 35C, m.140'),
    ('"RD SMART" Qapalı Səhmdar Cəmiyyəti', "1306586221", 'Bakı şəhəri, Yasamal rayonu, Xarici Dairəvi, ev. Yol 10'),
    ('"TEXDEFENS" Məhdud Məsuliyyətli Cəmiyyəti', "1009018191", 'Bakı şəhəri, Binəqədi rayonu, S. S. Axundov, ev. 361a, m. 19'),
    ('"ASELSAN-BAKÜ" Məhdud Məsuliyyətli Cəmiyyəti', "1700022281", 'Bakı şəhəri, Yasamal rayonu, H. Cavid pr., ev 8C, Məhəllə 520'),
    ('"Vland Systems" Məhdud Məsuliyyətli Cəmiyyəti', "2906014981", 'Sumqayıt şəhəri, H.Z.Tağıyev, ev Texnopark'),
    ('"AZROKSAN" Məhdud Məsuliyyətli Cəmiyyəti', "2906738631", 'Sumqayıt şəhəri, Zeynalabdin Tağıyev qəs., ev Texnopark'),
    ('"SAMT" Məhdud Məsuliyyətli Cəmiyyəti', "2907009611", 'Sumqayıt şəhəri, H.Z Tağıyev, ev Texnopark'),
    ('"UMUD TECHNOLOGİES" MMC', "1903092051", 'Bakı şəhəri, Suraxanı rayonu, Bülbülə ŞTQ, 3-cü Mədən'),
    ('"ARKAN İNNOVATİONS" MMC', "1309638971", 'Bakı şəhəri, Yasamal rayonu, Mətbuat pr., ev 40'),
    ('"DEFTECH AZERBAİJAN" MMC', "1006903071", 'Bakı şəhəri, Suraxanı ray., Yaşayış sahəsi D, ev 30, mən. 34'),
    ('"Blackyard" Məhdud Məsuliyyətli Cəmiyyəti', "2009568411", 'Bakı şəhəri, Xətai rayonu, Süleyman Vəzirov, ev 17, m. 5'),
    ('"HARDFORGE ENGİNEERİNG" MMC', "2009601151", 'Bakı şəhəri, Xətai rayonu, Qədir Məmmədov, ev 7A, m. 35'),
    ('"FİRECORP" Məhdud Məsuliyyətli Cəmiyyəti', "1309939431", 'Bakı şəhəri, Yasamal rayonu, H. Zərdabi pr., ev 92A, m. 294'),
    ('"RYNEX SOLUTİONS" MMC', "1009477351", 'Bakı şəhəri, Binəqədi rayonu, Mikrorayon 7, ev 16A, m. 27'),
    ('"VEXA DS" Məhdud Məsuliyyətli Cəmiyyəti', "2908280041", 'Sumqayıt şəhəri, H.Z.Tağıyev, ev Texnopark sahəsi'),
]

# Nazirliyin strukturuna DAXİL OLMAYAN müəssisələr (üst təşkilat təyin olunmur).
STANDALONE_COMPANIES = [
    ('"Novasis" MMC', "1309515601", 'AZ1141, BAKI ŞƏHƏRİ YASAMAL RAYONU, MƏTBUAT PR., ev.40'),
    ('"İqlim" Elmi-İstehsalat Müəssisəsi MMC', "9900048161", 'AZ1093, BAKI ŞƏHƏRİ XƏZƏR RAYONU, BUZOVNA QƏSƏBƏSİ, MƏMMƏD NAMAZOV, ev.157'),
    ('"Sənayecihaz" Elmi-İstehsalat Müəssisəsi', "9900053221", 'AZ1108, BAKI ŞƏHƏRİ BİNƏQƏDİ RAYONU, ZİYA BÜNYADOV, ev.15'),
    ('"Zireh" MMC', "1806812581", 'AZ1104, BAKI ŞƏHƏRİ SABUNÇU RAYONU, ZABRAT ŞTQ, 18 OKTYABR, ev.106'),
    ('"Cihaz İstehsalat Birliyi" MMC', "1001009951", 'AZ1108, BAKI ŞƏHƏRİ BİNƏQƏDİ RAYONU, ZİYA BÜNYADOV, ev.15'),
]

# Müdafiə Sənayesi Nazirliyinin strukturuna daxil olan müəssisələr (üst təşkilat = Nazirlik).
MSN_STRUCTURE = [
    ('"Təhlükəsizlik və Mühafizə İdarəsi" MMC', "1001007011", 'AZ1108, BAKI ŞƏHƏRİ BİNƏQƏDİ RAYONU, ZİYA BÜNYADOV, ev.15'),
    ('"Şərq İstehsalat Birliyi" MMC', "1200272031", 'AZ1093, BAKI ŞƏHƏRİ XƏZƏR RAYONU, BUZOVNA QƏSƏBƏSİ, MƏMMƏD NAMAZOV, ev.157'),
    ('"Miras" MMC', "1902984111", 'AZ1006, BAKI ŞƏHƏRİ YASAMAL RAYONU, PARLAMENT PR., ev.3'),
]

# QEYD: "MSTİM" (Müdafiə Sənayesi Tədqiqat və İnnovasiya Mərkəzi) bura daxil EDİLMƏYİB -
# "Qeydiyyatı gözlənilir", VÖEN-i yoxdur, Organization.voen isə məcburi və unikaldır.
# VÖEN verildikdən sonra MSN_STRUCTURE siyahısına əlavə edib komandanı yenidən işlədin
# (adı: "Müdafiə Sənayesi Tədqiqat və İnnovasiya Mərkəzi", ünvan: BAKI ŞƏHƏRİ XƏTAİ RAYONU,
# RAHİB MƏMMƏDOV küçəsi 25).


class Command(BaseCommand):
    help = "Verilmiş təşkilatları (VÖEN-ə görə, olanları keçməklə) Təşkilatlar cədvəlinə əlavə edir."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Heç nə yazma, yalnız nəticəni göstər.")

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        msn = Organization.objects.filter(code=Organization.CODE_MSN).order_by("id").first()
        if msn is None:
            self.stdout.write(self.style.WARNING(
                "Nazirlik təşkilatı (code='msn') bazada tapılmadı - alt təşkilat olmalı olanlar üst təşkilatsız yaradılacaq."
            ))

        groups = [
            ("Excel (lisenziya sahibləri)", EXCEL_COMPANIES, msn),
            ("Nazirliyin strukturuna daxil olmayanlar", STANDALONE_COMPANIES, None),
            ("Nazirliyin strukturuna daxil olanlar", MSN_STRUCTURE, msn),
        ]

        created = skipped = 0
        for title, items, parent in groups:
            self.stdout.write(self.style.MIGRATE_HEADING(title))
            for full_name, voen, address in items:
                existing = Organization.objects.filter(voen=voen).first()
                if existing:
                    skipped += 1
                    self.stdout.write(f"  = {voen}  artıq var (id={existing.id}): {existing.full_name}")
                    continue
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {voen}  {full_name}"))
                if not dry:
                    Organization.objects.create(
                        code=Organization.CODE_OTHER, full_name=full_name, voen=voen,
                        address=address, parent=parent, is_active=True,
                    )

        verb = "əlavə olunacaq" if dry else "əlavə olundu"
        self.stdout.write(f"\nYekun: {created} {verb}, {skipped} artıq mövcud idi (dəyişdirilmədi).")
        if dry:
            self.stdout.write("(--dry-run: bazaya heç nə yazılmadı)")
