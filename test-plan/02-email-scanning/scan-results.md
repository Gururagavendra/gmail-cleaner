# Scan Results Test Scenarios

## Result Structure

### Scenario: Scan results contain required fields
- Scan completes successfully
- Each result should contain: domain, link, count, type, sender, email
- Results should be properly structured
- All fields should be populated with valid data

### Scenario: Scan results domain grouping
- Multiple emails from same domain
- Results should group by domain (email domain)
- Count should show total emails per domain
- Each domain should appear once in results

### Scenario: Scan results count accuracy
- Results show count of emails per domain
- Count should match actual number of emails scanned
- Count should be accurate

### Scenario: Scan results unsubscribe link extraction
- Emails contain List-Unsubscribe headers
- Links should be extracted correctly
- HTTP/HTTPS links should be preferred over mailto
- Links should be properly formatted URLs

### Scenario: Scan results unsubscribe type detection
- Emails with List-Unsubscribe-Post header
- Type should be "one-click"
- Emails with only List-Unsubscribe header
- Type should be "manual"

### Scenario: Scan results sender name extraction
- From header contains name and email
- Sender name should be extracted correctly
- Should handle various name formats (quoted, unquoted, with special characters)

### Scenario: Scan results sender email extraction
- From header contains email address
- Email should be extracted correctly
- Should handle email in angle brackets
- Should handle email-only format

### Scenario: Scan results subject samples
- Multiple emails from same sender
- Results should include up to 3 sample subjects
- Subjects should be from different emails
- Should show representative samples

### Scenario: Scan results date information
- Results include first_date and last_date
- First date should be earliest email from domain
- Last date should be most recent email from domain
- Dates should be extracted from email Date headers

## Result Ordering and Sorting

### Scenario: Scan results order
- Results should be ordered consistently
- Order should be deterministic
- Should be sortable by count or domain

### Scenario: Scan results with many domains
- Scan finds emails from many different domains
- All domains should appear in results
- Results list should contain all found domains
- No domains should be missing

## Empty and Edge Cases

### Scenario: Scan results when no emails found
- Scan finds no emails matching criteria
- Results should be empty list
- GET /api/results should return []
- Should not cause errors

### Scenario: Scan results when no unsubscribe links found
- Emails scanned but none have unsubscribe links
- Results should be empty list
- Scan should complete successfully
- Status should indicate completion

### Scenario: Scan results with malformed headers
- Some emails have malformed From headers
- Application should handle gracefully
- Should extract available information
- Should not crash on malformed data

### Scenario: Scan results with missing headers
- Some emails missing From or Date headers
- Application should handle missing headers
- Should use defaults or skip invalid entries
- Results should still be generated

## Result Retrieval

### Scenario: Get scan results endpoint
- GET /api/results should return current scan results
- Should return list of results
- Should return empty list if no scan performed
- Should not trigger new scan

### Scenario: Get scan results after scan completes
- Scan operation completes
- GET /api/results should return final results
- Results should be complete and accurate
- All found domains should be included

### Scenario: Get scan results during active scan
- Scan is in progress
- GET /api/results should return partial results
- Results should update as scan progresses
- Should show domains found so far

### Scenario: Get scan results after new scan starts
- Previous scan results exist
- New scan is initiated
- Previous results should be cleared
- GET /api/results should return empty list until new results available

## Result Data Quality

### Scenario: Scan results with special characters
- Email addresses or domains contain special characters
- Results should handle special characters correctly
- URLs should be properly encoded if needed
- Display should be correct

### Scenario: Scan results with unicode characters
- Sender names or subjects contain unicode
- Results should handle unicode correctly
- Should not cause encoding errors
- Display should preserve characters

### Scenario: Scan results link validation
- Unsubscribe links in results
- Links should be valid URLs
- Should be properly formatted
- Should be accessible (HTTP/HTTPS or mailto)

### Scenario: Scan results count consistency
- Count in results matches actual emails
- Count should be accurate
- Should not include duplicates incorrectly
- Should reflect actual emails scanned
