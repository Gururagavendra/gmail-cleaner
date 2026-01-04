# OAuth Flow Test Scenarios

## Successful OAuth Flow

### Scenario: Complete OAuth flow with valid credentials
- User clicks Sign In button
- Application should trigger OAuth flow
- User should see authorization URL (in logs for Docker mode)
- User completes authorization in browser
- Application should receive authorization code
- Token should be saved to token.json file
- User should be authenticated and logged in
- Application should display user's email address

### Scenario: OAuth flow in web auth mode (Docker)
- Application running with WEB_AUTH=true
- OAuth flow should use bind_address 0.0.0.0
- Browser should not auto-open
- Authorization URL should be printed to logs
- User manually opens URL and authorizes
- Token should be saved successfully

### Scenario: OAuth flow in desktop mode (local Python)
- Application running locally without WEB_AUTH
- OAuth flow should use localhost bind_address
- Browser should auto-open on Windows/Mac
- Browser should auto-open on Linux if xdg-open available or DISPLAY set
- User authorizes in browser
- Token should be saved successfully

### Scenario: OAuth flow with custom OAuth host
- Application configured with OAUTH_HOST environment variable
- OAuth callback should use custom host
- Redirect URI should match custom host configuration
- Authorization should complete successfully

## OAuth Flow Errors

### Scenario: User cancels OAuth authorization
- User starts OAuth flow
- User closes browser window without authorizing
- Application should handle cancellation gracefully
- _auth_in_progress flag should be reset
- Error message should be logged
- User should be able to retry sign-in

### Scenario: OAuth port already in use
- Port 8767 is already occupied by another process
- Application should detect port conflict
- OAuth flow should fail with clear error message
- Error should be logged appropriately
- _auth_in_progress flag should be reset

### Scenario: Network failure during OAuth
- Network connection lost during OAuth flow
- Application should catch network errors
- Error should be handled gracefully
- _auth_in_progress flag should be reset
- User should be able to retry sign-in

### Scenario: Invalid authorization code
- Authorization code is malformed or expired
- Application should handle invalid code error
- User should see appropriate error message
- User should be able to retry sign-in

### Scenario: OAuth timeout
- OAuth flow times out waiting for authorization
- Application should handle timeout gracefully
- Error should be logged
- _auth_in_progress flag should be reset

### Scenario: Multiple concurrent sign-in attempts
- User triggers sign-in while another sign-in is in progress
- Application should detect concurrent attempt
- Should return "already in progress" message
- Should not start duplicate OAuth flow
- Second attempt should wait for first to complete or fail

## OAuth Flow Platform-Specific

### Scenario: OAuth on Windows
- Application running on Windows
- Browser should auto-open automatically
- OAuth flow should complete successfully

### Scenario: OAuth on macOS
- Application running on macOS
- Browser should auto-open automatically
- OAuth flow should complete successfully

### Scenario: OAuth on Linux with xdg-open
- Application running on Linux with xdg-open available
- Browser should auto-open
- OAuth flow should complete successfully

### Scenario: OAuth on Linux without xdg-open but with DISPLAY
- Application running on Linux without xdg-open but DISPLAY env var set
- Browser should auto-open
- OAuth flow should complete successfully

### Scenario: OAuth on Linux headless (no browser)
- Application running on Linux without xdg-open or DISPLAY
- Browser should not auto-open
- Authorization URL should be printed to logs
- User must manually open URL
