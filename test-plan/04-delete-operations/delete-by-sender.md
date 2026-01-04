# Delete by Sender Test Scenarios

## Single Sender Deletion

### Scenario: Delete emails from single sender
- User selects a sender from delete scan results
- Clicks delete button for that sender
- POST /api/delete-emails is called with sender email
- Application should delete all emails from that sender
- Should return success response with deleted count

### Scenario: Delete emails API endpoint
- POST /api/delete-emails with sender parameter
- Endpoint should accept DeleteEmailsRequest
- Should call delete_emails_by_sender function
- Should return success/error response

### Scenario: Delete emails response structure
- Response should match DeleteResponse model
- Should contain success, deleted count, message
- Should indicate number of emails deleted
- Should be properly formatted

## Delete Operations

### Scenario: Delete emails using message IDs
- Delete operation uses message IDs from scan results
- Should delete emails by ID using batchModify
- Should remove emails from inbox (trash them)
- Deleted emails should go to Trash folder

### Scenario: Delete emails in batches
- Large number of emails to delete from sender
- Application should delete in batches of 100
- Should use Gmail batchModify API
- Should handle batching correctly

### Scenario: Delete emails success response
- Deletion completes successfully
- Response should indicate success: True
- Should include count of deleted emails
- Should include success message

## Delete Error Handling

### Scenario: Delete emails with invalid sender
- Sender email is invalid or malformed
- Application should validate sender
- Should return error response
- Should not attempt deletion

### Scenario: Delete emails with empty sender
- Sender parameter is empty string
- Application should handle empty sender
- Should validate input
- Should return error

### Scenario: Delete emails with no emails found
- Sender has no emails to delete
- Application should handle gracefully
- Should return appropriate response
- Should not error

### Scenario: Delete emails API error
- Gmail API returns error during deletion
- Application should catch and handle error
- Should return error response
- Should not crash application

### Scenario: Delete emails with authentication required
- User is not logged in
- Delete should check authentication
- Should return authentication error
- Should not attempt deletion

### Scenario: Delete emails permission error
- User lacks permission to delete emails
- Gmail API returns permission error
- Application should handle permission error
- Should return appropriate error message

## Delete Confirmation

### Scenario: Delete emails confirmation
- User initiates delete operation
- Application should proceed with deletion
- Should delete emails as requested
- Should provide feedback on completion

### Scenario: Delete emails count accuracy
- Deleted count in response should match actual deletions
- Count should be accurate
- Should reflect emails actually deleted

### Scenario: Deleted emails in Trash
- Deleted emails should be moved to Trash
- Emails should be recoverable from Trash
- Should not be permanently deleted immediately
- Should follow Gmail deletion behavior
