# Roadmap

## v0.1.0 beta candidate
- Docker setup and lifecycle scripts
- PayOS-only payment and balance flows
- Editable operator identity
- Public documentation and release gates

Release remains blocked pending:

- [ ] Seven clean-host acceptance rehearsals covering setup/health, both PayOS payment flows, balance payment, live settings, destructive restore, and update recovery.
- [ ] Explicit operator confirmation that every credential ever committed to private history has been revoked or rotated.
- [ ] Blocking CI passing in the clean single-commit public repository.

## v1.0.0
- One stable operating cycle
- No unresolved installation, payment, update, backup, or restore blocker

## After v1
1. Stabilize supplier workflows before adding an opt-in Compose profile.
2. Publish signed multi-architecture images.
3. Add an optional reverse-proxy/TLS profile.
4. Add guided credential rotation and audited admin recovery.
5. Add migration previews and supported release channels when usage warrants them.
