# Delete Scan Test Scenarios

## Delete Scan Operations

### Scenario: Scan senders for deletion with default limit
- User triggers delete scan without specifying limit
- Application should use default limit of 1000 emails
- Scan should identify senders and email counts
- Results should be grouped by sender

### Scenario: Scan senders for deletion with custom limit
- User specifies custom limit (e.g., 5000 emails)
- Application should respect the limit
- Should not exceed maximum limit of 10000
- Scan should process up to specified number

### Scenario: Scan senders with filters
- User specifies filters for delete scan
- Scan should apply filters before grouping by sender
- Results should only include matching emails
- Filters should work same as regular scan

### Scenario: Delete scan API endpoint
- POST /api/delete-scan is called
- Should start scan in background task
- Should return {"status": "started"}
- Should not block request

## Delete Scan Results

### Scenario: Get delete scan results
- DELETE scan completes successfully
- GET /api/delete-scan-results should return sender list
- Each result should contain sender info, count, size, message IDs
- Results should be grouped by sender email

### Scenario: Delete scan results with sender information
- Results should include sender name and email
- Sender name should be extracted from From header
- Email address should be extracted correctly
- Should handle various From header formats

### Scenario: Delete scan results with email counts
- Results should show count of emails per sender
- Count should be accurate
- Should match actual emails found

### Scenario: Delete scan results with total size
- Results should include total size per sender
- Size should be sum of all emails from sender
- Should be in bytes (sizeEstimate)

### Scenario: Delete scan results with message IDs
- Results should include message IDs for each sender
- Message IDs should be valid Gmail message IDs
- IDs should be used for deletion operations

### Scenario: Delete scan results with subject samples
- Results should include up to 3 sample subjects per sender
- Subjects should be from different emails
- Should provide representative samples

### Scenario: Delete scan results with date information
- Results should include first_date and last_date per sender
- First date should be earliest email from sender
- Last date should be most recent email from sender

## Delete Scan Status

### Scenario: Delete scan status during operation
- DELETE scan in progress
- GET /api/delete-scan-status should return progress
- Progress should increment from 0 to 100
- Message should update with current status

### Scenario: Delete scan status when complete
- DELETE scan completes successfully
- Status should indicate done: True
- Progress should be 100
- Error should be None

### Scenario: Delete scan status with no results
- DELETE scan finds no emails
- Status should indicate "No emails found"
- Results should be empty
- Scan should complete successfully

### Scenario: Delete scan status on error
- DELETE scan encounters error
- Status should include error message
- done should be True
- Error details should be available

## Delete Scan Batch Processing

### Scenario: Delete scan processes emails in batches
- Large number of emails to scan
- Application should use Gmail Batch API
- Should process 100 emails per batch
- Progress should update after each batch

### Scenario: Delete scan with pagination
- More emails than single API call can return
- Application should use page tokens
- Should fetch all emails up to limit
- Should handle pagination correctly

## Delete Scan Initialization

### Scenario: Delete scan resets previous results
- Previous delete scan results exist
- New delete scan is initiated
- Previous results should be cleared
- Status should be reset

### Scenario: Delete scan with authentication required
- User is not logged in
- Delete scan should detect missing authentication
- Should return appropriate error
- Status should indicate authentication needed
