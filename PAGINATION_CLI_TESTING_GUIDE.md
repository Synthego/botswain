# Pagination CLI Testing Guide

## Location

**CLI Script:** `./botswain-cli.py`

## Prerequisites

1. **Start the Botswain API server:**
   ```bash
   python manage.py runserver --settings=botswain.settings.barb_prod_replica 8002
   ```

2. **Or use the default settings:**
   ```bash
   python manage.py runserver 8002
   ```

## Testing Pagination

### Page-Based Pagination (User-Friendly)

**Page 1 (default):**
```bash
./botswain-cli.py "Show synthesizers"
```

**Page 2 with 25 results per page:**
```bash
./botswain-cli.py "Show synthesizers" --page 2 --page-size 25
```

**Page 3 with 10 results per page:**
```bash
./botswain-cli.py "Show synthesizers" --page 3 --page-size 10
```

### Offset-Based Pagination (Developer-Friendly)

**Skip first 50 results, show 25:**
```bash
./botswain-cli.py "Show synthesizers" --offset 50 --limit 25
```

**Skip first 100 results, show 10:**
```bash
./botswain-cli.py "Show synthesizers" --offset 100 --limit 10
```

## Example Output

When you run a paginated query, you'll see output like this:

```
📊 Query Results
============================================================

Found 225 synthesizers (showing results 26-50)

────────────────────────────────────────────────────────────
Entity:         synthesizer
Results Count:  25
Execution Time: 45ms
Cache:          ✓ Cached result
────────────────────────────────────────────────────────────
Pagination:
  Page:           2 of 9+
  Results:        26-50
  Total:          225+
  Previous:       --page 1
  Next:           --page 3
```

## Testing Different Scenarios

### Test 1: Navigate Through Pages

```bash
# Page 1
./botswain-cli.py "Show synthesizers" --page 1 --page-size 20

# Page 2
./botswain-cli.py "Show synthesizers" --page 2 --page-size 20

# Page 3
./botswain-cli.py "Show synthesizers" --page 3 --page-size 20
```

**Expected:**
- Page 1: has_previous=false, has_next=true
- Page 2: has_previous=true, has_next=true (if more results)
- Navigation hints show correct page numbers

### Test 2: Offset vs Page Equivalence

These should return the same results:

```bash
# Page-based: page 3, page_size 20 = offset 40
./botswain-cli.py "Show synthesizers" --page 3 --page-size 20

# Offset-based: offset 40, limit 20
./botswain-cli.py "Show synthesizers" --offset 40 --limit 20
```

**Expected:** Same results and pagination metadata

### Test 3: Last Page (Exact Total)

```bash
# Request a page beyond the data
./botswain-cli.py "Show synthesizers" --page 10 --page-size 50
```

**Expected:**
- If it's the last page: `Total: 225` (exact number, no `+`)
- No "Next" navigation hint

### Test 4: Different Page Sizes

```bash
# Small pages
./botswain-cli.py "Show synthesizers" --page-size 5

# Medium pages
./botswain-cli.py "Show synthesizers" --page-size 50

# Large pages
./botswain-cli.py "Show synthesizers" --page-size 100
```

### Test 5: With Other Options

**With JSON format:**
```bash
./botswain-cli.py "Show synthesizers" --page 2 --format json
```

**With debug mode:**
```bash
./botswain-cli.py "Show synthesizers" --page 2 --debug
```

**With raw output:**
```bash
./botswain-cli.py "Show synthesizers" --page 2 --raw
```

**Bypass cache:**
```bash
./botswain-cli.py "Show synthesizers" --page 2 --no-cache
```

## CLI Help

View all pagination options:
```bash
./botswain-cli.py --help
```

## Pagination Metadata in Output

The CLI displays:
- **Page:** Current page number and total pages (estimated or exact)
- **Results:** Range of results shown (e.g., "26-50")
- **Total:** Total results available (estimated with `+` or exact)
- **Previous:** Command to navigate to previous page (if applicable)
- **Next:** Command to navigate to next page (if applicable)

## Testing with Different Entities

Try pagination with different data sources:

**Synthesizers:**
```bash
./botswain-cli.py "Show synthesizers" --page 2
```

**Instruments:**
```bash
./botswain-cli.py "Show instruments" --page 2
```

**Workflows:**
```bash
./botswain-cli.py "Show workflows" --page 2
```

**Orders (requires Buckaneer database):**
```bash
./botswain-cli.py "Show orders" --page 2
```

## Validation Testing

### Valid Parameters

All of these should work:
```bash
./botswain-cli.py "Show synthesizers" --page 1
./botswain-cli.py "Show synthesizers" --page-size 10
./botswain-cli.py "Show synthesizers" --offset 0
./botswain-cli.py "Show synthesizers" --limit 1000
```

### Invalid Parameters (Expected to Fail)

These should return validation errors:

**Page 0 (pages are 1-indexed):**
```bash
./botswain-cli.py "Show synthesizers" --page 0
# Expected: 400 Bad Request - page must be >= 1
```

**Negative offset:**
```bash
./botswain-cli.py "Show synthesizers" --offset -10
# Expected: 400 Bad Request - offset must be >= 0
```

**Excessive page size:**
```bash
./botswain-cli.py "Show synthesizers" --page-size 5000
# Expected: 400 Bad Request - page_size max is 1000
```

**Excessive limit:**
```bash
./botswain-cli.py "Show synthesizers" --limit 5000
# Expected: 400 Bad Request - limit max is 1000
```

## Direct API Testing (Alternative)

You can also test the API directly with curl:

```bash
# Page-based
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show synthesizers",
    "page": 2,
    "page_size": 25
  }'

# Offset-based
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show synthesizers",
    "offset": 50,
    "limit": 25
  }'
```

## Troubleshooting

**"Cannot connect to Botswain API":**
- Make sure the server is running: `python manage.py runserver 8002`
- Check the URL: `./botswain-cli.py "..." --url http://localhost:8002`

**"No results":**
- Try a different entity or query
- Check database connectivity (VPN for production)
- Use `--debug` to see detailed request/response

**"Permission denied":**
- Make sure the script is executable: `chmod +x botswain-cli.py`

## Quick Test Script

Save this as `test-pagination.sh`:

```bash
#!/bin/bash

echo "Testing Pagination..."
echo ""

echo "1. Page 1 (default):"
./botswain-cli.py "Show synthesizers" --page-size 10
echo ""

echo "2. Page 2:"
./botswain-cli.py "Show synthesizers" --page 2 --page-size 10
echo ""

echo "3. Using offset:"
./botswain-cli.py "Show synthesizers" --offset 20 --limit 10
echo ""

echo "Done!"
```

Run with: `chmod +x test-pagination.sh && ./test-pagination.sh`
