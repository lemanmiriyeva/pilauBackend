"""
Mail konfiqurasiyasını sürətlə yoxlamaq üçün:

    python manage.py send_test_email your@address.com

Əvvəlcə cari EMAIL_* ayarlarını göstərir (parol gizlədilmiş), sonra həqiqi bir mail
göndərməyə cəhd edir və nəticəni (uğur/xəta, tam exception mətni ilə) ekrana çap edir.
Bu, forgot-password axınından fərqli olaraq xətanı UDMUR - səbəbi birbaşa görəcəksiniz.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "SMTP/EMAIL_* ayarlarını yoxlamaq üçün test maili göndərir."

    def add_arguments(self, parser):
        parser.add_argument("to_email", type=str, help="Test mailinin göndəriləcəyi ünvan")

    def handle(self, *args, **options):
        to_email = options["to_email"]

        self.stdout.write(self.style.MIGRATE_HEADING("Cari EMAIL ayarları:"))
        self.stdout.write(f"  EMAIL_BACKEND      = {settings.EMAIL_BACKEND}")
        self.stdout.write(f"  EMAIL_HOST         = {settings.EMAIL_HOST or '(boşdur!)'}")
        self.stdout.write(f"  EMAIL_PORT         = {settings.EMAIL_PORT}")
        self.stdout.write(f"  EMAIL_USE_TLS      = {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  EMAIL_HOST_USER    = {settings.EMAIL_HOST_USER or '(boşdur!)'}")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD= {'(doludur, gizlədilib)' if settings.EMAIL_HOST_PASSWORD else '(boşdur!)'}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL = {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write("")

        if not settings.EMAIL_HOST:
            raise CommandError(
                "EMAIL_HOST boşdur -> mail 'console' backend ilə terminala yazılacaq, "
                "real SMTP-yə getməyəcək. .env faylında EMAIL_HOST təyin edin (məs. smtp.gmail.com)."
            )

        self.stdout.write(f"'{to_email}' ünvanına test maili göndərilir...")
        try:
            send_mail(
                subject="PİLAU - test maili",
                message="Bu, EMAIL_* ayarlarınızın düzgün işlədiyini yoxlamaq üçün göndərilən test mailidir.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"UĞURSUZ: {exc!r}"))
            self.stdout.write(self.style.WARNING(
                "Ən çox rast gəlinən səbəblər:\n"
                "  - Gmail/Outlook: adi hesab parolu ilə deyil, 'App password' (tətbiq parolu) ilə\n"
                "    daxil olmaq lazımdır (adi parolla SMTPAuthenticationError verir).\n"
                "  - EMAIL_PORT/EMAIL_USE_TLS uyğunsuzluğu: 587 üçün TLS=True olmalıdır,\n"
                "    465 (SSL) istifadə edirsinizsə fərqli backend/parametr lazımdır.\n"
                "  - Hosting/firewall SMTP portunu (25/587) bağlayıb - bir çox bulud provayderi\n"
                "    (məs. bəzi PaaS-lar) çıxış SMTP trafikini defolt olaraq bloklayır.\n"
                "  - .env faylı production mühitinə düzgün yüklənməyib."
            ))
            raise CommandError("Mail göndərilmədi - yuxarıdakı xətaya bax.")

        self.stdout.write(self.style.SUCCESS(f"UĞURLU: test maili '{to_email}' ünvanına göndərildi."))