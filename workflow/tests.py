from django.test import TestCase

# Create your tests here.


from rest_framework.test import APITestCase

from authentication.models import User


class SignerLeadershipTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", "a@x.az", "pw", is_staff=True, is_superuser=True)
        self.leader = User.objects.create_user("nazir", "n@x.az", "pw", first_name="Ad", last_name="Soyad",
                                               rehber_kadr=True)
        self.other = User.objects.create_user("oper", "o@x.az", "pw", is_staff=True)
        self.client.force_authenticate(self.admin)

    def _put(self, signer):
        return self.client.put("/api/workflow/workflow-config/", {
            "doc_type": "xususi_lisenziya", "stage1_mode": "qurum", "stage2_enabled": True,
            "signer_user": signer,
        }, format="json")

    def test_only_leadership_can_be_signer(self):
        self.assertEqual(self._put(self.other.id).status_code, 400)
        r = self._put(self.leader.id)
        self.assertEqual(r.status_code, 200, r.content)

    def test_candidates_listed_and_pdf_has_signer(self):
        rows = self.client.get("/api/workflow/workflow-config/").json()
        lis = [x for x in rows if x["doc_type"] == "xususi_lisenziya"][0]
        self.assertEqual([u["id"] for u in lis["signer_candidates"]], [self.leader.id])

        from licenses.certificate_pdf import build_certificate_pdf
        from licenses.models import LicenseCertificate, PermitDocument
        from organizations.models import Organization
        self._put(self.leader.id)
        org = Organization.objects.create(full_name="PdfOrg", voen="1000000055")
        doc = PermitDocument.objects.create(doc_type="xususi_lisenziya", organization=org, status="aktiv",
                                            applicant_name="PdfOrg")
        cert = LicenseCertificate.objects.create(permit_document=doc, form_data={})
        self.assertTrue(build_certificate_pdf(cert).startswith(b"%PDF"))


class SignerByPositionTests(APITestCase):
    def test_deputy_minister_by_position_is_candidate_and_root_not_shown(self):
        from organizations.models import Organization, OrganizationDepartment, OrganizationPosition
        from licenses.certificate_pdf import _signer_info
        from licenses.models import LicenseCertificate, PermitDocument
        org = Organization.objects.create(full_name="MSN", voen="1000000066")
        dept = OrganizationDepartment.objects.create(organization=org, name="Rəhbərlik")
        pos = OrganizationPosition.objects.create(organization=org, department=dept, name="Nazir müavini")
        deputy = User.objects.create_user("muavin", "m@x.az", "pw", first_name="Ə", last_name="M", position=pos)
        root = User.objects.create_user("root", "r@x.az", "pw", is_staff=True, is_superuser=True)
        self.client.force_authenticate(root)
        rows = self.client.get("/api/workflow/workflow-config/").json()
        lis = [x for x in rows if x["doc_type"] == "xususi_lisenziya"][0]
        self.assertIn(deputy.id, [u["id"] for u in lis["signer_candidates"]])
        self.assertNotIn(root.id, [u["id"] for u in lis["signer_candidates"]])

        doc = PermitDocument.objects.create(doc_type="xususi_lisenziya", organization=org, status="aktiv",
                                            stage2_approved_by=root)
        cert = LicenseCertificate.objects.create(permit_document=doc, form_data={}, completed_by=root)
        self.assertEqual(_signer_info(doc, cert), ("", ""))  # 'root' görünmür
        r = self.client.put("/api/workflow/workflow-config/", {
            "doc_type": "xususi_lisenziya", "stage1_mode": "qurum", "signer_user": deputy.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_signer_info(doc, cert), ("Ə M", "Nazir müavini"))
