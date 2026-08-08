from rest_framework.permissions import BasePermission

from apps.couples.models import Couple, CoupleMember, Entitlement, PartnerInvitation


def get_couple_from_object(obj):
    if isinstance(obj, Couple):
        return obj
    if isinstance(obj, (CoupleMember, PartnerInvitation, Entitlement)):
        return obj.couple
    return getattr(obj, "couple", None)


def get_active_membership(user, couple):
    if not getattr(user, "is_authenticated", False) or couple is None:
        return None
    return CoupleMember.objects.filter(
        user=user,
        couple=couple,
        status=CoupleMember.Status.ACTIVE,
    ).first()


def user_is_couple_member(user, couple) -> bool:
    return get_active_membership(user, couple) is not None


def user_is_active_couple_member(user, couple) -> bool:
    return (
        couple is not None
        and couple.status == Couple.Status.ACTIVE
        and get_active_membership(user, couple) is not None
    )


def user_is_partner_one(user, couple) -> bool:
    membership = get_active_membership(user, couple)
    return membership is not None and membership.role == CoupleMember.Role.PARTNER_1


def couple_has_active_entitlement(couple) -> bool:
    from apps.couples.services import has_active_entitlement

    return couple is not None and has_active_entitlement(couple)


class IsActiveCoupleMember(BasePermission):
    message = "You must be an active member of this couple."

    def has_object_permission(self, request, view, obj):
        return user_is_active_couple_member(request.user, get_couple_from_object(obj))


class IsCoupleMember(BasePermission):
    message = "You must be a member of this couple."

    def has_object_permission(self, request, view, obj):
        return user_is_couple_member(request.user, get_couple_from_object(obj))


class IsPartnerOne(BasePermission):
    message = "Only Partner 1 can perform this action."

    def has_object_permission(self, request, view, obj):
        return user_is_partner_one(request.user, get_couple_from_object(obj))


class HasActiveEntitlement(BasePermission):
    message = "This couple does not have an active entitlement."

    def has_object_permission(self, request, view, obj):
        return couple_has_active_entitlement(get_couple_from_object(obj))


class CanCreatePartnerInvitation(BasePermission):
    message = "Only Partner 1 can invite a partner."

    def has_object_permission(self, request, view, obj):
        couple = get_couple_from_object(obj)
        return couple is not None and couple.status in {Couple.Status.PENDING, Couple.Status.ACTIVE} and user_is_partner_one(request.user, couple)


class CanRevokePartnerInvitation(BasePermission):
    message = "Only Partner 1 can revoke this invitation."

    def has_object_permission(self, request, view, obj):
        couple = get_couple_from_object(obj)
        return couple is not None and couple.status in {Couple.Status.PENDING, Couple.Status.ACTIVE} and user_is_partner_one(request.user, couple)


class CanViewSharedContent(IsActiveCoupleMember):
    message = "You must be an active member of an active couple to view shared content."


class CanViewPrivateResponse(BasePermission):
    message = "You can only view private responses you own before release."

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner is not None and owner == request.user:
            return True
        return getattr(obj, "released_at", None) is not None and user_is_active_couple_member(
            request.user,
            get_couple_from_object(obj),
        )


class CanApprovePactVersion(IsActiveCoupleMember):
    message = "You must be an active couple member to approve this pact version."


class CanViewCoachConversation(BasePermission):
    message = "You cannot view this coach conversation."

    def has_object_permission(self, request, view, obj):
        scope = getattr(obj, "scope", "")
        if scope == "individual":
            return getattr(obj, "owner", None) == request.user
        return user_is_active_couple_member(request.user, get_couple_from_object(obj))
