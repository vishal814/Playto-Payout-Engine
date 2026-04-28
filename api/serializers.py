from rest_framework import serializers
from .models import Merchant, Payout, LedgerEntry

class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ['id', 'name', 'available_balance_paise', 'held_balance_paise']

class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'amount_paise', 'entry_type', 'description', 'created_at']

class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ['id', 'merchant', 'amount_paise', 'bank_account_id', 'status', 'idempotency_key', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate_amount_paise(self, value):
        """Ensure the payout amount is a positive integer."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate_bank_account_id(self, value):
        """Ensure bank account ID is not empty or whitespace."""
        if not value or not value.strip():
            raise serializers.ValidationError("Bank account ID cannot be empty.")
        return value.strip()
