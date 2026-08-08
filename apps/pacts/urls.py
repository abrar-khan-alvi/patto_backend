from django.urls import path

from apps.pacts.views import (
    ClauseProposalApproveView,
    ClauseProposalEditView,
    PactDetailView,
    PactListCreateView,
    PactPDFDownloadView,
    PactVersionProposeView,
    PactVersionPDFLinkView,
)

urlpatterns = [
    path("pacts/", PactListCreateView.as_view(), name="pact-list-create"),
    path("pacts/<uuid:pact_id>/", PactDetailView.as_view(), name="pact-detail"),
    path("pacts/<uuid:pact_id>/propose/", PactVersionProposeView.as_view(), name="pact-version-propose"),
    path("pacts/<uuid:pact_id>/versions/<uuid:version_id>/pdf-link/", PactVersionPDFLinkView.as_view(), name="pact-version-pdf-link"),
    path("clause-proposals/<uuid:proposal_id>/", ClauseProposalEditView.as_view(), name="clause-proposal-edit"),
    path("clause-proposals/<uuid:proposal_id>/approve/", ClauseProposalApproveView.as_view(), name="clause-proposal-approve"),
    path("pact-pdfs/<str:token>/download/", PactPDFDownloadView.as_view(), name="pact-pdf-download"),
]
