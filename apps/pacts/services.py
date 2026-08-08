from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.analysis.models import ProposedClause as AnalysisProposedClause
from apps.common.services import record_audit_event
from apps.couples.models import CoupleMember
from apps.couples.permissions import user_is_active_couple_member
from apps.pacts.models import ClauseApproval, ClauseProposal, Pact, PactClause, PactSection, PactVersion


def ensure_pact_member(*, user, couple) -> CoupleMember:
    membership = CoupleMember.objects.filter(couple=couple, user=user, status=CoupleMember.Status.ACTIVE).first()
    if membership is None or not user_is_active_couple_member(user, couple):
        raise PermissionDenied("Only active couple members can manage this pact.")
    return membership


@transaction.atomic
def create_pact_with_proposals(
    *,
    user,
    title: str = "Relationship Pact",
    proposed_clause_ids: list | None = None,
    manual_clauses: list[str] | None = None,
    request_id: str = "",
) -> Pact:
    membership = user.couple_memberships.select_related("couple").filter(status=CoupleMember.Status.ACTIVE).first()
    if membership is None:
        raise PermissionDenied("Join an active couple before creating a pact.")
    ensure_pact_member(user=user, couple=membership.couple)
    pact = Pact.objects.create(couple=membership.couple, title=title.strip()[:180] or "Relationship Pact", created_by=user)
    version = PactVersion.objects.create(pact=pact, couple=membership.couple, version=1)

    for index, proposed_clause in enumerate(resolve_analysis_clauses(membership.couple, proposed_clause_ids or []), start=1):
        ClauseProposal.objects.create(
            version=version,
            source_proposed_clause=proposed_clause,
            text=proposed_clause.clause_text,
            created_by=user,
        )
    start_index = len(proposed_clause_ids or []) + 1
    for index, clause_text in enumerate(manual_clauses or [], start=start_index):
        normalized = clause_text.strip()
        if normalized:
            ClauseProposal.objects.create(version=version, text=normalized, created_by=user)

    if not version.clause_proposals.exists():
        raise ValidationError({"clauses": "At least one clause proposal is required."})
    record_audit_event(action="pact.created", actor=user, target=pact, request_id=request_id)
    return pact


@transaction.atomic
def propose_pact_version(*, pact: Pact, user, request_id: str = "") -> PactVersion:
    pact = Pact.objects.select_for_update().get(id=pact.id)
    ensure_pact_member(user=user, couple=pact.couple)
    version = current_editable_version(pact)
    if version.status == PactVersion.Status.LIVE:
        version = create_new_version_from_live(pact=pact, user=user)
    version.status = PactVersion.Status.PROPOSED
    version.proposed_by = user
    version.proposed_at = timezone.now()
    version.save(update_fields=["status", "proposed_by", "proposed_at", "updated_at"])
    record_audit_event(action="pact_version.proposed", actor=user, target=version, request_id=request_id)
    from apps.notifications.services import notify_pact_approval_required

    notify_pact_approval_required(version=version, actor=user)
    return version


@transaction.atomic
def edit_clause_proposal(*, proposal: ClauseProposal, user, text: str, request_id: str = "") -> ClauseProposal:
    proposal = ClauseProposal.objects.select_for_update().select_related("version", "version__pact", "version__couple").get(id=proposal.id)
    ensure_pact_member(user=user, couple=proposal.version.couple)
    if proposal.version.status == PactVersion.Status.LIVE:
        raise ValidationError({"version": "Live pact versions are immutable. Create a new proposed version first."})
    normalized = text.strip()
    if not normalized:
        raise ValidationError({"text": "Clause text is required."})
    proposal.text = normalized
    proposal.revision += 1
    proposal.save(update_fields=["text", "revision", "updated_at"])
    ClauseApproval.objects.filter(proposal=proposal, invalidated_at__isnull=True).update(invalidated_at=timezone.now())
    record_audit_event(action="clause_proposal.edited", actor=user, target=proposal.version, request_id=request_id)
    return proposal


@transaction.atomic
def approve_clause_proposal(*, proposal: ClauseProposal, user, request_id: str = "") -> ClauseApproval:
    proposal = ClauseProposal.objects.select_for_update().select_related("version", "version__pact", "version__couple").get(id=proposal.id)
    membership = ensure_pact_member(user=user, couple=proposal.version.couple)
    if proposal.version.status not in {PactVersion.Status.DRAFT, PactVersion.Status.PROPOSED}:
        raise ValidationError({"version": "Only draft or proposed pact versions can be approved."})
    approval, _ = ClauseApproval.objects.get_or_create(
        proposal=proposal,
        user=user,
        proposal_revision=proposal.revision,
        defaults={
            "version": proposal.version,
            "couple": proposal.version.couple,
            "role": membership.role,
            "approved_at": timezone.now(),
        },
    )
    if approval.invalidated_at is not None:
        approval.invalidated_at = None
        approval.approved_at = timezone.now()
        approval.save(update_fields=["invalidated_at", "approved_at"])
    record_audit_event(action="clause_proposal.approved", actor=user, target=proposal.version, request_id=request_id)
    maybe_activate_version(version=proposal.version, request_id=request_id)
    return approval


@transaction.atomic
def maybe_activate_version(*, version: PactVersion, request_id: str = "") -> PactVersion:
    version = PactVersion.objects.select_for_update().select_related("pact", "couple").get(id=version.id)
    active_members = list(version.couple.members.filter(status=CoupleMember.Status.ACTIVE).order_by("role"))
    if len(active_members) < 2:
        return version
    proposals = list(version.clause_proposals.all())
    if not proposals:
        return version
    active_user_ids = {member.user_id for member in active_members}
    for proposal in proposals:
        approved_user_ids = set(
            ClauseApproval.objects.filter(
                proposal=proposal,
                proposal_revision=proposal.revision,
                invalidated_at__isnull=True,
                user_id__in=active_user_ids,
            ).values_list("user_id", flat=True)
        )
        if approved_user_ids != active_user_ids:
            return version

    activate_version(version=version)
    record_audit_event(action="pact_version.activated", actor=None, target=version, request_id=request_id)
    return version


def activate_version(*, version: PactVersion) -> None:
    now = timezone.now()
    pact = Pact.objects.select_for_update().get(id=version.pact_id)
    PactVersion.objects.filter(pact=pact, status=PactVersion.Status.LIVE).exclude(id=version.id).update(
        status=PactVersion.Status.SUPERSEDED,
        updated_at=now,
    )
    section = PactSection.objects.create(version=version, title="Shared agreements", sort_order=1)
    for index, proposal in enumerate(version.clause_proposals.order_by("created_at"), start=1):
        PactClause.objects.create(
            version=version,
            section=section,
            text=proposal.text,
            source_proposed_clause=proposal.source_proposed_clause,
            sort_order=index,
        )
    version.status = PactVersion.Status.LIVE
    version.activated_at = now
    version.save(update_fields=["status", "activated_at", "updated_at"])
    pact.live_version = version
    pact.save(update_fields=["live_version", "updated_at"])
    AnalysisProposedClause.objects.filter(clause_proposals__version=version).update(status=AnalysisProposedClause.Status.CONVERTED)
    from apps.pacts.documents import generate_and_email_live_pact_pdf

    generate_and_email_live_pact_pdf(version_id=version.id)
    from apps.notifications.services import notify_pact_activated

    notify_pact_activated(version=version)


def current_editable_version(pact: Pact) -> PactVersion:
    version = pact.versions.exclude(status__in=[PactVersion.Status.SUPERSEDED]).order_by("-version").first()
    if version is None:
        return PactVersion.objects.create(pact=pact, couple=pact.couple, version=1)
    return version


def create_new_version_from_live(*, pact: Pact, user) -> PactVersion:
    latest_version_number = pact.versions.aggregate(max_version=Max("version"))["max_version"] or 0
    live_version = pact.live_version
    new_version = PactVersion.objects.create(
        pact=pact,
        couple=pact.couple,
        version=latest_version_number + 1,
        based_on_version=live_version,
    )
    if live_version is not None:
        for clause in live_version.clauses.order_by("sort_order"):
            ClauseProposal.objects.create(
                version=new_version,
                source_proposed_clause=clause.source_proposed_clause,
                text=clause.text,
                created_by=user,
            )
    return new_version


def resolve_analysis_clauses(couple, proposed_clause_ids: list):
    clauses = list(AnalysisProposedClause.objects.filter(id__in=proposed_clause_ids, run__couple=couple))
    if len(clauses) != len(set(proposed_clause_ids)):
        raise ValidationError({"proposed_clause_ids": "One or more proposed clauses are not available for this couple."})
    return clauses
