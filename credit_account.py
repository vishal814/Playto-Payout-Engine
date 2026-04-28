import os
import django
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import Merchant, LedgerEntry
from django.db import transaction

def credit_merchant(amount_inr, description="Manual Credit"):
    """
    Credits a merchant's account by the given INR amount.
    """
    try:
        # Convert INR to paise
        amount_paise = int(float(amount_inr) * 100)
        
        if amount_paise <= 0:
            print("Error: Amount must be greater than 0")
            return

        with transaction.atomic():
            # Get the first merchant (assuming single-merchant setup for now)
            merchant = Merchant.objects.select_for_update().first()
            
            if not merchant:
                print("Error: No merchant found in the database.")
                return
            
            print(f"Adding ₹{amount_inr} to {merchant.name}'s account...")
            
            # 1. Update available balance
            merchant.available_balance_paise += amount_paise
            merchant.save(update_fields=['available_balance_paise'])
            
            # 2. Create the Ledger Entry
            LedgerEntry.objects.create(
                merchant=merchant,
                amount_paise=amount_paise,
                entry_type=LedgerEntry.CREDIT,
                description=description
            )
            
            # 3. Verify integrity
            merchant.verify_integrity()
            
            print(f"✅ Success! New Available Balance: ₹{merchant.available_balance_paise / 100:.2f}")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    # Check if amount was passed via command line arguments
    if len(sys.argv) > 1:
        try:
            amount = float(sys.argv[1])
            desc = sys.argv[2] if len(sys.argv) > 2 else "Manual Credit"
            credit_merchant(amount, desc)
        except ValueError:
            print("Usage: python credit_account.py <amount_inr> [description]")
            print("Example: python credit_account.py 500 'Bonus payment'")
    else:
        # Interactive mode
        print("--- Credit Merchant Account ---")
        try:
            amount_input = input("Enter amount to credit (in INR): ₹")
            desc_input = input("Enter description (optional): ")
            
            amount = float(amount_input)
            desc = desc_input if desc_input.strip() else "Manual Credit"
            
            credit_merchant(amount, desc)
        except ValueError:
            print("Error: Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nCancelled.")
