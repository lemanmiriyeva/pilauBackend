from django.db import migrations


def add_module(apps, schema_editor):
    Module = apps.get_model("permissions_module", "Module")
    Module.objects.get_or_create(
        key="partnyor-sirketler", parent=None,
        defaults={
            "title": "Partnyor şirkətlər",
            "description": "Partnyor şirkətlərin qeydiyyatı və təşkilatlarla əlaqələndirilməsi.",
            "icon": "apartment",
            "order": 5,
        },
    )


def remove_module(apps, schema_editor):
    apps.get_model("permissions_module", "Module").objects.filter(key="partnyor-sirketler", parent=None).delete()


class Migration(migrations.Migration):
    dependencies = [("permissions_module", "0008_globalorgmoduleaccess_organizationmodulesettings")]
    operations = [migrations.RunPython(add_module, remove_module)]
