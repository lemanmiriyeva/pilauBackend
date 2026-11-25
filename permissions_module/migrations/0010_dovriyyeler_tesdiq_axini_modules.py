from django.db import migrations, models


def add_modules(apps, schema_editor):
    Module = apps.get_model("permissions_module", "Module")
    # Dövriyyələr - ayrıca modul (sidebar-da görünür, modul icazələrində verilə bilir)
    Module.objects.get_or_create(
        key="dovriyyeler", parent=None,
        defaults={
            "title": "Dövriyyələr",
            "description": "Təşkilatların idxal/ixrac dövriyyə qeydləri.",
            "icon": "swap_horiz", "order": 6,
        },
    )
    # Təsdiq axını - yalnız İnzibatçı panelinin daxilində (sidebar-da ayrıca modul YOXDUR)
    panel = Module.objects.filter(key="inzibatci-paneli", parent=None).first()
    if panel:
        Module.objects.get_or_create(
            key="tesdiq-axini", parent=panel,
            defaults={
                "title": "Təsdiq axını",
                "description": "Sənəd növləri üzrə təsdiq axınının və imzalayanın konfiqurasiyası.",
                "icon": "fact_check", "order": 5,
            },
        )


def remove_modules(apps, schema_editor):
    Module = apps.get_model("permissions_module", "Module")
    Module.objects.filter(key="dovriyyeler", parent=None).delete()


class Migration(migrations.Migration):
    dependencies = [("permissions_module", "0009_partner_companies_module")]
    operations = [migrations.RunPython(add_modules, remove_modules)]
