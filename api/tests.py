from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
import uuid
import threading
from django.db import connection
from unittest.mock import patch
from .models import Merchant, Payout, LedgerEntry

# CELERY_TASK_ALWAYS_EAGER makes Celery run tasks immediately (no Redis needed)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class PayoutIdempotencyTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            available_balance_paise=10000,
            held_balance_paise=0
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=10000,
            entry_type=LedgerEntry.CREDIT,
            description="Initial deposit"
        )
        self.url = '/api/v1/payouts'
        self.payload = {
            'merchant': str(self.merchant.id),
            'amount_paise': 5000,
            'bank_account_id': 'TEST1234'
        }

    @patch('api.tasks.process_payout.delay')
    def test_idempotency_same_key_returns_same_response(self, mock_delay):
        idem_key = str(uuid.uuid4())
        
        # First request
        response1 = self.client.post(self.url, self.payload, headers={'Idempotency-Key': idem_key}, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second request with same key
        response2 = self.client.post(self.url, self.payload, headers={'Idempotency-Key': idem_key}, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK) # Should return 200, not 201
        
        # Check that only one payout was actually created
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(response1.data['id'], response2.data['id'])


class PayoutConcurrencyTest(TransactionTestCase):
    # Using TransactionTestCase because we need to test real database locks
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Concurrency Merchant",
            available_balance_paise=10000, # 100 INR
            held_balance_paise=0
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=10000,
            entry_type=LedgerEntry.CREDIT,
            description="Initial deposit"
        )
        self.url = '/api/v1/payouts'

    @patch('api.tasks.process_payout.delay')
    def test_concurrent_payouts_prevent_overdraft(self, mock_delay):
        """
        Simulate 5 simultaneous requests for 60 INR when the balance is only 100 INR.
        Exactly 1 should succeed. The others should fail cleanly.
        """
        results = []
        errors = []
        
        def make_request():
            try:
                client = APIClient()
                idem_key = str(uuid.uuid4()) 
                payload = {
                    'merchant': str(self.merchant.id),
                    'amount_paise': 6000,
                    'bank_account_id': 'TEST1234'
                }
                response = client.post(self.url, payload, HTTP_IDEMPOTENCY_KEY=idem_key, format='json')
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
            finally:
                connection.close()

        threads = []
        for _ in range(5):
            t = threading.Thread(target=make_request)
            threads.append(t)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        successes = [r for r in results if r == status.HTTP_201_CREATED]
        failures = [r for r in results if r == status.HTTP_400_BAD_REQUEST]
        
        self.assertEqual(len(successes), 1, f"Exactly one request should succeed. Results: {results}, Errors: {errors}")
        self.assertEqual(len(failures), 4, f"The other 4 requests should fail. Results: {results}, Errors: {errors}")
        
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.available_balance_paise, 4000)
        self.assertEqual(self.merchant.held_balance_paise, 6000)
