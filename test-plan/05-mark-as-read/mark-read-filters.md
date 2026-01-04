# Mark as Read Filters Test Scenarios

## Mark as Read with Filters

### Scenario: Mark as read with older_than filter
- User specifies older_than: "30d" filter
- Should only mark emails older than 30 days as read
- Gmail query should include older_than filter
- Should combine with is:unread query

### Scenario: Mark as read with date filters
- User specifies after_date or before_date filters
- Should only mark emails within date range as read
- Date filters should be applied correctly
- Should combine with is:unread

### Scenario: Mark as read with size filter
- User specifies larger_than filter
- Should only mark emails larger than specified size as read
- Size filter should be applied correctly
- Should combine with is:unread

### Scenario: Mark as read with category filter
- User specifies category filter (e.g., promotions)
- Should only mark emails in that category as read
- Category filter should be applied correctly
- Should combine with is:unread

### Scenario: Mark as read with sender filter
- User specifies sender filter
- Should only mark emails from that sender as read
- Sender filter should be applied correctly
- Should combine with is:unread

### Scenario: Mark as read with label filter
- User specifies label filter
- Should only mark emails with that label as read
- Label filter should be applied correctly
- Should combine with is:unread

## Combined Filters

### Scenario: Mark as read with multiple filters
- User specifies multiple filters
- All filters should be combined in query
- Should mark emails matching all criteria as read
- Filters should be properly combined

### Scenario: Mark as read query construction
- Query should always include is:unread
- Additional filters should be appended
- Query should be properly formatted
- Should use build_gmail_query for filter construction

### Scenario: Mark as read with filters and count
- User specifies both filters and count
- Should apply filters first
- Then limit to count
- Should respect both parameters

## Filter Validation

### Scenario: Mark as read with invalid filters
- User specifies invalid filter values
- Validation should reject invalid filters
- Should return validation error
- Operation should not proceed

### Scenario: Mark as read with empty filters
- User specifies empty filter values
- Empty filters should be ignored
- Should proceed with just is:unread
- Should work correctly
