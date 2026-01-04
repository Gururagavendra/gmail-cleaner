# Mark as Read Operations Test Scenarios

## Basic Mark as Read

### Scenario: Mark emails as read with default count
- User triggers mark as read without specifying count
- Application should use default count of 100 emails
- Should mark unread emails as read
- Should return success response

### Scenario: Mark emails as read with custom count
- User specifies custom count (e.g., 500 emails)
- Application should respect the count
- Should not exceed maximum limit of 100000
- Should mark specified number of emails

### Scenario: Mark as read API endpoint
- POST /api/mark-read is called with count and filters
- Endpoint should accept MarkReadRequest
- Should start background task
- Should return {"status": "started"}

### Scenario: Mark as read with no filters
- User marks emails as read without filters
- Should mark unread emails matching count
- Should process all unread emails up to limit
- Should work correctly

## Mark as Read Status

### Scenario: Mark as read status during operation
- Mark as read operation in progress
- GET /api/mark-read-status should return progress
- Progress should increment from 0 to 100
- Message should update with current status

### Scenario: Mark as read status fields
- Status should include progress, message, done, error, marked_count
- Should provide detailed progress information
- Should update in real-time

### Scenario: Mark as read status when complete
- Operation completes successfully
- Status should indicate done: True
- Progress should be 100
- marked_count should match emails marked
- Error should be None

### Scenario: Mark as read status with no unread emails
- No unread emails found matching criteria
- Status should indicate "No unread emails found"
- done should be True
- marked_count should be 0

### Scenario: Mark as read status on error
- Operation encounters error
- Status should include error message
- done should be True
- Error details should be available

## Mark as Read Operations

### Scenario: Mark as read uses batch operations
- Large number of emails to mark as read
- Application should use batchModify API
- Should process in batches of 100
- Should remove UNREAD label in batches

### Scenario: Mark as read with pagination
- More unread emails than single API call can return
- Application should use page tokens
- Should fetch all unread emails up to count
- Should handle pagination correctly

### Scenario: Mark as read tracks marked count
- marked_count should increment as emails are marked
- Should reflect actual number marked
- Should be accurate

### Scenario: Mark as read progress calculation
- Progress should be calculated based on marked_count / total
- Should update incrementally
- Should reach 100% when complete

## Mark as Read Initialization

### Scenario: Mark as read resets previous status
- Previous mark as read status exists
- New operation is initiated
- Previous status should be reset
- New operation should start fresh

### Scenario: Mark as read with authentication required
- User is not logged in
- Operation should check authentication
- Should return authentication error
- Should not attempt operation

## Unread Count

### Scenario: Get unread email count
- GET /api/unread-count is called
- Should return current unread email count
- Count should be accurate
- Should use Gmail API to get count

### Scenario: Unread count when logged out
- User is not logged in
- Unread count should return error or 0
- Should handle authentication check

### Scenario: Unread count API error
- Gmail API returns error
- Application should handle error
- Should return error in response
- Should not crash
