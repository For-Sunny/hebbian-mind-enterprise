# Security Policy

## About Hebbian Mind Enterprise Security

Hebbian Mind Enterprise was built with security as a core requirement. The codebase includes:

- **SQL Injection Prevention**: All database operations use parameterized queries
- **Input Validation**: Comprehensive validation with strict limits on all inputs
- **Dual-Write Integrity**: RAM writes verified against disk truth with automatic sync
- **Error Sanitization**: Sensitive data (paths, credentials) scrubbed from error messages
- **Non-Root Execution**: Docker containers run as non-privileged user (UID 1000)
- **Minimal Attack Surface**: Lean Alpine/slim base images with only required dependencies
- **Secure Defaults**: All optional integrations (FAISS, PRECOG) disabled by default

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x.x   | Active support |
| < 2.0   | Not supported |

## Reporting a Vulnerability

If you discover a security vulnerability in Hebbian Mind Enterprise, please report it privately.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### Contact

**Email**: glass@cipscorps.io
**Subject Line**: [SECURITY] Hebbian Mind Enterprise Vulnerability Report

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Affected versions
- Suggested fix (if you have one)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Resolution Timeline**: Provided after assessment

### What to Expect

1. We will acknowledge your report within 48 hours
2. We will investigate and assess the severity
3. We will work on a fix and coordinate disclosure timing with you
4. We will credit you in the security advisory (unless you prefer anonymity)

## Responsible Disclosure

We kindly request that you:

- Allow reasonable time for us to fix the issue before public disclosure
- Do not exploit vulnerabilities beyond proof of concept
- Do not access, modify, or delete other users' data
- Act in good faith to avoid privacy violations and service disruption

## Security Best Practices

When deploying Hebbian Mind Enterprise:

### Docker Security

1. **Run as non-root**: Containers already configured with user `hebbian` (UID 1000)
2. **Read-only filesystem**: Consider adding `--read-only` flag with writable volumes
3. **Network isolation**: Use Docker networks to isolate services
4. **Resource limits**: Set memory and CPU limits in docker-compose.yml

### Environment Variables

1. **Never commit .env files**: Add `.env` to `.gitignore`
2. **Use secrets management**: For production, use Docker secrets or vault
3. **Rotate credentials**: If using license keys, rotate them periodically

### Data Protection

1. **Encrypt volumes**: Use encrypted filesystem for `/data/hebbian_mind`
2. **Backup regularly**: Implement automated backups of persistent volumes
3. **Access control**: Restrict filesystem permissions on data directories

### Network Security

1. **No exposed ports**: Default configuration uses stdio (no network exposure)
2. **If using sockets**: Bind to localhost only, use firewall rules
3. **TLS/SSL**: If exposing over network, use TLS termination (nginx/traefik)

## Known Security Considerations

### SQLite WAL Mode

- Write-Ahead Logging (WAL) enabled for better concurrency
- WAL files (`-wal`, `-shm`) should be backed up with main database
- Checkpoint regularly to prevent unbounded WAL growth

### RAM Disk Mode

- Data in tmpfs is lost on container restart
- Dual-write ensures disk persistence
- Ensure adequate disk space for backup writes

### FAISS Tether Integration

- Socket communication is unauthenticated by default
- Use internal Docker networks only
- Do not expose FAISS socket to public internet

### PRECOG Integration

- Requires mounting external code into container
- Validate PRECOG source before mounting
- Consider using read-only volume mount

## Compliance

Hebbian Mind Enterprise can be configured to meet common compliance requirements:

- **GDPR**: Data minimization through configurable retention
- **SOC 2**: Audit logging of all operations (enable via LOG_LEVEL=DEBUG)
- **HIPAA**: Encryption at rest and in transit (configure externally)

Contact glass@cipscorps.io for compliance consultation.

## Security Updates

Security patches are released as soon as possible after confirmation. Subscribers receive:

- Email notification of security releases
- Detailed changelog with CVE references (if applicable)
- Migration guides for breaking security fixes

## Contact

- **Security Issues**: glass@cipscorps.io
- **General Support**: contact@cipscorps.com
- **Documentation**: https://docs.cipscorps.com/hebbian-mind

---

*CIPS LLC - https://cipscorps.io*
