
## Authentication & Security Audit Architecture

This backend implements robust credential handling and verification to satisfy strict security engineering standards:

1. **One-Way Password Hashing (`scrypt`)**: 
   Passwords are never stored in plaintext. The `User` model leverages Werkzeug's `generate_password_hash()` (utilizing secure `scrypt` parameters) upon registration via `set_password()`.
2. **Anti-Enumeration Login Responses**: 
   Login failures return a generic `"Invalid username or password"` error message with an HTTP `401 Unauthorized` status code for both nonexistent accounts and incorrect passwords, preventing user harvesting.
3. **Audit Verification Endpoint**: 
   An evidence-only route (`GET /audit/users`) exposes `to_evidence_dict()` to verify that database records store cryptographic hashes rather than raw strings.

### Verification & Testing Transcripts

- **Successful Registration (`201 Created`)**:
  ```bash
  curl -X POST [http://127.0.0.1:5000/auth/register](http://127.0.0.1:5000/auth/register) \
    -H "Content-Type: application/json" \
    -d '{"username": "test_auditor", "password": "securepassword123"}'
Credential Verification (200 OK vs 401 Unauthorized):
Correct passwords return token verification success; incorrect passwords return consistent 401 status codes.

Audit Storage Inspection (GET /audit/users):
Returns records containing password_hash strings starting with scrypt:32768:....
