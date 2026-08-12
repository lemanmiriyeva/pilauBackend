from rest_framework import serializers

from .models import AuthorizedPerson, Organization


class AuthorizedPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedPerson
        fields = ["id", "organization", "full_name", "fin_kod", "department", "position", "email", "phone"]
        extra_kwargs = {"organization": {"required": False}}


class OrganizationListSerializer(serializers.ModelSerializer):
    """Sadələşdirilmiş - dropdown/ağac görünüşü üçün (Image 2-dəki 'Təşkilatı seçin')."""
    children = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "full_name", "children"]

    def get_children(self, obj):
        return OrganizationListSerializer(obj.children.all(), many=True).data


class OrganizationDetailSerializer(serializers.ModelSerializer):
    authorized_persons = AuthorizedPersonSerializer(many=True, required=False)

    class Meta:
        model = Organization
        fields = [
            "id", "full_name", "voen", "state_reg_number",
            "email", "phone", "address",
            "parent", "notes", "authorized_persons",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        persons_data = validated_data.pop("authorized_persons", [])
        organization = Organization.objects.create(**validated_data)
        for person_data in persons_data:
            AuthorizedPerson.objects.create(organization=organization, **person_data)
        return organization
