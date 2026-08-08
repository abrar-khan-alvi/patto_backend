from rest_framework import status
from django.http import Http404
from django.conf import settings
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.couples.services import user_active_membership
from apps.pacts.models import ClauseProposal, Pact
from apps.pacts.serializers import (
    ClauseApprovalSerializer,
    ClauseProposalEditSerializer,
    ClauseProposalSerializer,
    PactDocumentDownloadLinkSerializer,
    PactCreateSerializer,
    PactListSerializer,
    PactSerializer,
    PactVersionSerializer,
)
from apps.pacts.documents import (
    create_pact_document_download_token,
    generate_pact_document_for_live_version,
    pact_document_file_response,
    resolve_pact_document_download,
)
from apps.pacts.services import approve_clause_proposal, create_pact_with_proposals, edit_clause_proposal, propose_pact_version


class PactListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"results": []})
        pacts = Pact.objects.filter(couple=membership.couple).select_related("live_version").order_by("-created_at")
        return Response({"results": PactListSerializer(pacts, many=True).data})

    def post(self, request):
        serializer = PactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pact = create_pact_with_proposals(
            user=request.user,
            title=serializer.validated_data.get("title", "Relationship Pact"),
            proposed_clause_ids=serializer.validated_data.get("proposed_clause_ids", []),
            manual_clauses=serializer.validated_data.get("manual_clauses", []),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(PactSerializer(pact).data, status=status.HTTP_201_CREATED)


class PactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_pact(self, request, pact_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return None
        return get_object_or_404(
            Pact.objects.select_related("live_version").prefetch_related(
                "versions__clause_proposals__approvals",
                "versions__sections__clauses",
            ),
            id=pact_id,
            couple=membership.couple,
        )

    def get(self, request, pact_id):
        pact = self.get_pact(request, pact_id)
        if pact is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PactSerializer(pact).data)


class PactVersionProposeView(PactDetailView):
    def post(self, request, pact_id):
        pact = self.get_pact(request, pact_id)
        if pact is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        version = propose_pact_version(pact=pact, user=request.user, request_id=getattr(request, "request_id", ""))
        return Response(PactVersionSerializer(version).data)


class ClauseProposalEditView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, proposal_id):
        proposal = get_scoped_proposal_or_404(request, proposal_id)
        serializer = ClauseProposalEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposal = edit_clause_proposal(
            proposal=proposal,
            user=request.user,
            text=serializer.validated_data["text"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(ClauseProposalSerializer(proposal).data)


class ClauseProposalApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, proposal_id):
        proposal = get_scoped_proposal_or_404(request, proposal_id)
        approval = approve_clause_proposal(
            proposal=proposal,
            user=request.user,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(ClauseApprovalSerializer(approval).data, status=status.HTTP_201_CREATED)


class PactVersionPDFLinkView(PactDetailView):
    def post(self, request, pact_id, version_id):
        pact = self.get_pact(request, pact_id)
        if pact is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        version = get_object_or_404(pact.versions.all(), id=version_id)
        document = generate_pact_document_for_live_version(version=version)
        token, download_url = create_pact_document_download_token(document=document, user=request.user)
        return Response(
            PactDocumentDownloadLinkSerializer(
                {
                    "document": document,
                    "token": token,
                    "download_url": download_url,
                    "expires_in_minutes": settings.PACT_PDF_TOKEN_TTL_MINUTES,
                }
            ).data
        )


class PactPDFDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        document = resolve_pact_document_download(token=token, user=request.user)
        return pact_document_file_response(document=document)


def get_scoped_proposal_or_404(request, proposal_id):
    membership = user_active_membership(request.user)
    if membership is None:
        raise Http404
    return get_object_or_404(
        ClauseProposal.objects.select_related("version", "version__couple"),
        id=proposal_id,
        version__couple=membership.couple,
    )
