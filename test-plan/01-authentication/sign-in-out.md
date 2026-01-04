# Sign In and Sign Out Test Scenarios

## Sign In Operations

### Scenario: Sign in with valid credentials
- User clicks Sign In button
- OAuth flow is initiated
- User authorizes application
- Token is saved successfully
- User is logged in
- Email address is displayed in UI
- Application state shows logged_in as True

### Scenario: Sign in status check when logged in
- User is already logged in with valid token
- check_login_status() should return logged_in: True
- Email address should be returned
- Should not trigger new OAuth flow

### Scenario: Sign in status check when not logged in
- User has no valid token
- check_login_status() should return logged_in: False
- Email should be None
- Application should indicate sign-in is needed

### Scenario: Sign in API endpoint
- POST /api/sign-in is called
- Should trigger OAuth flow in background
- Should return {"status": "signing_in"}
- Should not block the request

### Scenario: Sign in with web auth status check
- GET /api/web-auth-status is called
- Should return needs_setup, web_auth_mode, has_credentials, pending_auth_url
- Status should accurately reflect current authentication state

### Scenario: Sign in triggers background OAuth thread
- Sign in should not block main application
- OAuth flow should run in background thread
- Application should remain responsive
- User should see sign-in initiated message immediately

## Sign Out Operations

### Scenario: Sign out when logged in
- User is logged in with valid token
- User clicks Sign Out button
- POST /api/sign-out is called
- Token file should be deleted
- User state should be reset (email: None, logged_in: False)
- Scan results should be cleared
- Delete scan results should be cleared
- Mark read status should be reset
- Application should return success message

### Scenario: Sign out when not logged in
- User is not logged in (no token file)
- User attempts to sign out
- Sign out should succeed without error
- State should remain logged out
- No token file operations should occur

### Scenario: Sign out clears all application state
- User has scan results, delete scan results, and mark read status
- User signs out
- All operation states should be reset
- All results should be cleared
- Application should return results_cleared: True

### Scenario: Sign out API endpoint response
- POST /api/sign-out should return success: True
- Should return message indicating successful sign out
- Should return results_cleared: True if results existed

### Scenario: Sign out with token file deletion error
- Token file exists but deletion fails (permission error)
- Application should handle error appropriately
- State should still be reset
- Error should be logged

## Authentication State Management

### Scenario: Authentication state persistence
- User signs in successfully
- Application restarts
- User should still be logged in if token is valid
- State should be restored from token file

### Scenario: Authentication state after token expiry
- User was logged in
- Token expires without refresh token
- Application should detect expired token
- User should be logged out automatically
- User should be prompted to sign in again

### Scenario: Multiple sign-in attempts
- User triggers sign-in multiple times rapidly
- Only one OAuth flow should be active
- Subsequent attempts should be blocked with appropriate message
- _auth_in_progress flag should prevent duplicates

### Scenario: Sign in after sign out
- User signs out successfully
- User attempts to sign in again
- OAuth flow should start normally
- New token should be created
- User should be logged in successfully

## Authentication Status Endpoints

### Scenario: GET /api/auth-status when logged in
- User is logged in with valid token
- Endpoint should return logged_in: True
- Should return user's email address
- Should update current_user state

### Scenario: GET /api/auth-status when logged out
- User is not logged in
- Endpoint should return logged_in: False
- Email should be None
- Should not trigger OAuth flow

### Scenario: GET /api/web-auth-status with credentials
- credentials.json file exists
- has_credentials should be True
- Status should reflect actual state

### Scenario: GET /api/web-auth-status without credentials
- credentials.json file does not exist
- has_credentials should be False
- needs_setup should be True

### Scenario: GET /api/web-auth-status in web auth mode
- WEB_AUTH environment variable is set to true
- web_auth_mode should be True
- Status should reflect web auth configuration
