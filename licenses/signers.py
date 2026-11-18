"""Sənədi imzalaya biləcək şəxslər - YALNIZ rəhbərlik (nazir, nazir müavinləri).

Rəhbərlik = istifadəçi formasında 'Rəhbərlik' kimi işarələnmiş (User.rehber_kadr) və ya
vəzifəsində 'nazir' (Nazir, Nazir müavini) olan aktiv istifadəçilər. Həm Lisenziya yarat formasındakı
"İmzalayan şəxs" seçimi, həm də Təsdiq axını ekranı eyni siyahını istifadə edir."""
from django.db.models import Q

from authentication.models import User


def signer_candidates_qs():
    return (
        User.objects.filter(Q(rehber_kadr=True) | Q(position__name__icontains="nazir"), is_active=True)
        .select_related("department", "position")
        .order_by("first_name", "last_name")
    )


def serialize_signer(u):
    return {
        "id": u.id,
        "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
        "department": u.department.name if u.department else "",
        "position": u.position.name if u.position else "",
    }


def signer_candidates():
    return [serialize_signer(u) for u in signer_candidates_qs()]
