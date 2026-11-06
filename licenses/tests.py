from django.test import TestCase

# Create your tests here.


from rest_framework.test import APITestCase

from authentication.models import User
from licenses.field_schema import APPROVAL_FLOW_DOC_TYPES, config_doc_type
from licenses.models import ApprovalSettings


class UnifiedLisenziyaApprovalTests(APITestCase):
    def test_single_lisenziya_row(self):
        keys = [k for k, _ in APPROVAL_FLOW_DOC_TYPES]
        self.assertIn("xususi_lisenziya", keys)
        for gone in ("umumi_lisenziya", "istehsal"):
            self.assertNotIn(gone, keys)
        self.assertEqual(dict(APPROVAL_FLOW_DOC_TYPES)["xususi_lisenziya"], "Lisenziya")

    def test_toggle_applies_to_all_lisenziya_types(self):
        admin = User.objects.create_user("adm", "a@x.az", "pw", is_staff=True)
        self.client.force_authenticate(admin)
        r = self.client.patch("/api/licenses/approval-settings/",
                              {"doc_type": "xususi_lisenziya", "staged_approval_enabled": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        for dt in ("xususi_lisenziya", "umumi_lisenziya", "istehsal"):
            self.assertFalse(ApprovalSettings.get_for(dt).staged_approval_enabled, dt)
        self.assertEqual(config_doc_type("ixrac"), "ixrac")
        rows = self.client.get("/api/licenses/approval-settings/").json()
        self.assertEqual([x["label"] for x in rows if x["doc_type"].endswith("lisenziya")], ["Lisenziya"])


class DisabledApprovalCertificateTests(APITestCase):
    def test_active_doc_gets_certificate_when_flow_disabled(self):
        from licenses.models import LicenseCertificate, PermitDocument
        from organizations.models import Organization
        ApprovalSettings.get_for("xususi_lisenziya")
        s = ApprovalSettings.get_for("umumi_lisenziya"); s.staged_approval_enabled = False; s.save()
        org = Organization.objects.create(full_name="O", voen="1000000009")
        doc = PermitDocument.objects.create(doc_type="umumi_lisenziya", organization=org, status="aktiv")
        self.assertTrue(LicenseCertificate.objects.filter(permit_document=doc).exists())
        LicenseCertificate.objects.all().delete()
        admin = User.objects.create_user("adm2", "a2@x.az", "pw", is_staff=True)
        self.client.force_authenticate(admin)
        r = self.client.get(f"/api/licenses/permit-documents/{doc.pk}/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["certificate_id"])
