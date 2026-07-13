# Dashboard frontend

React 18 and TypeScript dashboard for Bot Order System. Production builds are served by the supported `frontend` Compose service and call the FastAPI `api` service.

Use the root [Installation](../docs/INSTALLATION.md) and [Configuration](../docs/CONFIGURATION.md) guides for deployment. Do not create a second frontend installation path here. `VITE_API_BASE_URL` is a public build-time value; changing it requires rebuilding the frontend through `./manage.sh restart` from the repository root.

## Development commands

Run from this directory after installing the lockfile dependencies:

```bash
npm ci
npm run dev
npm test -- --run
npm run lint
npm run build
```

The dashboard supports Vietnamese and English catalogs under `src/i18n/locales/`. Keep API calls in the shared client, preserve role-based navigation, and add focused Vitest coverage for changed behavior.

See [Architecture](../docs/ARCHITECTURE.md), [Contributing](../CONTRIBUTING.md), and [Operations](../OPERATIONS.md) for the authoritative system boundaries.
