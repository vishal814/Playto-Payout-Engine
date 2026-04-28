from django.urls import path
from .views import PayoutRequestView, MerchantDetailView, PayoutListView, LedgerEntryListView

urlpatterns = [
    path('payouts', PayoutRequestView.as_view(), name='payout-request'),
    path('merchants/<uuid:pk>', MerchantDetailView.as_view(), name='merchant-detail'),
    path('merchants/<uuid:merchant_id>/payouts', PayoutListView.as_view(), name='payout-list'),
    path('merchants/<uuid:merchant_id>/ledger', LedgerEntryListView.as_view(), name='ledger-list'),
]
