from django.db import migrations, models


def copy_fk_to_m2m(apps, schema_editor):
    Nomenclature = apps.get_model("organizations", "Nomenclature")
    for n in Nomenclature.objects.all():
        n.operation_types.add(n.operation_type_id)


def copy_m2m_to_fk(apps, schema_editor):
    Nomenclature = apps.get_model("organizations", "Nomenclature")
    for n in Nomenclature.objects.all():
        first = n.operation_types.first()
        if first:
            n.operation_type_id = first.id
            n.save(update_fields=["operation_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0013_partner_company"),
    ]

    operations = [
        migrations.AddField(
            model_name="nomenclature",
            name="operation_types",
            field=models.ManyToManyField(related_name="nomenclatures_m2m", to="organizations.nomenclatureoperationtype"),
        ),
        migrations.RunPython(copy_fk_to_m2m, copy_m2m_to_fk),
        migrations.RemoveField(model_name="nomenclature", name="operation_type"),
        migrations.AlterField(
            model_name="nomenclature",
            name="operation_types",
            field=models.ManyToManyField(related_name="nomenclatures", to="organizations.nomenclatureoperationtype"),
        ),
    ]
