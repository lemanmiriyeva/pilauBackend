from rest_framework import serializers

from .models import AuthorizedPerson, Organization, OrganizationDepartment, OrganizationPosition


class AuthorizedPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedPerson
        fields = [
            "id", "organization", "person_type", "full_name",
            "fin_kod", "department", "position", "email", "phone",
        ]
        extra_kwargs = {"organization": {"required": False}}


class OrganizationDepartmentSerializer(serializers.ModelSerializer):
    """İnzibatçı Paneli -> Departamentlər və Vəzifələr səhifəsi üçün (bax
    organizations/views.py -> OrganizationDepartmentViewSet). unique_together=(organization,
    parent, name) modeldə təyin olunduğu üçün DRF eyni departament daxilində təkrar ad üçün
    avtomatik xəta verir (fərqli ana-departamentlərdə/təşkilatlarda eyni ad təkrarlana bilər).

    QEYD: 'parent' unique_together-də iştirak etdiyi üçün DRF onu avtomatik MƏCBURİ sahəyə
    çevirir (modeldə null=True/blank=True olsa belə - bu, DRF-in məlum bir davranışıdır: bir
    UniqueTogetherValidator-a daxil olan bütün sahələr defolt required olur). Aşağıda əl ilə
    'required=False, allow_null=True' göstərərək bunu ləğv edirik - əks halda ali (top-level)
    departament yaratmaq mümkün olmurdu ("Bu sahə tələb edilir" xətası)."""
    organization_name = serializers.CharField(source="organization.full_name", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, default=None)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=OrganizationDepartment.objects.all(), required=False, allow_null=True, default=None,
    )
    head_name = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationDepartment
        fields = [
            "id", "organization", "organization_name",
            "parent", "parent_name", "head", "head_name", "name",
        ]

    def get_head_name(self, obj):
        if not obj.head_id:
            return None
        return f"{obj.head.first_name} {obj.head.last_name}".strip() or obj.head.username

    def validate(self, attrs):
        parent = attrs.get("parent") if "parent" in attrs else getattr(self.instance, "parent", None)
        organization = attrs.get("organization") or getattr(self.instance, "organization", None)
        if parent and organization and parent.organization_id != organization.id:
            raise serializers.ValidationError(
                {"parent": "Ana departament eyni təşkilata aid olmalıdır."}
            )
        if self.instance and parent_id_equals_self(self.instance, parent):
            raise serializers.ValidationError({"parent": "Departament öz-özünün ana departamenti ola bilməz."})
        return attrs


def parent_id_equals_self(instance, parent):
    return bool(parent) and parent.id == instance.id


class OrganizationPositionSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.full_name",
        read_only=True
    )

    department_name = serializers.CharField(
        source="department.name",
        read_only=True
    )

    class Meta:
        model = OrganizationPosition
        fields = [
            "id",
            "organization",
            "organization_name",
            "department",
            "department_name",
            "name",
        ]


class OrganizationListSerializer(serializers.ModelSerializer):
    """Sadələşdirilmiş - dropdown/ağac görünüşü üçün (Image 2-dəki 'Təşkilatı seçin')."""
    children = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "full_name", "code", "children"]

    def get_children(self, obj):
        return OrganizationListSerializer(obj.children.all(), many=True).data


class OrganizationSummarySerializer(serializers.ModelSerializer):
    """İnzibatçı Paneli -> İcazələrin idarə edilməsi siyahısı üçün (Image 4)."""
    user_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Organization
        fields = ["id", "full_name", "code", "voen", "parent", "user_count", "is_active"]


class OrganizationTableSerializer(serializers.ModelSerializer):
    authorized_person_count = serializers.IntegerField(read_only=True)
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "full_name",
            "code",
            "voen",
            "is_active",
            "authorized_person_count",
            "user_count",
            "created_at",
        ]


class OrganizationReportCardSerializer(serializers.ModelSerializer):
    """Hesabatlar -> Təşkilatlar səhifəsindəki kart siyahısı üçün - hər təşkilatın YARATDIĞI
    ÜMUMİ lisenziya sənədi sayı ilə birlikdə (bax OrganizationReportCardsView)."""
    license_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Organization
        fields = ["id", "full_name", "code", "voen", "is_active", "license_count"]


class OrganizationDetailSerializer(serializers.ModelSerializer):
    authorized_persons = AuthorizedPersonSerializer(many=True, required=False)

    class Meta:
        model = Organization
        fields = [
            "id", "code", "full_name", "voen", "state_reg_number",
            "email", "phone", "address",
            "parent", "notes", "authorized_persons", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        persons_data = validated_data.pop("authorized_persons", [])
        organization = Organization.objects.create(**validated_data)
        for person_data in persons_data:
            AuthorizedPerson.objects.create(organization=organization, **person_data)
        return organization

    def update(self, instance, validated_data):
        persons_data = validated_data.pop("authorized_persons", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if persons_data is not None:
            instance.authorized_persons.all().delete()
            for person_data in persons_data:
                AuthorizedPerson.objects.create(organization=instance, **person_data)
        return instance