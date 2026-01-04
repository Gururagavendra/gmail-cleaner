# Token Management Test Scenarios

## Token Creation and Storage

### Scenario: Token file created after successful OAuth
- User completes OAuth authorization
- Token file (token.json) should be created
- Token should contain valid credentials
- Token should include refresh token if available
- Token should be properly formatted JSON

### Scenario: Token file permissions
- Token file should have appropriate file permissions
- Token should not be world-readable
- Token should be accessible by application process

### Scenario: Token saved with correct scopes
- Token should include required Gmail API scopes
- Scopes should match application requirements (readonly and modify)
- Token should be usable for Gmail API operations

## Token Validation

### Scenario: Valid token is recognized
- Valid token.json exists
- Application should recognize token as valid
- User should be considered logged in
- needs_auth_setup() should return False

### Scenario: Expired token with valid refresh token
- Token is expired but refresh token exists
- Application should automatically refresh token
- New token should be saved to token.json
- User should remain logged in
- API operations should continue to work

### Scenario: Expired token without refresh token
- Token is expired and no refresh token available
- Application should detect token is invalid
- User should be prompted to sign in again
- needs_auth_setup() should return True

### Scenario: Token with wrong scopes
- Token exists but has insufficient or incorrect scopes
- Application should allow token to be used initially
- API operations should fail with permission errors
- Error should be handled gracefully

### Scenario: Token refresh success
- Valid refresh token exists
- Application refreshes expired token
- New access token should be obtained
- Token file should be updated with new token
- Refresh should happen automatically when needed

### Scenario: Token refresh failure
- Refresh token is invalid or expired
- Refresh attempt should fail
- Application should clear invalid token
- User should be prompted to sign in again
- Error should be logged appropriately

## Token File Errors

### Scenario: Corrupted token file
- Token.json file exists but contains invalid JSON
- Application should detect corruption
- Should handle ValueError gracefully
- User should be prompted to sign in again
- needs_auth_setup() should return True

### Scenario: Empty token file
- Token.json file exists but is empty
- Application should handle empty file
- Should treat as no token present
- User should be prompted to sign in again

### Scenario: Token file permission denied
- Token.json file exists but cannot be read (permission denied)
- Application should handle IOError
- Should log error appropriately
- User should be prompted to sign in again

### Scenario: Token file missing
- Token.json file does not exist
- Application should detect missing file
- User should be prompted to sign in
- needs_auth_setup() should return True

### Scenario: Token file write failure during refresh
- Token refresh succeeds but writing new token fails
- Application should handle write error
- Error should be logged
- Token refresh operation should be considered failed
- User may need to sign in again

## Token Security

### Scenario: Token file is gitignored
- Token.json should be in .gitignore
- Token should not be committed to version control
- Application should not expose token in logs

### Scenario: Token contains sensitive information
- Token file should contain only necessary OAuth data
- Sensitive information should not be exposed
- Token should not be logged in plain text

### Scenario: Token expiry handling
- Application should check token validity before use
- Should refresh token proactively if near expiry
- Should handle expiry gracefully during operations
