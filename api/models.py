import uuid
from django.db import models
from django.db.models import Sum
from django.core.validators import MinValueValidator

class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    available_balance_paise = models.BigIntegerField(default=0)
    held_balance_paise = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Available: {self.available_balance_paise}, Held: {self.held_balance_paise})"

    def verify_integrity(self):
        """
        Calculates the true balance from the LedgerEntry table and asserts it 
        perfectly matches the cached (available + held) balance.
        """
        aggregates = self.ledger_entries.aggregate(
            total_credits=Sum('amount_paise', filter=models.Q(entry_type=LedgerEntry.CREDIT)),
            total_debits=Sum('amount_paise', filter=models.Q(entry_type=LedgerEntry.DEBIT))
        )
        
        total_credits = aggregates['total_credits'] or 0
        total_debits = aggregates['total_debits'] or 0
        true_balance = total_credits - total_debits
        
        cached_balance = self.available_balance_paise + self.held_balance_paise
        
        if true_balance != cached_balance:
            raise ValueError(
                f"Ledger Integrity Error for Merchant {self.id}: "
                f"True Balance ({true_balance}) != Cached Balance ({cached_balance})"
            )
        return True


class LedgerEntry(models.Model):
    CREDIT = 'CREDIT'
    DEBIT = 'DEBIT'
    ENTRY_TYPE_CHOICES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='ledger_entries')
    amount_paise = models.BigIntegerField(validators=[MinValueValidator(1)])
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    
    # Optional link to the payout if this entry was caused by a payout
    payout = models.ForeignKey('Payout', on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} of {self.amount_paise} paise for {self.merchant.name}"


class Payout(models.Model):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='payouts')
    amount_paise = models.BigIntegerField(validators=[MinValueValidator(1)])
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    
    idempotency_key = models.UUIDField(db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'idempotency_key'], 
                name='unique_merchant_idempotency_key'
            )
        ]

    def __str__(self):
        return f"Payout {self.id} - {self.status} ({self.amount_paise} paise)"
