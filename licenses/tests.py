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


class IssueDateTests(APITestCase):
    def test_issue_date_set_when_active(self):
        from licenses.models import PermitDocument
        from organizations.models import Organization
        org = Organization.objects.create(full_name="O2", voen="1000000010")
        d = PermitDocument.objects.create(doc_type="xususi_lisenziya", organization=org, status="gozleyir")
        self.assertIsNone(d.issue_date)
        d.status = "aktiv"; d.save()
        d.refresh_from_db()
        self.assertIsNotNone(d.issue_date)


class LegacyImportModeTests(APITestCase):
    def _create(self):
        from organizations.models import Organization
        org = Organization.objects.create(full_name="Legacy Org", voen="1000000077")
        admin = User.objects.create_user("legacy", "l@x.az", "pw", is_staff=True, organization=org)
        self.client.force_authenticate(admin)
        return self.client.post("/api/licenses/permit-documents/", {
            "doc_type": "xususi_lisenziya", "organization": org.id, "submission_mode": "file",
            "applicant_name": "Legacy Org", "voen": "1000000077",
            "form_data": {"mehsulun_novu": "X", "lisenziya_tipi": "t", "fealiyyet_sahesi": "herbi_texnika",
                          "istinad_maddesi_bendleri": ["a"]},
        }, format="json")

    def test_active_without_documents_in_legacy_mode(self):
        from django.test import override_settings
        with override_settings(LEGACY_LICENSE_IMPORT_MODE=True):
            r = self._create()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["status"], "aktiv")
        self.assertTrue(r.json()["certificate_id"])
        self.assertTrue(r.json()["issue_date"])

    def test_draft_when_mode_off(self):
        from django.test import override_settings
        with override_settings(LEGACY_LICENSE_IMPORT_MODE=False):
            r = self._create()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["status"], "qaralama")


class SignerSelectionTests(TestCase):
    def setUp(self):
        from authentication.models import User
        from rest_framework.test import APIClient
        self.admin = User.objects.create_user(username="adm", email="a1@x.az", password="x", is_staff=True, is_superuser=True)
        self.lead = User.objects.create_user(username="lead", email="a2@x.az", password="x", first_name="Hidayət", last_name="Əzimov", rehber_kadr=True)
        self.other = User.objects.create_user(username="oth", email="a3@x.az", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_candidates_endpoint_only_leadership(self):
        r = self.client.get("/api/licenses/signer-candidates/")
        self.assertEqual(r.status_code, 200)
        ids = [x["id"] for x in r.json()]
        self.assertIn(self.lead.id, ids)
        self.assertNotIn(self.other.id, ids)

    def test_signer_validation(self):
        from licenses.serializers import PermitDocumentCreateSerializer
        f = PermitDocumentCreateSerializer().fields["signer"]
        self.assertEqual(f.run_validation(self.lead.id), self.lead)
        with self.assertRaises(Exception):
            PermitDocumentCreateSerializer().validate_signer(self.other)
