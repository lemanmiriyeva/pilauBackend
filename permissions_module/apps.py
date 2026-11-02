from django.apps import AppConfig


class PermissionsModuleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "permissions_module"
    verbose_name = "İcazələr"

    def ready(self):
        from django.db.models.signals import post_save
        from organizations.models import Organization

        from .models import grant_default_modules

        def _grant(sender, instance, created, **kw):
            if created:
                grant_default_modules(instance)

        post_save.connect(_grant, sender=Organization, dispatch_uid="org_default_modules")
