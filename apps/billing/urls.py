from django.urls import path

from apps.billing.views import CurrentEntitlementView, DevelopmentIAPVerifyView

urlpatterns = [
    path("billing/iap/development/verify/", DevelopmentIAPVerifyView.as_view(), name="billing-iap-dev-verify"),
    path("billing/entitlement/current/", CurrentEntitlementView.as_view(), name="billing-entitlement-current"),
]
