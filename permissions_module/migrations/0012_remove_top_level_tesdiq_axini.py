from django.db import migrations


def remove_top_level(apps, schema_editor):
    """Təsdiq axını yalnız İnzibatçı panelinin daxilində olur - əvvəlki versiyada yaranmış ayrıca
    (üst səviyyəli) modul silinir."""
    apps.get_model("permissions_module", "Module").objects.filter(key="tesdiq-axini", parent=None).delete()


class Migration(migrations.Migration):
    dependencies = [("permissions_module", "0011_module_icon_choices")]
    operations = [migrations.RunPython(remove_top_level, migrations.RunPython.noop)]
