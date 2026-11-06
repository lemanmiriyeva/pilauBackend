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
