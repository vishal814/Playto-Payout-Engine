from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import timedelta
from .models import Merchant, Payout, LedgerEntry
from .serializers import PayoutSerializer, MerchantSerializer
from .tasks import process_payout

class PayoutRequestView(APIView):
    def post(self, request):
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response({'error': 'Idempotency-Key header is required'}, status=status.HTTP_400_BAD_REQUEST)

        merchant_id = request.data.get('merchant')
        amount_paise = request.data.get('amount_paise')
        bank_account_id = request.data.get('bank_account_id')

        if not all([merchant_id, amount_paise, bank_account_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_paise = int(amount_paise)
            if amount_paise <= 0:
                return Response({'error': 'Amount must be positive'}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({'error': 'Invalid amount format'}, status=status.HTTP_400_BAD_REQUEST)

        assert amount_paise > 0, "amount_paise must be positive after validation"

        # 1. Idempotency Check (Dirty Read to avoid unnecessary locks)
        existing_payout = Payout.objects.filter(merchant_id=merchant_id, idempotency_key=idempotency_key).first()
        if existing_payout:
            # Check if older than 24 hours
            if timezone.now() - existing_payout.created_at > timedelta(hours=24):
                return Response({'error': 'Idempotency key expired'}, status=status.HTTP_400_BAD_REQUEST)
            return Response(PayoutSerializer(existing_payout).data, status=status.HTTP_200_OK)

        # 2. Concurrency Control with Row-Level Lock
        try:
            with transaction.atomic():
                # select_for_update prevents other simultaneous requests from modifying this merchant
                merchant = Merchant.objects.select_for_update().get(id=merchant_id)
                
                # Verify integrity just to be safe (optional, can be disabled in extreme high throughput, but requested by spec)
                merchant.verify_integrity()
                
                # Check balance
                if merchant.available_balance_paise < amount_paise:
                    return Response({'error': 'Insufficient funds'}, status=status.HTTP_400_BAD_REQUEST)
                
                # Move funds from Available to Held
                merchant.available_balance_paise -= amount_paise
                merchant.held_balance_paise += amount_paise
                merchant.save(update_fields=['available_balance_paise', 'held_balance_paise'])

                # Create Payout
                payout = Payout.objects.create(
                    merchant=merchant,
                    amount_paise=amount_paise,
                    bank_account_id=bank_account_id,
                    status=Payout.PENDING,
                    idempotency_key=idempotency_key
                )
                
                # Trigger Celery task ONLY after the database transaction commits successfully
                transaction.on_commit(lambda: process_payout.delay(payout.id))
                
                serializer = PayoutSerializer(payout)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            # Catches verify_integrity errors
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except IntegrityError:
            # Fallback for exact simultaneous request race condition bypassing the dirty read
            existing_payout = Payout.objects.get(merchant_id=merchant_id, idempotency_key=idempotency_key)
            return Response(PayoutSerializer(existing_payout).data, status=status.HTTP_200_OK)


class MerchantDetailView(APIView):
    def get(self, request, pk):
        try:
            merchant = Merchant.objects.get(id=pk)
            merchant.verify_integrity()
            return Response(MerchantSerializer(merchant).data)
        except Merchant.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

class PayoutListView(APIView):
    def get(self, request, merchant_id):
        payouts = Payout.objects.filter(merchant_id=merchant_id).order_by('-created_at')
        return Response(PayoutSerializer(payouts, many=True).data)

from .serializers import LedgerEntrySerializer

class LedgerEntryListView(APIView):
    def get(self, request, merchant_id):
        entries = LedgerEntry.objects.filter(merchant_id=merchant_id).order_by('-created_at')
        return Response(LedgerEntrySerializer(entries, many=True).data)
