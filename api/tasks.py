import random
import time
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from .models import Payout, Merchant, LedgerEntry

class BankTimeoutException(Exception):
    pass

@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        return

    # Strict State Machine: Must be PENDING or PROCESSING (if it's a retry)
    if payout.status not in [Payout.PENDING, Payout.PROCESSING]:
        return

    payout.status = Payout.PROCESSING
    payout.save(update_fields=['status'])

    # Simulate banking network (70% success, 20% fail, 10% hang)
    outcome = random.choices(
        ['SUCCESS', 'FAIL', 'HANG'], 
        weights=[70, 20, 10], 
        k=1
    )[0]

    if outcome == 'HANG':
        try:
            # Trigger exponential backoff manually
            self.retry(exc=BankTimeoutException("Bank network timed out."), countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            # If we've hit max retries, treat it as a FAIL outcome
            outcome = 'FAIL'

    if outcome == 'SUCCESS':
        with transaction.atomic():
            merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
            payout = Payout.objects.select_for_update().get(id=payout_id)
            
            # State machine guard
            if payout.status != Payout.PROCESSING:
                return
            
            # Money officially leaves the system
            merchant.held_balance_paise -= payout.amount_paise
            merchant.save(update_fields=['held_balance_paise'])
            
            # Record the permanent debit
            LedgerEntry.objects.create(
                merchant=merchant,
                amount_paise=payout.amount_paise,
                entry_type=LedgerEntry.DEBIT,
                description=f"Payout {payout.id} completed",
                payout=payout
            )
            
            payout.status = Payout.COMPLETED
            payout.save(update_fields=['status'])

    elif outcome == 'FAIL':
        with transaction.atomic():
            merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
            payout = Payout.objects.select_for_update().get(id=payout_id)
            
            # State machine guard
            if payout.status != Payout.PROCESSING:
                return
            
            # Move funds from held back to available
            merchant.held_balance_paise -= payout.amount_paise
            merchant.available_balance_paise += payout.amount_paise
            merchant.save(update_fields=['held_balance_paise', 'available_balance_paise'])
            
            payout.status = Payout.FAILED
            payout.save(update_fields=['status'])
