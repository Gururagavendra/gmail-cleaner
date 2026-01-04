# Bulk Delete Test Scenarios

## Bulk Delete Operations

### Scenario: Delete emails from multiple senders
- User selects multiple senders for deletion
- POST /api/delete-emails-bulk is called with senders list
- Application should delete emails from all selected senders
- Should process senders sequentially or in batches

### Scenario: Bulk delete API endpoint
- POST /api/delete-emails-bulk with senders list
- Endpoint should accept DeleteBulkRequest
- Should start background task
- Should return {"status": "started"}

### Scenario: Bulk delete with large number of senders
- User selects many senders (e.g., 50+)
- Application should handle large number of senders
- Should process efficiently
- Should track progress

## Bulk Delete Status

### Scenario: Bulk delete status during operation
- Bulk delete operation in progress
- GET /api/delete-bulk-status should return progress
- Progress should update as senders are processed
- Should show current sender being processed

### Scenario: Bulk delete status fields
- Status should include progress, message, done, error
- Should include deleted_count, total_senders, current_sender
- Should provide detailed progress information
- Should update in real-time

### Scenario: Bulk delete status when complete
- All senders processed successfully
- Status should indicate done: True
- Progress should be 100
- Should show total deleted count

### Scenario: Bulk delete status with partial completion
- Some senders deleted successfully, some failed
- Status should indicate progress made
- Should show deleted count so far
- Error should indicate failures if any

## Bulk Delete Progress Tracking

### Scenario: Bulk delete tracks current sender
- Status should show which sender is being processed
- current_sender should increment as progress continues
- Should provide clear progress indication

### Scenario: Bulk delete tracks total senders
- total_senders should match number of senders selected
- Should be set at start of operation
- Should remain constant throughout operation

### Scenario: Bulk delete tracks deleted count
- deleted_count should increment as emails are deleted
- Should reflect cumulative count across all senders
- Should be accurate

## Bulk Delete Error Handling

### Scenario: Bulk delete with empty senders list
- Senders list is empty
- Application should handle empty list
- Should return appropriate response
- Should not attempt deletion

### Scenario: Bulk delete with invalid senders
- Some senders in list are invalid
- Application should skip invalid senders
- Should continue with valid senders
- Should report errors for invalid senders

### Scenario: Bulk delete with partial failures
- Some sender deletions succeed, some fail
- Application should continue processing
- Should track successes and failures
- Should complete operation with summary

### Scenario: Bulk delete with network errors
- Network failures during bulk operation
- Application should handle network errors
- Should retry or skip failed operations
- Should report errors appropriately

### Scenario: Bulk delete with API errors
- Gmail API returns errors for some senders
- Application should handle API errors
- Should continue with remaining senders
- Should report specific errors

### Scenario: Bulk delete timeout handling
- Operation takes too long
- Application should handle timeouts
- Should report timeout if occurs
- Should provide partial results

## Bulk Delete Background Processing

### Scenario: Bulk delete runs in background
- Operation should not block API request
- Should use background task
- Application should remain responsive
- Status should be pollable

### Scenario: Bulk delete concurrent operations
- User triggers multiple bulk delete operations
- Application should handle concurrent operations
- Should track each operation separately
- Should prevent conflicts if possible
