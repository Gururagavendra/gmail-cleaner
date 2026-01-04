# Unsubscribe Scan Test Scenarios

## Basic Scan Operations

### Scenario: Scan emails with default limit
- User triggers email scan without specifying limit
- Application should use default limit of 500 emails
- Scan should process emails in batches
- Results should include unsubscribe links found

### Scenario: Scan emails with custom limit
- User specifies custom limit (e.g., 1000 emails)
- Application should respect the limit
- Scan should process up to the specified number of emails
- Should not exceed Gmail API maximum per request (500)

### Scenario: Scan emails with maximum limit
- User specifies maximum limit of 5000 emails
- Application should process up to 5000 emails
- Should handle pagination correctly
- All emails should be scanned

### Scenario: Scan emails with minimum limit
- User specifies limit of 1 email
- Application should scan exactly 1 email
- Results should reflect single email scan

## Scan Progress and Status

### Scenario: Scan status updates during operation
- User starts email scan
- GET /api/status should return progress updates
- Progress should increment from 0 to 100
- Message should update with current status
- done should be False during scan

### Scenario: Scan status when complete
- Email scan completes successfully
- GET /api/status should return done: True
- Progress should be 100
- Message should indicate completion
- Error should be None

### Scenario: Scan status with no emails found
- Scan operation finds no emails matching criteria
- Status should indicate "No emails found"
- done should be True
- Progress should be 100
- Results should be empty

### Scenario: Scan status on error
- Scan operation encounters an error
- Status should include error message
- done should be True
- Error details should be available

## Scan Results

### Scenario: Retrieve scan results
- Scan completes successfully
- GET /api/results should return list of senders with unsubscribe links
- Each result should contain domain, link, count, type, sender info
- Results should be properly formatted

### Scenario: Scan results with unsubscribe links
- Scan finds emails with List-Unsubscribe headers
- Results should include unsubscribe links
- Links should be properly extracted (HTTP links preferred over mailto)
- Type should be "manual" or "one-click" as appropriate

### Scenario: Scan results with one-click unsubscribe
- Scan finds emails with List-Unsubscribe-Post header
- Results should indicate one-click unsubscribe type
- Link should be properly extracted

### Scenario: Scan results with mailto unsubscribe
- Scan finds emails with only mailto unsubscribe links
- Results should include mailto links
- Type should be "manual"
- Link should be properly formatted

### Scenario: Scan results grouped by domain
- Multiple emails from same domain found
- Results should group by domain
- Count should reflect total emails from domain
- Should show sample subjects (up to 3)

### Scenario: Scan results with sender information
- Results should include sender name and email
- Sender name should be extracted from From header
- Email address should be extracted correctly
- Should handle various From header formats

### Scenario: Scan results with date information
- Results should include first_date and last_date
- Dates should be extracted from email headers
- Should handle various date formats

## Batch Processing

### Scenario: Scan processes emails in batches
- Large number of emails to scan
- Application should use Gmail Batch API
- Should process 100 emails per batch
- Progress should update after each batch

### Scenario: Scan with pagination
- More emails than single API call can return
- Application should use page tokens for pagination
- Should fetch all emails up to limit
- Should handle empty pages gracefully

### Scenario: Scan batch API error handling
- Individual batch request fails
- Application should handle exception gracefully
- Should continue processing remaining batches
- Failed emails should not crash scan

## Scan Initialization

### Scenario: Scan resets previous results
- Previous scan results exist
- New scan is initiated
- Previous results should be cleared
- Scan status should be reset
- New results should replace old ones

### Scenario: Scan with authentication required
- User is not logged in
- Scan operation should detect missing authentication
- Should return appropriate error
- Status should indicate authentication needed

### Scenario: Scan API endpoint
- POST /api/scan is called with valid request
- Should start scan in background task
- Should return {"status": "started"} immediately
- Should not block the request
