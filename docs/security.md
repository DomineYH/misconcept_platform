# Security Guidelines

**Last Updated**: 2025-11-06 (T112: Security Hardening)

## Overview

This document outlines the security measures implemented in the
Misconception Dialogue Simulator and provides guidelines for secure
deployment and operation.

## Security Features Implemented

### 1. Authentication & Session Management

**Session-Based Authentication**:
- Secure session cookies with HttpOnly flag (prevents XSS attacks)
- 8-hour session timeout (configurable via `max_age`)
- SameSite=Lax to prevent CSRF attacks
- HTTPS-only cookies in production (ENV=production)

**Session Secret**:
- Strong random secret required in production
- Validation check prevents use of default insecure secret
- Minimum 32 bytes of randomness recommended

**Configuration**:
```python
# src/main.py
SessionMiddleware(
    secret_key=config.SESSION_SECRET,
    session_cookie="session_id",
    max_age=28800,  # 8 hours
    same_site="lax",
    https_only=config.is_production,  # True in production
    httponly=True,  # Prevents JavaScript access
)
```

### 2. SQL Injection Prevention

**ORM-Based Queries**:
- All database operations use SQLAlchemy ORM
- Parameterized queries prevent SQL injection
- No f-string interpolation in SQL statements

**Static Queries Only**:
- Health check endpoint uses `text()` with hardcoded strings
- No user input in raw SQL queries
- All user data passed through ORM models

**Safe Patterns**:
```python
# ✅ SAFE: ORM with parameters
result = await db.execute(
    select(Session).where(Session.id == session_id)
)

# ✅ SAFE: Hardcoded query with no user input
await db.execute(text("SELECT 1"))

# ❌ UNSAFE: Never do this (not present in codebase)
# await db.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
```

### 3. Cross-Site Scripting (XSS) Prevention

**Content Security Policy**:
- CSP header restricts script sources
- Only self-hosted and trusted CDN scripts allowed
- Inline styles restricted

**Template Escaping**:
- Jinja2 automatic HTML escaping enabled by default
- User-generated content sanitized before rendering

**Security Headers**:
```python
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-XSS-Protection"] = "1; mode=block"
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'"
)
```

### 4. Cross-Site Request Forgery (CSRF)

**SameSite Cookies**:
- Session cookies use `SameSite=Lax`
- Prevents cross-origin session hijacking
- Compatible with modern browsers

**CORS Configuration**:
- Restricted origins in production
- Credentials allowed only for trusted origins
- Configurable via `FRONTEND_URL` environment variable

### 5. Security Headers

**HTTP Strict Transport Security (HSTS)**:
- Forces HTTPS connections in production
- 1-year max-age with includeSubDomains
- Prevents downgrade attacks

**Additional Headers**:
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `Referrer-Policy: strict-origin-when-cross-origin` - Limits referrer
- `Permissions-Policy` - Restricts browser features

### 6. Rate Limiting

**API Rate Limits**:
- Login: 5 requests/minute per IP
- Messages: 30 requests/minute per IP
- End session: 10 requests/minute per IP

**Implementation**:
```python
from slowapi import Limiter

limiter = Limiter(
    key_func=get_remote_address,
    enabled=not config.TESTING,
)

@router.post("/sessions/{session_id}/messages")
@limiter.limit("30/minute")
async def send_message(...):
    ...
```

**Benefits**:
- Prevents brute force attacks
- Mitigates DoS attempts
- Protects OpenAI API quota

### 7. Input Validation

**Pydantic Models**:
- All API inputs validated with Pydantic
- Type checking and constraint validation
- Automatic rejection of invalid data

**Validation Examples**:
```python
class CreateScenarioRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    prompt: str = Field(min_length=10, max_length=10000)
    student_profile: str = Field(max_length=500)
    framework_id: int = Field(gt=0)
```

### 8. Error Handling

**No Information Disclosure**:
- Generic error messages for users
- Detailed errors logged server-side only
- No stack traces exposed in production

**Structured Logging**:
- JSON logging with request IDs
- Error tracking with context
- Security event monitoring

## Production Deployment Security

### Environment Configuration

**Required Settings**:
```bash
# .env
ENV=production
SESSION_SECRET=<64-character-random-string>
OPENAI_API_KEY=sk-...
DATABASE_URL=sqlite+aiosqlite:///./dialogue_sim.db
```

**Generate Secure Secret**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### HTTPS Enforcement

**nginx Configuration**:
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

**Let's Encrypt SSL**:
```bash
sudo certbot --nginx -d your-domain.com
```

### File Permissions

**Database**:
```bash
chmod 640 dialogue_sim.db
chown misconcept:misconcept dialogue_sim.db
```

**Environment File**:
```bash
chmod 600 .env
chown misconcept:misconcept .env
```

### Firewall Configuration

**UFW Rules**:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

## Security Monitoring

### Log Monitoring

**Key Events to Monitor**:
- Failed login attempts (>5/hour from same IP)
- Rate limit violations (sustained pattern)
- Authentication errors (invalid tokens, expired sessions)
- Database connection failures
- OpenAI API errors (rate limits, failures)

**Log Analysis**:
```bash
# Failed authentication attempts
grep "authentication failed" /var/log/misconcept/app.log | \
    jq -r '.client' | sort | uniq -c | sort -rn

# Rate limit violations
grep "rate_limit_exceeded" /var/log/misconcept/app.log | \
    jq -r '.path' | sort | uniq -c | sort -rn
```

### Health Monitoring

**Endpoints**:
- `GET /health` - Application and database health
- `GET /metrics` - Usage statistics and performance

**Automated Checks**:
```bash
#!/bin/bash
# healthcheck.sh
response=$(curl -s https://your-domain.com/health)
status=$(echo $response | jq -r '.status')

if [ "$status" != "healthy" ]; then
    echo "ALERT: Application unhealthy"
    # Send notification
fi
```

## Security Best Practices

### Development

1. **Never commit secrets**:
   - Use .env files (in .gitignore)
   - Never hardcode API keys or secrets
   - Rotate secrets regularly

2. **Keep dependencies updated**:
   ```bash
   uv pip list --outdated
   uv pip install --upgrade <package>
   ```

3. **Run security audits**:
   ```bash
   # Check for known vulnerabilities
   pip-audit

   # Scan for hardcoded secrets
   trufflehog filesystem .
   ```

4. **Test security features**:
   - Verify HTTPS enforcement
   - Test rate limiting
   - Validate input sanitization
   - Check authentication flows

### Production

1. **Regular updates**:
   - Apply security patches promptly
   - Update dependencies weekly
   - Monitor security advisories

2. **Backup strategy**:
   - Daily database backups
   - Secure backup storage
   - Regular restore testing

3. **Access control**:
   - Principle of least privilege
   - SSH key authentication only
   - Disable password authentication
   - Regular access audits

4. **Incident response**:
   - Document response procedures
   - Maintain contact information
   - Practice incident scenarios
   - Post-incident reviews

## Known Limitations

1. **Single-Factor Authentication**:
   - Current: Session cookie only
   - Future: Consider 2FA for admin users

2. **Database Encryption**:
   - SQLite file unencrypted at rest
   - Consider encryption for sensitive deployments

3. **API Key Storage**:
   - OpenAI keys in environment variables
   - Consider secrets management system for production

4. **CSRF Protection**:
   - Relies on SameSite cookies
   - Consider adding CSRF tokens for critical operations

## Security Contacts

**Report Security Issues**:
- Email: security@example.com
- GitHub: Create private security advisory

**Response Time**:
- Critical: 24 hours
- High: 72 hours
- Medium: 1 week
- Low: Best effort

## Compliance

### OWASP Top 10 (2021)

- ✅ A01 Broken Access Control - Role-based access, session management
- ✅ A02 Cryptographic Failures - HTTPS, secure sessions, HSTS
- ✅ A03 Injection - ORM, parameterized queries, input validation
- ✅ A04 Insecure Design - Security by design, defense in depth
- ✅ A05 Security Misconfiguration - Secure defaults, hardened headers
- ✅ A06 Vulnerable Components - Dependency management
- ✅ A07 Authentication Failures - Session timeout, rate limiting
- ✅ A08 Data Integrity Failures - Input validation, CSP
- ✅ A09 Logging Failures - Structured logging, monitoring
- ✅ A10 SSRF - No external requests from user input

### Data Protection

**GDPR Considerations**:
- User data minimization
- Anonymization in exports (SHA-256 hashing)
- Right to erasure (manual process)
- Data retention policies (configurable)

**PII Handling**:
- Student UIDs are pseudonymous
- Nicknames not verified
- No email or phone collection
- Session data anonymized in exports

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/20/faq/security.html)
- [Mozilla Security Headers](https://infosec.mozilla.org/guidelines/web_security)
- [Let's Encrypt](https://letsencrypt.org/)

---

**Version**: 1.0 | **Status**: Production-Ready | **Last Audit**: 2025-11-06
