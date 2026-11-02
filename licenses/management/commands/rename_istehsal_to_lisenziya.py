"""Bir dəfəlik, təkrar işlədilə bilən (idempotent) keçid:

1. Menyudakı "istehsal" modulunun açarı "lisenziya" olur -> URL
   /modullar/lisenziya-senedler/istehsal  ->  /modullar/lisenziya-senedler/lisenziya
   (Module.key dəyişir, istifadəçi icazələri modula FK ilə bağlıdır deyə itmir).
2. Mövcud sənədlərdə istinad maddəsi bəndlərinin köhnə açarları yeniləri ilə əvəz olunur:
     bend_6_N -> bend_texnika_N + bend_silah_N     (6-cı maddə texnika və silaha bölündü)
     bend_7_N -> bend_sursat_N

İstifadə:  python manage.py rename_istehsal_to_lisenziya [--dry-run]
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from licenses.models import PermitDocument
from permissions_module.models import Module


def _map_keys(keys):
    out = []
    for k in keys or []:
        m = re.fullmatch(r"bend_([67])_([1-5])", k)
        if not m:
            out.append(k)
        elif m.group(1) == "6":
            out += [f"bend_texnika_{m.group(2)}", f"bend_silah_{m.group(2)}"]
        else:
            out.append(f"bend_sursat_{m.group(2)}")
    seen = set()
    return [k for k in out if not (k in seen or seen.add(k))]


class Command(BaseCommand):
    help = "'istehsal' modulunu 'lisenziya' adlandırır və köhnə bənd açarlarını yeniləyir."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        for mod in Module.objects.filter(key="istehsal"):
            if Module.objects.filter(parent=mod.parent, key="lisenziya").exists():
                self.stdout.write(f"Modul {mod.id}: 'lisenziya' artıq var, keçildi")
                continue
            self.stdout.write(f"Modul {mod.id}: key istehsal -> lisenziya")
            if not dry:
                mod.key = "lisenziya"
                mod.title = "Lisenziya"
                mod.save()

        changed = 0
        for doc in PermitDocument.objects.all():
            fd = doc.form_data or {}
            old = fd.get("istinad_maddesi_bendleri")
            if not old:
                continue
            new = _map_keys(old)
            if new != old:
                changed += 1
                if not dry:
                    fd["istinad_maddesi_bendleri"] = new
                    # save() çağırmırıq (nömrə/PDF/status yan təsirləri olmasın)
                    PermitDocument.objects.filter(pk=doc.pk).update(form_data=fd)
        self.stdout.write(self.style.SUCCESS(f"Sənəd bəndləri yenilənən: {changed}" + (" (dry-run)" if dry else "")))
        if dry:
            transaction.set_rollback(True)
