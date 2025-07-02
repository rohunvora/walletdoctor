# WAL-317a: Bigger Pages & Batch TX Fetch - COMPLETED ✅

## Summary
Implemented high-performance transaction fetching using:
1. **1000 transactions per page** (instead of 100)
2. **Batch transaction fetching** with getParsedTransactionsBatch
3. **Page count validation** (fail fast if > 20 pages)

## Key Changes

### Part A - Sanity Check
1. **Page Count Logging**: Added logging of total pages fetched
2. **Page Limit Validation**: Fails fast if pages > 20 with clear error message
3. **Error Message**: `"ERROR: Too many pages (X > 20) with SIGNATURE_PAGE_LIMIT=1000"`

### Part B - Batch TX Fetch
1. **Two-phase fetching**:
   - Phase 1: `_fetch_swap_signatures()` - Fetches signatures only
   - Phase 2: `_fetch_transactions_batch()` - Batch fetches full transactions
   
2. **Batch Processing**:
   - Groups signatures into chunks of 100 (TX_BATCH_SIZE)
   - Uses getParsedTransactionsBatch endpoint
   - Filters for SWAP transactions (events.swap or tokenTransfers)
   
3. **429 Handling**:
   - Exponential backoff: 5s → 10s → 20s
   - Max 3 retries per batch
   - Uses same semaphore/rate limiter

### Constants
```python
SIGNATURE_PAGE_LIMIT = 1000  # Bigger pages for signature fetch
TX_BATCH_SIZE = 100  # Batch size for getParsedTransactionsBatch
```

### Performance Flow
```python
# Step 1: Fetch signatures (fast, 1000 per page)
signatures = await self._fetch_swap_signatures(wallet_address)

# Step 2: Batch fetch transactions (efficient, 100 per batch)
transactions = await self._fetch_transactions_batch(signatures)
```

## Acceptance Criteria Met

✅ **Part A - Sanity Check**
- Logs page count when SIGNATURE_PAGE_LIMIT=1000
- Fails fast if pages > 20

✅ **Part B - Batch TX Fetch**
- Collects signatures, then batch fetches transactions
- Groups into chunks of 100
- Respects semaphore/429 logic
- Created `tests/test_batch_fetch.py` for unit testing

## Testing

### Performance Test
```bash
HELIUS_KEY=<your-key> python tests/test_perf.py
```
Target: <20s for 5,478-trade wallet

### Unit Test
```bash
python tests/test_batch_fetch.py
```
Verifies:
- Page count ≤ 20 validation
- Batch endpoint returns transactions
- 429 handling works correctly 