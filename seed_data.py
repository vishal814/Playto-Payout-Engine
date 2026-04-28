import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import Merchant, LedgerEntry
from django.db import transaction

def seed():
    with transaction.atomic():
        # Clear existing
        LedgerEntry.objects.all().delete()
        from api.models import Payout
        Payout.objects.all().delete()
        Merchant.objects.all().delete()
        # Create a test merchant
        merchant = Merchant.objects.create(
            name="Acme Design Studio",
            available_balance_paise=1000000, # 10,000 INR
            held_balance_paise=0
        )
        
        # Create initial credit history
        LedgerEntry.objects.create(
            merchant=merchant,
            amount_paise=1000000,
            entry_type=LedgerEntry.CREDIT,
            description="Initial Customer Payment from USA"
        )
        
        print(f" Seeded Merchant: {merchant.name}")
        print(f" MERCHANT_ID: {merchant.id}")
        print("Please copy this ID into frontend/src/App.tsx")

if __name__ == "__main__":
    seed()
