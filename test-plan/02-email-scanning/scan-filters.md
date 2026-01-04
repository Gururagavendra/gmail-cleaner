# Scan Filters Test Scenarios

## Date Filters

### Scenario: Scan with older_than filter
- User specifies older_than: "30d"
- Scan should only process emails older than 30 days
- Gmail query should include "older_than:30d"
- Results should only include matching emails

### Scenario: Scan with older_than filter - various values
- Test with "7d", "30d", "90d", "180d", "365d"
- Each should generate correct Gmail query
- Results should match filter criteria

### Scenario: Scan with after_date filter
- User specifies after_date: "2025/01/15"
- Scan should only process emails after specified date
- Gmail query should include date filter
- Date format should be validated (YYYY/MM/DD)

### Scenario: Scan with before_date filter
- User specifies before_date: "2025/12/31"
- Scan should only process emails before specified date
- Gmail query should include date filter
- Date format should be validated (YYYY/MM/DD)

### Scenario: Scan with date range (after_date and before_date)
- User specifies both after_date and before_date
- Scan should process emails within date range
- Both filters should be applied correctly

### Scenario: Scan with invalid date format
- User specifies invalid date format
- Validation should reject invalid format
- Should return validation error
- Scan should not proceed

## Size Filters

### Scenario: Scan with larger_than filter
- User specifies larger_than: "5M"
- Scan should only process emails larger than 5MB
- Gmail query should include "larger:5M"
- Results should only include matching emails

### Scenario: Scan with larger_than filter - various units
- Test with "1K", "1M", "1G" (case insensitive)
- Each should generate correct Gmail query
- Results should match filter criteria

### Scenario: Scan with invalid size format
- User specifies invalid size format
- Validation should reject invalid format
- Should return validation error
- Format must match regex: ^\d+[KMG]$

## Category Filters

### Scenario: Scan with category: promotions
- User specifies category: "promotions"
- Scan should only process emails in Promotions category
- Gmail query should include "category:promotions"
- Results should only include matching emails

### Scenario: Scan with category: social
- User specifies category: "social"
- Scan should process Social category emails
- Category should be converted to lowercase
- Results should match filter

### Scenario: Scan with category: updates
- User specifies category: "updates"
- Scan should process Updates category emails
- Results should match filter

### Scenario: Scan with category: primary
- User specifies category: "primary"
- Scan should process Primary category emails
- Results should match filter

### Scenario: Scan with category: forums
- User specifies category: "forums"
- Scan should process Forums category emails
- Results should match filter

### Scenario: Scan with invalid category
- User specifies invalid category value
- Validation should reject invalid category
- Should return error with allowed values list
- Scan should not proceed

### Scenario: Scan with category case insensitive
- User specifies "PROMOTIONS" (uppercase)
- Category should be converted to lowercase
- Query should use lowercase category
- Results should match filter

## Sender Filters

### Scenario: Scan with sender email filter
- User specifies sender: "newsletter@example.com"
- Scan should only process emails from specific sender
- Gmail query should include sender filter
- Results should only include matching emails

### Scenario: Scan with sender domain filter
- User specifies sender: "example.com"
- Scan should process emails from domain
- Query should handle domain-only format
- Results should match filter

### Scenario: Scan with invalid sender format
- User specifies sender without @ or .
- Validation should reject invalid format
- Should return validation error
- Scan should not proceed

## Label Filters

### Scenario: Scan with label filter
- User specifies label: "INBOX"
- Scan should only process emails with specified label
- Gmail query should include label filter
- Results should only include matching emails

### Scenario: Scan with custom label filter
- User specifies custom label
- Scan should process emails with that label
- Results should match filter

## Combined Filters

### Scenario: Scan with multiple filters
- User specifies multiple filters (e.g., older_than, category, larger_than)
- All filters should be combined in Gmail query
- Results should match all filter criteria
- Filters should be joined with spaces in query

### Scenario: Scan with filters and custom limit
- User specifies filters and custom limit
- Both should be applied correctly
- Limit should be respected
- Filters should be applied before limiting

### Scenario: Scan with empty filter values
- User specifies filters with empty strings
- Empty filters should be ignored
- Query should only include valid filters
- Scan should proceed with non-empty filters

### Scenario: Scan with None filter values
- User specifies filters with None values
- None filters should be ignored
- Query should only include valid filters
- Scan should proceed normally

### Scenario: Scan without any filters
- User does not specify any filters
- Scan should process all emails (up to limit)
- Query should be empty string
- Results should include all scanned emails

## Filter Validation

### Scenario: Filters model validation
- Request includes FiltersModel
- Validation should check all field formats
- Invalid fields should be rejected
- Valid fields should be accepted

### Scenario: Filter boundary values
- Test filters with edge case values
- Minimum and maximum valid values should work
- Boundary conditions should be handled correctly
