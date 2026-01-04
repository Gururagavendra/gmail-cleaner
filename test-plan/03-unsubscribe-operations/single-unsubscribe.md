# Single Unsubscribe Test Scenarios

## Successful Unsubscribe

### Scenario: Unsubscribe with valid HTTP link
- User clicks unsubscribe button for a sender
- Unsubscribe link is valid HTTP/HTTPS URL
- POST /api/unsubscribe is called with domain and link
- Application should make HTTP request to unsubscribe link
- Should return success response
- Unsubscribe should complete successfully

### Scenario: Unsubscribe with one-click link
- Unsubscribe link supports one-click unsubscribe
- Application should send POST request with List-Unsubscribe=One-Click
- Should handle one-click unsubscribe properly
- Should return success response

### Scenario: Unsubscribe with mailto link
- Unsubscribe link is mailto: address
- Application should handle mailto link appropriately
- Should return appropriate response
- May require different handling than HTTP links

### Scenario: Unsubscribe API endpoint
- POST /api/unsubscribe with domain and link
- Endpoint should accept UnsubscribeRequest
- Should call unsubscribe_single function
- Should return success/error response

## Unsubscribe Error Handling

### Scenario: Unsubscribe with invalid link
- Unsubscribe link is malformed or invalid
- Application should handle invalid link error
- Should return error response
- Should not crash application

### Scenario: Unsubscribe with unreachable link
- Unsubscribe link is unreachable (404, timeout, etc.)
- Application should handle network errors
- Should return appropriate error message
- Error should be logged

### Scenario: Unsubscribe with empty domain
- Domain parameter is empty string
- Application should handle empty domain
- Should validate input
- Should return error if required

### Scenario: Unsubscribe with empty link
- Link parameter is empty string
- Application should handle empty link
- Should validate input
- Should return error if required

### Scenario: Unsubscribe network failure
- Network error during unsubscribe request
- Application should catch network exceptions
- Should return error response
- Should handle gracefully

### Scenario: Unsubscribe with authentication required
- Unsubscribe requires authentication but not logged in
- Application should check authentication
- Should return authentication error
- Should not attempt unsubscribe

## Unsubscribe Response

### Scenario: Unsubscribe success response
- Unsubscribe completes successfully
- Response should indicate success: True
- Should include success message
- Should include domain information

### Scenario: Unsubscribe error response
- Unsubscribe fails
- Response should indicate success: False
- Should include error message
- Should be descriptive of failure reason

### Scenario: Unsubscribe response structure
- Response should match UnsubscribeResponse model
- Should contain success, message, domain fields
- Should be properly formatted JSON

## Link Validation

### Scenario: Unsubscribe link safety validation
- Link should be validated before making request
- Should check for unsafe URLs
- Should prevent malicious links
- Validation should occur before HTTP request

### Scenario: Unsubscribe with relative URL
- Link is relative URL
- Application should handle relative URLs
- Should construct absolute URL if needed
- Should validate properly

### Scenario: Unsubscribe with different protocols
- Link uses various protocols (http, https, mailto)
- Application should handle each appropriately
- Should validate protocol
- Should use correct method for each
