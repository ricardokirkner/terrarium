# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in Terrarium, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.** Instead, please email:

```
ricardo@kirkner.com.ar
```

Include the following information in your report:

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact and severity
- Your suggested fix (if any)

## Response Timeline

We aim to:

1. Acknowledge your report within 48 hours
2. Provide an initial assessment within 1 week
3. Release a fix within 2-4 weeks (depending on complexity)
4. Credit you in the security advisory (unless you prefer to remain anonymous)

## Security Considerations

### Known Limitations

- **Early-stage software**: Terrarium v0.1.0 is in active development. The event boundary is v0 and subject to breaking changes.
- **No cryptographic guarantees**: Vivarium and Treehouse do not provide security guarantees for sensitive data processing.
- **Input validation**: Applications using Terrarium should validate all inputs before passing to behavior trees.

### Best Practices

When using Terrarium in your applications:

1. **Input Validation**: Validate and sanitize all inputs to behavior trees
2. **State Management**: Be cautious with sensitive data in the State object
3. **Error Handling**: Implement proper error handling for edge cases
4. **Dependency Updates**: Keep Treehouse dependencies (FastAPI, uvicorn, websockets) up to date
5. **Access Control**: Restrict access to the Treehouse visualizer in production environments

### Deserialization

Treehouse can deserialize execution traces. Only load traces from trusted sources, as malicious traces could potentially cause issues.

## Supported Versions

| Version | Status | Security Updates |
|---------|--------|-------------------|
| 0.1.0   | Current | Yes              |
| < 0.1.0 | N/A    | N/A              |

## Security Advisories

None published yet. Check this page for updates.

---

**Thank you for helping keep Terrarium secure!**
