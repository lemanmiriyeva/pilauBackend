from rest_framework.test import APITestCase

from authentication.models import User

from .models import Nomenclature, Organization


class NomenclatureApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", "a@x.az", "pw", is_staff=True)
        self.org1 = Organization.objects.create(full_name="Org 1", voen="1000000001")
        self.org2 = Organization.objects.create(full_name="Org 2", voen="1000000002")
        self.user1 = User.objects.create_user("u1", "u1@x.az", "pw", organization=self.org1)
        self.base = "/api/organizations/"

    def _catalog(self):
        self.client.force_authenticate(self.admin)
        op = self.client.post(self.base + "nomenclature-catalog/operation-types/", {"name": "Satış"}, format="json").json()
        cat = self.client.post(self.base + "nomenclature-catalog/categories/", {"name": "Silah"}, format="json").json()
        sub = self.client.post(self.base + "nomenclature-catalog/subcategories/",
                               {"name": "Tapança", "category": cat["id"]}, format="json").json()
        return op, cat, sub

    def test_many_to_many_and_scoping(self):
        op, cat, sub = self._catalog()
        again = self.client.post(self.base + "nomenclature-catalog/categories/", {"name": "silah"}, format="json").json()
        self.assertEqual(again["id"], cat["id"])  # təkrar yaranmır
        payload = {"operation_type": op["id"], "category": cat["id"], "subcategory": sub["id"],
                   "name": "Makarov", "unit": "ədəd", "organization_ids": [self.org1.id, self.org2.id]}
        r = self.client.post(self.base + "nomenclatures/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.client.post(self.base + "nomenclatures/", {**payload, "name": "Glock", "organization_ids": [self.org2.id]},
                         format="json")
        self.assertEqual(Nomenclature.objects.count(), 2)
        # təşkilat 1 yalnız öz nomenklaturasını görür
        self.client.force_authenticate(self.user1)
        names = [n["name"] for n in self.client.get(f"{self.base}{self.org1.id}/nomenclature/").json()]
        self.assertEqual(names, ["Makarov"])
        self.assertEqual([n["name"] for n in self.client.get(self.base + "nomenclatures/").json()], ["Makarov"])
        # adi istifadəçi yarada bilməz
        self.assertEqual(self.client.post(self.base + "nomenclatures/", payload, format="json").status_code, 403)

    def test_subcategory_must_match_category(self):
        op, cat, sub = self._catalog()
        other = self.client.post(self.base + "nomenclature-catalog/categories/", {"name": "Texnika"}, format="json").json()
        r = self.client.post(self.base + "nomenclatures/", {"operation_type": op["id"], "category": other["id"],
                                                            "subcategory": sub["id"], "name": "X"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_assign_and_unassign(self):
        op, cat, sub = self._catalog()
        n = self.client.post(self.base + "nomenclatures/", {"operation_type": op["id"], "category": cat["id"],
                                                            "name": "Y"}, format="json").json()
        self.client.post(f"{self.base}{self.org2.id}/nomenclature/", {"nomenclature_ids": [n["id"]]}, format="json")
        self.assertEqual(self.org2.nomenclatures.count(), 1)
        self.client.delete(f"{self.base}{self.org2.id}/nomenclature/{n['id']}/")
        self.assertEqual(self.org2.nomenclatures.count(), 0)
