# Architectural Decisions: Playto Payout Engine

This document answers the 5 core deliverables required by the Playto Engineering challenge.

---

### 1. The Ledger
**Paste your balance calculation query. Why did you model credits and debits this way?**

```python
aggregates = self.ledger_entries.aggregate(
    total_credits=Sum('amount_paise', filter=models.Q(entry_type=LedgerEntry.CREDIT)),
    total_debits=Sum('amount_paise', filter=models.Q(entry_type=LedgerEntry.DEBIT))
)
total_credits = aggregates['total_credits'] or 0
total_debits = aggregates['total_debits'] or 0
true_balance = total_credits - total_debits

cached_balance = self.available_balance_paise + self.held_balance_paise

if true_balance != cached_balance:
    raise ValueError("Ledger Integrity Error")
```

**Why modeled this way:**
We use a **Two-Pocket Strategy** (`available` and `held` balances) combined with an immutable Ledger. 
When a payout is requested, funds move from `available` to `held`. *No ledger entry is written yet* because the money hasn't officially left the ecosystem. If the bank succeeds, we deduct `held` to 0 and write a permanent `DEBIT` LedgerEntry. If the bank fails, we simply slide the funds from `held` back to `available` silently. This model prevents the database from bloating with fake "reversal" or "refund" credit entries for transactions that never actually settled.

---

### 2. The Lock
**Paste the exact code that prevents two concurrent payouts from overdrawing a balance. Explain what database primitive it relies on.**

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    
    if merchant.available_balance_paise < amount_paise:
        return Response({"error": "Insufficient funds"}, status=400)
        
    merchant.available_balance_paise -= amount_paise
    merchant.held_balance_paise += amount_paise
    merchant.save(update_fields=['available_balance_paise', 'held_balance_paise'])
```

**What primitive it relies on:**
It relies on PostgreSQL's `SELECT ... FOR UPDATE` which applies a strict **row-level exclusive lock**. If a merchant fires two simultaneous requests, Request A acquires the lock first. Request B hits `select_for_update()` and is physically forced by the database to wait. Once Request A finishes deducting the balance and commits, the lock is released. Request B is unpaused, reads the *freshly updated* balance, sees it is too low, and rejects cleanly.

---

### 3. The Idempotency
**How does your system know it has seen a key before? What happens if the first request is in flight when the second arrives?**

The system knows it has seen a key because we defined a strict database-level constraint in the model:
`models.UniqueConstraint(fields=['merchant', 'idempotency_key'])`

If Request A is "in flight" (it acquired the row lock and is currently doing math), and Request B arrives with the exact same idempotency key, here is what happens:
1. Request B waits for Request A to release the merchant lock.
2. Request A completes and saves the Payout to the database.
3. Request B is unpaused. It attempts to `Payout.objects.create(...)` with the same key.
4. The PostgreSQL database rejects Request B with an `IntegrityError` because the `UniqueConstraint` is violated.
5. Our view catches this `IntegrityError`, fetches the Payout that Request A just created, and safely returns it to the user without duplicating the transaction.

---

### 4. The State Machine
**Where in the code is failed-to-completed blocked? Show the check.**

In our background Celery worker (`api/tasks.py`), we enforce a strict state machine guard immediately after acquiring the row lock, right before applying the final bank outcome:

```python
elif outcome == 'SUCCESS':
    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().get(id=payout.merchant_id)
        payout = Payout.objects.select_for_update().get(id=payout_id)
        
        # State machine guard: Block FAILED (or completed) from moving to COMPLETED
        if payout.status != Payout.PROCESSING:
            return
```
This check ensures that if a Celery retry somehow fires after a payout was already marked `FAILED` or `COMPLETED`, it will silently abort instead of illegally altering the state or moving money twice.

---

### 5. The AI Audit
**One specific example where AI wrote subtly wrong code (bad locking, wrong aggregation, race condition). Paste what it gave you, what you caught, and what you replaced it with.**

**What it gave me:**
While writing the Celery failure logic, the AI attempted to create a "refund" receipt when a bank transfer failed:
```python
# AI's buggy code for a failed payout
merchant.held_balance_paise -= payout.amount_paise
merchant.available_balance_paise += payout.amount_paise

LedgerEntry.objects.create( # BAD!
    merchant=merchant,
    amount_paise=payout.amount_paise,
    entry_type=LedgerEntry.CREDIT,
)
```

**What I caught:**
I wrote a custom script (`simulate_fail.py`) that ran the `verify_integrity()` math immediately after a failed payout, and it crashed with a `Ledger Integrity Error`. The AI fundamentally misunderstood the "Two-Pocket Strategy". Because the original payout request only moved money from `Available` to `Held`, a `DEBIT` LedgerEntry was never actually created yet. By adding a `CREDIT` LedgerEntry upon failure, the AI effectively spawned "free money" out of thin air, causing the true ledger balance to jump higher than the cached balances. 

**What I replaced it with:**
I deleted the `LedgerEntry.objects.create()` block entirely from the `FAIL` outcome in `api/tasks.py`. The funds simply slide from `held_balance_paise` back to `available_balance_paise` with no ledger footprint, keeping the `Credits - Debits == Available + Held` invariant perfectly balanced.
