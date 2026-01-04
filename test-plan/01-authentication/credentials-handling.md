# Credentials Handling Test Scenarios

## Credentials File Management

### Scenario: Valid credentials.json file exists
- credentials.json file is present and valid
- Application should detect file
- _get_credentials_path() should return file path
- OAuth flow should use credentials from file

### Scenario: Missing credentials.json file
- credentials.json file does not exist
- Application should detect missing file
- Should check for GOOGLE_CREDENTIALS environment variable
- If env var also missing, should return None
- get_gmail_service() should return error message about missing credentials

### Scenario: Invalid credentials.json file format
- credentials.json file exists but contains invalid JSON
- Application should fail when trying to load credentials
- OAuth flow should fail with appropriate error
- Error should be caught and logged

### Scenario: Malformed credentials.json structure
- credentials.json file exists but missing required OAuth fields
- InstalledAppFlow.from_client_secrets_file() should raise error
- Error should be handled gracefully
- User should see appropriate error message

### Scenario: Credentials file with wrong OAuth client type
- credentials.json file contains wrong client type (web vs desktop)
- OAuth flow may fail or behave unexpectedly
- Application should handle error appropriately

## Environment Variable Credentials

### Scenario: Credentials from GOOGLE_CREDENTIALS environment variable
- credentials.json file does not exist
- GOOGLE_CREDENTIALS environment variable is set with valid JSON
- Application should create credentials.json from env var
- File should be created successfully
- OAuth flow should use created credentials file

### Scenario: GOOGLE_CREDENTIALS with invalid JSON
- GOOGLE_CREDENTIALS environment variable contains invalid JSON
- File creation should fail
- Application should handle error appropriately
- Should not create corrupted credentials file

### Scenario: GOOGLE_CREDENTIALS with empty value
- GOOGLE_CREDENTIALS environment variable is empty string
- Application should create empty or invalid file
- OAuth flow should fail appropriately

### Scenario: Credentials file takes precedence over environment variable
- Both credentials.json file and GOOGLE_CREDENTIALS env var exist
- Application should prefer credentials.json file
- Environment variable should be ignored
- OAuth flow should use file credentials

## Credentials File Operations

### Scenario: Credentials file read permission denied
- credentials.json file exists but cannot be read
- Application should handle permission error
- Error should be logged
- User should see appropriate error message

### Scenario: Credentials file write error from env var
- GOOGLE_CREDENTIALS env var exists
- Attempting to write credentials.json fails (disk full, permission denied)
- Application should handle write error
- Should not proceed with invalid credentials
- Error should be logged

### Scenario: Credentials file location
- credentials.json should be in application root directory
- Path should match settings.credentials_file
- Application should use correct path

## Credentials Validation

### Scenario: Credentials with valid client ID and secret
- credentials.json contains valid OAuth client credentials
- Application should successfully initialize OAuth flow
- Flow should proceed normally

### Scenario: Credentials with missing client ID
- credentials.json missing client ID
- OAuth flow initialization should fail
- Error should be clear and actionable

### Scenario: Credentials with missing client secret
- credentials.json missing client secret
- OAuth flow initialization should fail
- Error should be clear and actionable

### Scenario: Credentials with invalid redirect URIs
- credentials.json contains invalid redirect URI configuration
- OAuth flow may fail during callback
- Error should be handled appropriately

## Web Auth Mode Credentials

### Scenario: Web application credentials in Docker mode
- Application running with WEB_AUTH=true
- Should use Web application type credentials
- Redirect URI should match configured OAUTH_HOST
- OAuth flow should complete successfully

### Scenario: Desktop app credentials in local mode
- Application running locally without WEB_AUTH
- Should use Desktop app type credentials
- OAuth flow should use localhost redirect
- OAuth flow should complete successfully

### Scenario: Mismatched credentials type for deployment
- Web application credentials used in local desktop mode
- May cause redirect URI mismatch errors
- Application should handle error appropriately
- User should be informed of credential type requirement

## Security Considerations

### Scenario: Credentials file is gitignored
- credentials.json should be in .gitignore
- Credentials should not be committed to version control
- Application setup instructions should warn users

### Scenario: Credentials file permissions
- credentials.json should have appropriate file permissions
- Should not be world-readable if possible
- Application should handle permission issues

### Scenario: Credentials not exposed in logs
- Credentials should not be logged or printed
- Application should avoid exposing sensitive data
- Error messages should not include credential details
