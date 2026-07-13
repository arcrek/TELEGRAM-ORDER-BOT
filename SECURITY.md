# Security Policy

## Supported versions

Only the latest published release receives security fixes.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for this repository. Do not open a
public issue for an undisclosed vulnerability and do not include credentials,
customer records, delivery inventory, or payment payloads in reports.

Include the affected version, reachable attack path, impact, reproduction
steps, and a suggested remediation when available. Maintainers acknowledge a
report within seven calendar days and coordinate disclosure after a fix is
available.

## Secret handling

Never commit `.env`, database dumps, backups, Telegram tokens, PayOS keys, JWT
keys, customer data, or delivery inventory. Rotate a credential immediately if
it enters Git history; deleting the current file is not sufficient.
