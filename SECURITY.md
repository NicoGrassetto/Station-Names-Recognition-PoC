# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

We take the security of this project seriously. If you discover a security
vulnerability, please report it responsibly.

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please report them via one of the following methods:

1. **GitHub Private Vulnerability Reporting**: Use the
   [Security Advisories](../../security/advisories) feature to report the
   vulnerability privately.

2. **Email**: Send a detailed report to **ngrassetto@microsoft.com**.

### What to Include

- A description of the vulnerability and its potential impact.
- Steps to reproduce the issue.
- Any relevant logs, screenshots, or proof-of-concept code.
- Your suggested fix (if any).

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within
  **48 hours**.
- **Assessment**: We will investigate and provide an initial assessment within
  **7 days**.
- **Resolution**: We aim to release a fix for critical vulnerabilities within
  **30 days** of confirmation.
- **Credit**: With your permission, we will credit you in the security advisory.

## Security Best Practices for Users

When deploying this starter kit:

- **Never commit secrets**: Do not commit API keys, connection strings, or
  credentials to the repository. Use environment variables or Azure Key Vault.
- **Use RBAC**: The included Bicep templates configure role-based access control.
  Do not use API key authentication in production.
- **Keep dependencies updated**: Regularly run `pip audit` and `npm audit` to
  check for known vulnerabilities.
- **Restrict network access**: In production, configure firewalls and private
  endpoints for Azure OpenAI resources.
