# Botswain Comprehensive Bug Report - 15 Critical Issues Found

**Test Date**: 2026-03-12
**Testing Method**: Playwright automated browser testing
**Total Tests**: 26 queries across edge cases, invalid inputs, and complex scenarios
**Bugs Found**: 15 critical bugs

---

## Summary by Severity

| Severity | Count | Bugs |
|----------|-------|------|
| 🔴 CRITICAL | 6 | #1, #2, #5, #6, #10, #11 |
| 🟠 HIGH | 5 | #3, #7, #8, #9, #12 |
| 🟡 MEDIUM | 4 | #4, #13, #14, #15 |

---

## 🔴 CRITICAL BUGS (6)

### Bug #1: Filtered Aggregations Not Working
**Severity**: 🔴 CRITICAL
**Test Query**: `count synthesizers by location`
**Expected**: Group 59 synthesizers by their factory location (CRISPR/CELLS/IC)
**Actual**: Found 59 synthesizers but shows **"0 categories"** and **"No data to display"**

**Impact**: Cannot combine filters with GROUP BY clauses. Multi-dimensional queries completely broken.

**Root Cause**: Query executor not properly grouping filtered results.

**Technical Details**:
- Query successfully filters to 59 synthesizers (instrument_type='synthesizer')
- Aggregation step fails to group by location field
- Results in empty aggregation: `"0 categories"`
- Check `query_executor.py` lines 225-300 (`_calculate_count_aggregations`)

**Affected Queries**: Any query with both a WHERE filter and GROUP BY clause.

---

### Bug #2: GROUP BY Field Not Respected
**Severity**: 🔴 CRITICAL
**Test Query**: `count github issues by author`
**Expected**: Group by author field
**Actual**: Grouped by STATE field instead (same result as "count github issues by state")

**Result**: 99 issues across 2 categories - OPEN: 87, CLOSED: 12 (should be grouped by author names)

**Impact**: Wrong dimension used for grouping, making results completely misleading.

**Root Cause**: Either:
1. LLM not parsing "by author" correctly in intent
2. Backend defaulting to wrong field when group_by field doesn't exist in entity
3. GitHub entity doesn't have "author" field properly mapped

**Investigation Needed**:
- Add logging to see what `group_by` value is in the intent
- Check GitHub entity definition in `semantic_layer/registry.py`
- Verify author field mapping

---

### Bug #5: Numeric Aggregations Fail with "No Columns Defined"
**Severity**: 🔴 CRITICAL
**Test Query**: `average workflow execution time`
**Expected**: Calculate and display average execution time
**Actual**: **Error: No columns defined**

**Console Errors** (repeated 4 times):
```
DataTable: columns prop is required and must be a non-empty array
```

**Impact**: All numeric aggregations (sum, avg, min, max) are completely broken.

**Root Cause**: Layout analyzer not generating proper column definitions for numeric aggregation results.

**File**: `layout_analyzer.py` - not handling non-count aggregations properly.

---

### Bug #6: Filtered Count Returns Raw Table Instead of Aggregation
**Severity**: 🔴 CRITICAL
**Test Query**: `count online synthesizers`
**Expected**: Single count number or aggregation
**Actual**: Raw table showing all 54 synthesizers (10 rows displayed)

**Impact**: Simple count queries with filters don't aggregate - they return raw data tables.

**Example Output**:
```
Found 54 synthesizer (showing results 1-54)
[Table with barcode, name, status, host, port columns...]
```

**Root Cause**: Intent parser treating filtered count as a regular query instead of aggregation.

---

### Bug #10: Comparison Operators Crash with Parsing Error
**Severity**: 🔴 CRITICAL
**Test Query**: `count workflows where id > 1000`
**Expected**: Filter workflows with id greater than 1000
**Actual**: **Error: invalid literal for int() with base 10: '> 1000'**

**HTTP Status**: 400 Bad Request

**Impact**: Cannot use comparison operators (>, <, >=, <=, !=) in filters.

**Root Cause**: Backend trying to convert "> 1000" to integer directly without parsing the operator.

**Fix Needed**: Parse comparison operators separately from values in filter logic.

---

### Bug #11: Numeric Equality Filters Return No Results
**Severity**: 🔴 CRITICAL
**Test Query**: `count instruments where barcode = 1779`
**Expected**: Find instrument with barcode 1779 (exists in database)
**Actual**: **No Results Found - No instrument found matching your criteria**

**Impact**: Cannot filter by numeric equality. Numeric IDs/barcodes unusable as filters.

**Note**: This barcode (1779) definitely exists in the database - it appears in other query results.

**Root Cause**: Likely type mismatch or incorrect filter construction for numeric fields.

---

## 🟠 HIGH SEVERITY BUGS (5)

### Bug #3: Invalid Entity Silently Substituted
**Severity**: 🟠 HIGH
**Test Query**: `count foobar by status`
**Expected**: Error message: "Unknown entity: foobar"
**Actual**: LLM silently substituted "synthesizer" - returned 59 synthesizers by status

**HTTP Status**: 400 Bad Request (in console)

**Impact**: No validation feedback - users won't know their query was misinterpreted.

**Result**:
```
Found 59 synthesizer across 2 categories
Synthesizer by Status
online: 54, offline: 5
```

**Root Cause**: LLM hallucinating entity names instead of returning error when entity doesn't exist.

---

### Bug #7: Special Characters and SQL Injection Not Filtered
**Severity**: 🟠 HIGH (Security Issue)
**Test Queries**:
1. `count instruments with name @#$%`
2. `count instruments where name = '1' OR '1'='1'`

**Expected**:
- Query 1: No results or error for invalid characters
- Query 2: SQL injection blocked or sanitized

**Actual**: Both returned **ALL 101+ instruments** (full table, no filtering)

**Impact**:
- Special characters completely ignored
- Potential SQL injection vulnerability (though Django ORM likely prevents actual injection)
- Users get wrong results with no indication filters were ignored

**Root Cause**: Filter parsing ignores/strips special characters and complex conditions.

---

### Bug #8: Invalid GROUP BY Field Returns "0 Categories"
**Severity**: 🟠 HIGH
**Test Query**: `count online instruments by invalidfield`
**Expected**: Error: "Invalid field: invalidfield"
**Actual**: Found 203 instruments but **"0 categories"** and **"No data to display"**

**Impact**: No validation error - users see "0 categories" and think query succeeded but returned no groups.

**Root Cause**: Backend doesn't validate group_by field exists before attempting aggregation.

---

### Bug #9: Unicode Filters Ignored/Misinterpreted
**Severity**: 🟠 HIGH
**Test Query**: `count instruments with name 测试` (Chinese characters)
**Expected**: Filter by name containing "测试"
**Actual**: Returned 59 synthesizers (completely different entity and no name filtering)

**Impact**: International character support completely broken. Non-ASCII filters produce wrong results.

**Root Cause**: Filter parsing fails with unicode characters, possibly falling back to default query.

---

### Bug #12: Percentage Queries Return Raw Table
**Severity**: 🟠 HIGH
**Test Query**: `what percentage of instruments are online`
**Expected**: Calculate and display percentage (e.g., "90.2% of instruments are online")
**Actual**: Raw table showing 101+ instruments with all fields

**Impact**: Percentage/ratio calculations not supported - users get raw data instead of computed results.

**Calculation**: Should be ~90.2% (203 online out of 225 total)

**Root Cause**: Intent parser doesn't recognize percentage queries as a special aggregation type.

---

## 🟡 MEDIUM SEVERITY BUGS (4)

### Bug #4: Typos Auto-Corrected Without Warning
**Severity**: 🟡 MEDIUM
**Test Query**: `count instruments by statuss` (typo: statuss → status)
**Expected**: Error or warning about misspelled field
**Actual**: Silently corrected to "status" and returned results

**Result**: Found 225 instruments across 2 categories (online: 203, offline: 22)

**Impact**: Users don't know their query was modified. Could lead to confusion if correction is wrong.

**Note**: Auto-correction can be helpful, but should notify user.

---

### Bug #13: Sorting Instructions Ignored
**Severity**: 🟡 MEDIUM
**Test Query**: `count instruments by type sorted by count`
**Expected**: Results sorted by count descending (synthesizer: 59, zebra_printer: 22, liquid_handling: 19...)
**Actual**: Results appear in arbitrary order (miseq-sequencer: 2, argo: 2, bioshake: 7...)

**Impact**: Cannot control sort order of aggregation results.

**Root Cause**: ORDER BY clause not implemented in aggregation queries.

---

### Bug #14: Limit/Top N Instructions Ignored
**Severity**: 🟡 MEDIUM
**Test Query**: `count instruments by type limit to top 5`
**Expected**: Show only top 5 types by count
**Actual**: Returned all 21 types

**Impact**: Cannot limit aggregation results to top N categories.

**Root Cause**: LIMIT clause not parsed/applied in aggregation queries.

---

### Bug #15: OR Logic Not Supported
**Severity**: 🟡 MEDIUM
**Test Query**: `count github issues that are open or closed`
**Expected**: All issues (both open and closed)
**Actual**: **No Results Found - No github_issue found matching your criteria**

**Impact**: Cannot use OR logic in filters. Only AND logic supported.

**Root Cause**: Filter parser doesn't handle OR conditions.

---

## Working Features (Validated)

✅ **Case insensitivity**: `count INSTRUMENTS by TYPE` works correctly
✅ **Single category aggregation**: Mercury instrument (1 item) displays chart and table
✅ **Invalid filter values**: `count instruments in XYZFACTORY` correctly returns no results
✅ **Ambiguous queries**: `count stuff` returns helpful error message requesting clarification

---

## Bug Categories

### Query Parsing Issues (5 bugs)
- Bug #2: Wrong GROUP BY field selected
- Bug #3: Invalid entity substituted
- Bug #4: Typos auto-corrected silently
- Bug #6: Count queries return raw tables
- Bug #12: Percentage queries not recognized

### Filter Logic Bugs (5 bugs)
- Bug #1: Filtered aggregations broken
- Bug #7: Special characters and SQL injection ignored
- Bug #9: Unicode filters fail
- Bug #10: Comparison operators crash
- Bug #11: Numeric equality filters fail

### Aggregation Issues (3 bugs)
- Bug #5: Numeric aggregations crash
- Bug #8: Invalid GROUP BY field returns "0 categories"
- Bug #13: Sorting not implemented

### Feature Gaps (2 bugs)
- Bug #14: Limit/Top N not supported
- Bug #15: OR logic not supported

---

## Recommendations

### Immediate Fixes (CRITICAL)

1. **Bug #1 - Filtered Aggregations** (HIGHEST PRIORITY)
   - Fix `_calculate_count_aggregations` to handle filtered querysets
   - Test case: "count synthesizers by location"

2. **Bug #2 - GROUP BY Validation**
   - Add field existence validation before grouping
   - Log actual group_by value from LLM
   - Add test coverage for all valid group_by fields per entity

3. **Bug #5 - Numeric Aggregations**
   - Implement column generation for avg/sum/min/max results
   - Add proper layout handling for numeric aggregation types

4. **Bug #6 - Count Query Detection**
   - Improve intent parser to distinguish count+filter from list queries
   - "count X" should always return aggregation, not raw table

5. **Bug #10 - Comparison Operators**
   - Parse operators (>, <, >=, <=, !=) before type conversion
   - Update filter logic to handle operator+value pairs

6. **Bug #11 - Numeric Filters**
   - Fix type handling for numeric field filters
   - Ensure barcode/id filters work correctly

### High Priority Fixes

7. **Bug #3 - Entity Validation**
   - Return error for unknown entities instead of substituting
   - Add entity name validation before LLM processing

8. **Bug #7 - Input Sanitization**
   - Validate special characters in filter values
   - Add test coverage for SQL injection attempts
   - Return proper error messages for invalid filter syntax

9. **Bug #8 - Field Validation**
   - Validate group_by field exists in entity schema
   - Return clear error message for invalid fields

10. **Bug #9 - Unicode Support**
    - Fix filter parsing to handle unicode characters
    - Add test coverage for international characters

11. **Bug #12 - Percentage Queries**
    - Implement percentage/ratio calculations
    - Add new intent type: "percentage" or "ratio"

### Medium Priority Enhancements

12. **Bug #13 - Sorting**
    - Implement ORDER BY for aggregation results
    - Default to descending by count

13. **Bug #14 - Limit/Top N**
    - Parse and apply LIMIT clause to aggregations
    - Support "top 5", "first 10", "limit to 3" phrases

14. **Bug #15 - OR Logic**
    - Implement OR filter conditions
    - Parse "X or Y" in filter clauses

15. **Bug #4 - Auto-Correction Feedback**
    - Add UI indicator when query is auto-corrected
    - Show "Did you mean: status?" message

---

## Test Coverage Gaps

**Missing test scenarios**:
- Empty result sets with aggregation
- NULL value handling
- Date/time filtering and aggregation
- Multi-field GROUP BY (e.g., "by type and location")
- Nested aggregations
- DISTINCT counts
- String pattern matching (LIKE, CONTAINS)
- Case-sensitive vs case-insensitive filtering
- Cross-entity queries (JOINs)

---

## Impact Assessment

| Impact Level | Bug Count | User Impact |
|--------------|-----------|-------------|
| **Blocks Core Features** | 6 | Cannot use filtered aggregations, numeric aggregations, comparison filters |
| **Wrong Results** | 5 | Silently returns incorrect data (wrong grouping, ignored filters) |
| **Missing Features** | 4 | Cannot use sorting, limits, percentages, OR logic |

**Production Readiness**: ❌ **NOT READY**

**Blockers**:
1. Filtered aggregations completely broken (Bug #1)
2. GROUP BY not working correctly (Bug #2)
3. Numeric aggregations crash (Bug #5)
4. Comparison operators crash (Bug #10)

**Minimum Viable Product** requires fixing all 6 CRITICAL bugs.

---

## Test Artifacts

All test screenshots saved to `/tmp/`:
- `bug-test-1-invalid-entity.png` - Bug #3
- `bug-test-5-numeric-agg.png` - Bug #5
- `bug-test-8-case-sensitivity.png` - Case sensitivity working
- `bug-test-10-11-special-chars.png` - Bugs #7, #10, #11
- `bug-test-15-double-count.png` - Test 15
- `bug-test-16-17-edge-cases.png` - Bugs #8, #9
- `bug-test-18-19-multi-agg.png` - Bug #10
- `bug-test-20-22-edge-cases.png` - Bugs #11, #12
- `bug-test-22-23-sorting.png` - Bugs #12, #13
- `bug-test-24-limit.png` - Bug #14
- `bug-test-final-25-26.png` - Bug #15, single category test
- `bug-test-26-single-category.png` - Single category edge case

---

## Conclusion

Found **15 bugs** across 26 test queries:
- ✅ **6 CRITICAL** bugs that block core functionality
- ⚠️ **5 HIGH** bugs that produce wrong results or security issues
- 🟡 **4 MEDIUM** bugs that limit usability

**System Status**: The dynamic UI successfully handles basic aggregations but has critical bugs that make it unsuitable for production:
- Filtered aggregations are completely broken
- GROUP BY doesn't respect field names
- Numeric aggregations crash
- Most filter types don't work (comparison, equality, unicode, special chars)

**Estimated Fix Time**:
- CRITICAL bugs: 2-3 days
- HIGH bugs: 1-2 days
- MEDIUM bugs: 1 day
- **Total: 4-6 days** of engineering work

**Next Steps**:
1. Fix all CRITICAL bugs (#1, #2, #5, #6, #10, #11)
2. Add comprehensive test suite covering all bug scenarios
3. Implement input validation and error messages
4. Re-test with this bug report as regression test suite
5. Deploy to staging for QA validation
