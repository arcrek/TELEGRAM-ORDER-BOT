# Dashboard Rebuild — UI/UX Pro Max

## Context

The MTK Bot Order admin dashboard (`frontend/`, React 18 + TS + Vite) works but is visually thin and ergonomically rough: a horizontal top-nav, no sidebar, hardcoded colors and `vi-VN` locales scattered across pages, `alert()`/`window.confirm()` for user feedback, no shared `Modal`/`Toast`/`Table`/`Skeleton`/`Pagination`, "Loading..." text instead of skeletons, three duplicated scrollbar blocks in `App.css`, and only three Chart.js charts on Statistics — pie/line/bar with hardcoded colors that ignore the theme. The user wants a complete rebuild that "enhances experience and visualizes" data.

Driving the design via the `ui-ux-pro-max` skill: a **Data-Dense Dashboard + Bento Grid** layout on a **Dark Mode (OLED)** base, with the **Dashboard Data** typography pairing (Fira Sans UI + Fira Code numerals). Goals: a real shell (sidebar + topbar + cmd-k), a complete component library, theme-aware charts, richer visualizations (funnel, heatmap, sparklines, MoM deltas), URL-synced filters/pagination on every list page, full a11y and `prefers-reduced-motion` compliance, and Vietnamese as the i18n default.

Decisions confirmed up front: **full 12-page rebuild**, **sidebar + topbar shell**, **backend extensions are allowed**, **Vietnamese default with English fallback**.

## Critical files

**New (foundation)**
- `frontend/src/styles/tokens.css` — single source of truth for all design tokens
- `frontend/src/styles/base.css` — resets, scrollbar (deduped), focus styles
- `frontend/src/styles/fonts.css` — Fira Sans + Fira Code wiring
- `frontend/src/app/router.tsx` — central route table (path/key/label/icon/role)
- `frontend/src/app/providers.tsx` — Theme + Auth + i18n + Toast composition
- `frontend/src/app/layouts/AppShell.tsx` + `Sidebar.tsx` + `Topbar.tsx` + `Breadcrumb.tsx` + `MobileDrawer.tsx` + `UserMenu.tsx` + `CommandPalette.tsx`
- `frontend/src/shared/lib/charts.ts` — `getChartTheme()`, `applyChartDefaults()`, `useChartOptions()`
- `frontend/src/shared/lib/format.ts` — `formatCurrency/Number/Percent/Date/DateTime/Relative` + `useFormat()`
- `frontend/src/shared/lib/api.ts` — single axios instance with token + 401 interceptor
- `frontend/src/shared/hooks/` — `useDebounce`, `useDisclosure`, `useMediaQuery`, `useHotkey`, `useFocusTrap`, `useDismiss`, `useRovingTabindex`, `useFloatingPosition`, `useCombobox`, `useUrlState`, `useApi`, `useMutation`
- `frontend/src/shared/components/<Name>/` for each new primitive (see §3)

**Rewritten**
- `frontend/src/styles/theme.ts` → moves into `ThemeContext`; deleted afterwards
- `frontend/src/contexts/ThemeContext.tsx` → adds `'system'` mode, `resolvedTheme`, drives `data-theme` only
- `frontend/src/i18n/config.ts` → `fallbackLng:'vi'`, namespace split (14 namespaces)
- `frontend/src/i18n/locales/{vi,en}/dashboard.json` → split into per-feature files

**Deleted**
- `frontend/src/App.css` (split into `tokens.css` + `base.css`)
- `frontend/src/layouts/DashboardLayout.tsx` + `.css`

**Rebuilt page-by-page** (under `frontend/src/features/<feature>/`)
- LoginPage, StatisticsPage, OrdersPage, ProductsPage, ProductUploadPage, VariationsPage, PreUploadedPage, BonusSummaryPage, BotUiSettingsPage, IotdPage, NotificationsPage, SuppliersPage (re-enabled)

**Backend (limited extensions)**
- `src/dashboard/routers/statistics.py` — extend `GET /api/statistics/overview` with `range` query, `funnel`, `orders_heatmap`, `revenue_delta`/`orders_delta`, `recent_orders`; add `GET/PUT /api/statistics/goals` for monthly target.
- `src/dashboard/routers/suppliers.py` — extend supplier statistics with `avg_response_seconds`, `outcome_breakdown`.
- `src/dashboard/routers/iotd.py` — add `GET /api/iotd/history` (last 7), optional `POST /api/iotd/upload` for direct upload.
- `src/dashboard/routers/bonus_tiers.py` — add `GET /api/bonus-tiers/coverage` for tier hit-rate aggregation.
- `src/dashboard/routers/notifications.py` — add `GET /api/notifications/history` for the History tab; optional `schedule_at` field on broadcast.
- Migrations through Alembic for any persisted fields (`statistics_goal` table, schedule fields).

## Plan

### 1. Foundation: tokens, fonts, theme, i18n

**1.1 Tokens** — replace `App.css` `:root` block with a comprehensive `tokens.css`:

- **Surfaces** (3 layers): `--bg-page`, `--bg-surface`, `--bg-raised`, `--bg-sunken`.
- **Borders**: `--border-subtle`, `--border-strong`, `--border-focus`.
- **Text**: `--text-primary`, `--text-secondary`, `--text-muted`, `--text-disabled`, `--text-inverted`, `--text-link`.
- **Brand**: `--brand-{50,100,500,600,700}` anchored on `#4B82FF` (light) / `#6EA8FF` (dark).
- **Semantic**: `--{success,warning,danger,info}-{50,500,600}`.
- **Data viz palette**: `--viz-1..8` (8 categorical colors validated for both modes).
- **Status enums** (matches backend `OrderStatus`): `--status-{pending,paid,processing,delivered,cancelled}-{bg,fg}`.
- **Shadows**: `--shadow-{none,sm,md,lg}` tuned per theme.
- **Radius**: `--radius-{sm,md,lg,xl,full}` (6/10/14/20/9999).
- **Spacing**: `--space-1..10` on the 4-px scale.
- **Density**: `--header-height:56px`, `--sidebar-width:240px`, `--sidebar-width-collapsed:64px`, `--table-row-height:36px`, `--table-row-height-dense:28px`, `--grid-gap:16px`, `--card-padding:16px`.
- **Z-index scale**: `--z-{dropdown:1000,sticky:1100,fixed:1200,modal-backdrop:1300,modal:1400,popover:1500,toast:1600}`.
- **Motion**: `--duration-{fast:120ms,base:180ms,slow:280ms}`, `--easing-{standard,emphasized}`.

Both light and dark sets are defined; `[data-theme='dark']` only overrides — no runtime `style.setProperty`. Light-mode glass-card visibility fix is now central: `.card { background: var(--bg-surface); border:1px solid var(--border-subtle); box-shadow: var(--shadow-sm); }`.

**1.2 Fonts** — install `@fontsource/fira-sans` (400/500/600 + `vietnamese` subset) and `@fontsource/fira-code` (400/500). Self-hosted: deterministic builds, offline Docker, no CDN race. Imported in `main.tsx`. `--font-sans` and `--font-mono` set in `fonts.css`. Mono used for table numbers, IDs, timestamps, `StatCard` value (`font-variant-numeric: tabular-nums`).

**1.3 Type scale** — `--text-{xs:11,sm:12,base:14,lg:16,xl:18,2xl:22,3xl:28}` with paired `--lh-*` and `--tracking-{tight,normal,wide}`.

**1.4 Theme provider** — rewrite `ThemeContext` with `theme: 'light'|'dark'|'system'`, persisted, plus `resolvedTheme` derived from `matchMedia('(prefers-color-scheme: dark)')`. Sets `data-theme={resolvedTheme}` only. On change calls `applyChartDefaults()` so Chart.js re-themes.

**1.5 i18n** — `fallbackLng:'vi'`, supportedLngs `['vi','en']`. One-time bootstrap: if `localStorage.i18nextLng` is unset, seed `'vi'`. Split flat `dashboard.json` into namespaces: `common`, `nav`, `auth`, `statistics`, `products`, `orders`, `variations`, `inventory`, `bonus`, `botUi`, `upload`, `iotd`, `notifications`, `suppliers`, `validation`, `formats`. All `vi-VN` hardcodes are removed; date/number/currency formatting flows through `useFormat()` which reads the active locale.

**1.6 API client + auth** — single axios instance in `shared/lib/api.ts` (replaces ad-hoc `localStorage.getItem('token')` everywhere). Request interceptor injects bearer; response interceptor on 401 → `logout()` + redirect to `/login` + `toast.error(t('auth.session.expired'))`.

### 2. Layout shell

Replace `DashboardLayout` with a CSS-grid `AppShell`:

```
.app-shell { display:grid;
  grid-template-columns: var(--sidebar-width) 1fr;
  grid-template-rows: var(--header-height) 1fr;
  grid-template-areas: "sidebar topbar" "sidebar main"; min-height:100vh; }
.app-shell[data-collapsed='true'] { grid-template-columns: var(--sidebar-width-collapsed) 1fr; }
@media (max-width:900px) { ... single column, sidebar becomes drawer }
```

**Sidebar** (`Sidebar.tsx`) — logo, grouped nav, collapse toggle pinned bottom. Persists collapsed state to `localStorage('sidebar-collapsed')`.

Groups:
- **Overview**: Statistics
- **Catalog**: Products, Variations, IOTD
- **Operations**: Orders, Notifications, Product Upload, Pre-uploaded, Bonus Summary, Suppliers
- **Settings**: Bot UI Settings

**Topbar** (`Topbar.tsx`) — `Breadcrumb` (left), `Button` "Search…" (`⌘K` opens `CommandPalette`), `LanguageSelector`, `ThemeToggle`, `UserMenu` (avatar + dropdown).

**CommandPalette** (`⌘K`) — v1 = route navigation only. Hand-rolled `Modal`-style overlay with input + filtered route list + arrow-key nav. Future-extension hook for global resource search.

**MobileDrawer** — `<768px`: sidebar slides in over backdrop; topbar shows hamburger.

**Routes mapped from a single `routes.ts`** so Sidebar, Breadcrumb and CommandPalette all read the same source.

### 3. Component library

Each under `frontend/src/shared/components/<Name>/` with `index.ts`, `<Name>.tsx`, `<Name>.css`, `<Name>.test.tsx`.

**Atoms** — `Button` (extend: `loading`, `iconLeft`, `iconRight`, `iconOnly`, `tone:'solid'|'subtle'|'ghost'|'link'`, `variant:'primary'|'secondary'|'destructive'`, `aria-busy` while loading), `IconButton` (44×44 hit target, `aria-label` required, optional `tooltip`), `Input` (extend: `leftIcon`, `rightIcon`, `clearable`, `helperText`, `error`, `prefix`, `suffix`, `inputMode`), `Textarea` (autosize via `useAutosize`), `Select` (combobox with keyboard nav + type-to-search via `useCombobox`), `Checkbox`, `Radio`, `Switch`, `Spinner` (CSS-only, respects `prefers-reduced-motion`).

**Molecules** — `FormField` (label + helper + error, wires `aria-describedby`), `Badge` (semantic + status enum + size, optional dot), `Skeleton` (line/circle/rect, `animate-pulse` with reduced-motion fallback), `EmptyState` (icon + title + description + CTA), `Tooltip` (hand-rolled via `useFloatingPosition`), `Popover`, `DropdownMenu` (focus trap + click-outside + roving tabindex), `Tabs` (arrow-key nav, lazy panels), `Pagination` (page input + jump-to + per-page selector), `FileDrop` (drag/drop + paste + mime/size guard), `DateRangePicker` (lightweight hand-rolled grid + presets: Today / 7d / 30d / This month / Last month / Custom), `StatCard` (label + mono value + delta `Badge` + sparkline SVG + icon + loading state), `ChartCard` (header with title/range/export, body with skeleton, footer with caption), `PageHeader` (breadcrumb + title + description + actions slot), `Card` (kept).

**Organisms** — `Modal` (full prop signature: `open`, `onClose`, `size:'sm'|'md'|'lg'|'xl'|'full'`, `title`, `description`, `children`, `footer`, `initialFocusRef`, `closeOnBackdrop`, `closeOnEsc`, `preventScroll`, `ariaLabelledBy`, `ariaDescribedBy`, `hideCloseButton`, `stickyHeader`, `stickyFooter`; portal + custom focus trap; hard cutover of `.modal-overlay` ad-hoc divs across pages), `ConfirmDialog` (Promise-based via `useConfirm()`; replaces every `window.confirm` and `alert` audited in 8 pages), `Toast` + `ToastProvider` (top-right stack, 4 variants, 5s default, action slot, pausable on hover, separate `aria-live='polite'`/`'assertive'` regions for status vs. alert), `Table` (full prop signature with `ColumnDef<T>`: `id`, `header`, `accessor`, `cell`, `sortable`, `sortFn`, `filter`, `width`, `minWidth`, `align`, `sticky`, `mono`, `hidden`; supports server-side sort/filter/pagination, selection, expansion, sticky header, density toggle, skeleton rows, empty state slot, semantic `<table>` with `<th aria-sort>`).

**Lint rule** — add ESLint `no-restricted-globals: ['alert','confirm','prompt']` to prevent regressions.

### 4. Statistics page (the visualization centerpiece)

Bento layout:

```
PageHeader: title • DateRangePicker • Refresh • Export
+----------------------------------------------------------+
| KPI row (4–6 StatCards: revenue, orders, sold, avg-order, conversion%, week-summary) — each with sparkline + delta |
+--------------------------+----------------+--------------+
| Revenue trend (Line+Area | Status donut   | IOTD card    |
| Tabs: Daily/Weekly/Mo)   | center label   | image + Edit |
+--------------------------+----------------+--------------+
| Conversion funnel (NEW)  | Hour×Weekday heatmap (NEW)    |
+--------------------------+--------------------------------+
| Top products (h-bar top 10) | Activity feed (last 10)    |
+-----------------------------+-----------------------------+
```

Charts:
- **Sparklines** — inline SVG, 7-day per KPI.
- **Revenue trend** — Line+Area, granularity tabs, theme-aware via `useChartOptions()`.
- **Status donut** — replaces existing pie; click slice filters Activity feed.
- **Top products** — horizontal bar, sorted desc, top 10.
- **Conversion funnel** (NEW) — pending → paid → processing → delivered with per-stage % and absolute counts.
- **Hour×Weekday heatmap** (NEW) — 24×7 grid, intensity = order count; drives staffing.
- **Activity feed** — last 10 orders with status `Badge`, relative time.

Backend extensions (allowed): `range=today|7d|30d|90d|custom&from=&to=`; response gains `funnel`, `orders_heatmap`, `revenue_delta`, `orders_delta`, `recent_orders`, `monthly_goal`. All theme colors come from CSS vars via `useChartOptions()`.

### 5. List pages (Orders, Products, Variations, PreUploaded, Suppliers)

Common pattern:
- `PageHeader` + sticky filter bar (search + key selects + DateRangePicker + "More filters" `Popover`)
- Bulk action bar (appears when rows selected)
- `Table` from `ColumnDef[]`, `Skeleton` rows while loading, `EmptyState` when empty, inline error banner with retry on failure
- `Pagination` footer
- Side `Modal` (drawer variant) for detail view, `ConfirmDialog` for destructive actions, `Toast` for success/error
- All filters/sort/page state synced to URL via `useUrlState` (back/forward restores state)
- Keyboard: `/` focus search, `n` new, `e` edit, `Del` delete, `Esc` close, `j/k` row nav, `Enter` open

Column lists per page (id, header key, render hint, sortable, width) are defined as code-level contracts:

- **Orders**: select / id (mono) / user_id (mono) / status (`Badge` semantic) / total_amount (currency) / items_count / payment_id / created_at (relative + tooltip absolute) / actions.
- **Products**: name+id / description / delivery_type (`Badge`) / variations_count / is_active (inline `Switch` optimistic) / created_at / actions.
- **Variations**: select / name+id / price (currency) / stock (numeric + low-stock `Badge`) / benefit_mode / is_active (`Switch`) / created_at / actions. Grouped accordion-by-product OR flat-table toggle.
- **PreUploaded**: select / product / variation / product_data (mono truncate + Copy `IconButton`) / status (available/sold) / used_at / order_id (linked) / created_at / actions.
- **Suppliers** (re-enabled): name+telegram_id / telegram_id (mono) / is_active (`Switch` + confirm) / assigned_count / total_orders / avg_response_time (NEW) / created_at / actions.

Inline above-table mini-charts where they pay off:
- Orders: 14-day revenue area + status-distribution stacked horizontal bar (current filter scope).
- Products: delivery-type distribution donut (small, dismissible).
- PreUploaded: per-product depletion donut in StatCard popover; "days of stock left" chip column (client-side derivation from last-7d burn rate).
- Suppliers: response-time leaderboard bar (top 5 fastest / slowest).

### 6. Form / configuration pages

- **LoginPage** — split-screen visual: left brand panel (logo + tagline + decorative sparkline), right `Card` with `FormField` username/password (with show-password `Eye` toggle), `Button` with `loading`, inline error block. Stacks on mobile. `t()` everywhere.
- **ProductUploadPage** — Stepper: 1 Target → 2 Data (Tabs File/Paste + format radio) → 3 Preview (parsed `Table` + duplicate banner) → 4 Result (StatCards Success/Failed/Duplicates + tiny stacked bar + collapsible error log). `FileDrop` for files. `ConfirmDialog` for "skip duplicates and upload?".
- **BotUiSettingsPage** — two-column form / live Telegram-bubble preview pane; dirty-state guard + `ConfirmDialog` on navigate-away; `Cmd+S` to save; field char-counters; token autocomplete (`{product_name}`, etc.) via `Popover` chip menu.
- **IotdPage** — two-column: URL/upload form + large 16:9 preview with broken-image fallback + history strip (last 7) from new `GET /api/iotd/history`.
- **NotificationsPage** — Tabs: Broadcast | Order alerts | History.
  - Broadcast: compose card (`Textarea` + char-count + emoji `Popover` + optional schedule) + audience picker (`Tabs` All/Active/Specific + searchable users `Table`).
  - Order alerts: `Switch` enables + chip-input for whitelist/upgrade chat IDs (`^-?\d+(:\d+)?$`).
  - History: `Table` of past broadcasts with stacked-bar preview cell (success vs failed) + delivery-rate trend (last 30).
- **BonusSummaryPage** — KPI row + accordion-by-product with tier-ladder visualization (stepped horizontal bars). New `GET /api/bonus-tiers/coverage` powers the "tier progress rings" addition.

### 7. Cross-cutting decisions

- **Routing & breadcrumbs** — central `routes.ts` (path/key/labelKey/icon/role) consumed by `Sidebar`, `Breadcrumb`, `CommandPalette`. Detail drawers open via querystring (`/orders?orderId=abc`) so URLs are shareable.
- **URL-sync** — `useUrlState<T>(key, default, codec)` wraps `useSearchParams` with typed parse/serialize. Filter changes → `push`; pagination/sort → `replace`.
- **Data fetching** — in-house `useApi` (SWR-style: cache-by-key, dedupe, AbortController, `revalidateOnFocus`) and `useMutation` with optimistic-update support. No external dep added (drop-in compatible with SWR/React Query later).
- **Optimistic updates** — allowed for `is_active` row toggles, single-row non-regression status changes, mark-used/unused, tier active toggle. Forbidden for create, delete, bulk delete, status regression, broadcast send, supplier assignments.
- **Error & toast strategy** — `Toast` for transient feedback; inline error block + retry for whole-section failures; field errors live inside `FormField`; one-shot `formatApiError(err)` helper extracts axios errors.
- **Charts theming** — `useChartOptions()` reads CSS vars and merges into Chart.js options; chart components are keyed on `resolvedTheme` so the toggle re-renders cleanly.
- **Accessibility** — every `IconButton` requires `aria-label`; modals trap focus + restore on close + Esc; `<th aria-sort>` on sortable columns; status badges include screen-reader text; skip-to-main link in `AppShell`; respects `prefers-reduced-motion`; defined z-index scale prevents arbitrary `z-index: 9999`.

### 8. Migration order (incremental — app stays runnable after each step)

1. **Tokens + fonts + base.css** — add new files, alias old token names (`--card-bg: var(--bg-raised)`) so existing pages render unchanged.
2. **ThemeContext rewrite + i18n switch + namespace split** — flip default to `vi`, retain English translations, mechanical key-split.
3. **API client + format helpers + ToastProvider + ConfirmDialog** — install in `providers.tsx`. Replace every `alert()` with `toast.error()` and every `window.confirm` with `useConfirm()` page-by-page (8 pages).
4. **Atom primitives** — Button (extend), IconButton, Input/Textarea/FormField, Spinner, Skeleton, Badge, EmptyState, Switch/Checkbox/Radio. Keep backwards-compat exports from `components/index.ts`.
5. **Overlay primitives** — Modal, Tooltip, Popover, DropdownMenu, Toast (already from step 3). Hard-cutover inline `.modal-overlay` divs.
6. **Data primitives** — Table, Pagination, Tabs, Select (combobox), DateRangePicker, FileDrop. Migrate OrdersPage first (canonical), then ripple to other list pages.
7. **Layout shell** — AppShell + Sidebar + Topbar + UserMenu + Breadcrumb + MobileDrawer + CommandPalette. Swap router root from `DashboardLayout` to `AppShell`. Delete old layout.
8. **Statistics overhaul** — StatCard + ChartCard + PageHeader, bento grid, charts theming, backend extensions deployed first via Alembic migration + `statistics.py` changes.
9. **Page-by-page polish** — Statistics → Orders → Products → Variations → BonusSummary → Notifications → BotUiSettings → ProductUpload → PreUploaded → IOTD → Suppliers (re-enable) → Login.
10. **Cleanup** — delete `App.css`, `styles/theme.ts`, old `layouts/*`; remove token aliases; ESLint rule `no-restricted-globals` for `alert`/`confirm`/`prompt`; update test imports for moved paths.

### 9. Risks & open questions

- **Stat-card delta % requires "previous period" data** — covered by `revenue_delta`/`orders_delta` in extended `/api/statistics/overview`. Hide delta when absent rather than fake.
- **Order-status enum drift** — token names assume backend `OrderStatus` = `pending|paid|processing|delivered|cancelled`. Verify against actual enum before writing tokens; add `shipped`/`refunded` if present.
- **Chart.js re-theme on toggle** — re-render charts on `resolvedTheme` change via React `key`. Brief flash acceptable.
- **`cmd-k` palette v1** — route nav only; global resource search (orders by ID, products by SKU) deferred to phase 2 and would need a `/api/search` endpoint.
- **Tooltip hand-roll** — no flip/shift logic; tooltips near viewport edges may clip. Acceptable for v1 (tooltips only on icon buttons in known positions). Migrate to `@floating-ui/react` if `Popover` collision detection becomes needed.
- **VN-default risk** — only seed `'vi'` when `localStorage.i18nextLng` is absent; never overwrite an existing user choice.
- **Sync-→-async destructive flows** — every `window.confirm` site becomes `await confirm({...})`; lint rule prevents regressions.
- **Bundle size** — Fira Sans (3 weights × `latin`+`vietnamese` subsets) + Fira Code (2 weights) ≈ 80KB gz. Acceptable; subset to `latin,vietnamese` only.
- **Supplier re-enable** — verify backend routes still function and the supplier bot integration is intact before un-commenting routes.
- **Test debt** — existing `test/components/` imports break when paths move; update in same commit.

## Verification

1. **Build & lint after each migration step** — `cd frontend && npm run build && npm run lint && npm test`. Backend: `ruff check . && mypy src && pytest`.
2. **Visual smoke** — start `python run_dashboard.py` (port 8001) and `cd frontend && npm run dev`; walk every page in both themes and both languages, including: login flow, navigating via Sidebar + CommandPalette (`⌘K`), opening detail drawers (verify URL sync), placing the keyboard through `/`, `n`, `e`, `Esc`, `j/k`, opening a `ConfirmDialog` and confirming Toast feedback, switching theme and seeing charts re-color.
3. **A11y** — run axe DevTools on each page (zero serious violations); keyboard-only walkthrough of Orders + Statistics; verify focus trap and Esc on Modals; verify `aria-sort`, `aria-busy`, `aria-live` toast regions; respect `prefers-reduced-motion` (Skeleton stops pulsing, Spinner pulses opacity instead of rotating).
4. **Responsive** — manual at 375 / 768 / 1024 / 1440 px; verify Sidebar → MobileDrawer transition, Tables → card lists, Modal → full-screen sheet, sticky filter bars collapse correctly.
5. **i18n** — start fresh (clear `localStorage`) → confirms Vietnamese loads; switch to English mid-session and confirm currency/date formatting flips via `useFormat()`; verify no hardcoded `vi-VN` strings remain (`grep -RIn "vi-VN" frontend/src` returns 0).
6. **Backend contract** — for each extended endpoint, run pytest covering the new fields (funnel sums match status counts, heatmap has 7×24 = 168 entries, `revenue_delta` is `null` when no prior period data); run Alembic up/down on a clean SQLite to confirm migration is reversible.
7. **Charts** — sample at least 3 ranges (Today / 7d / 30d) and verify Chart.js renders correctly under both themes; verify `prefers-reduced-motion` disables chart entry animations.
8. **End-to-end order flow** — place a test order via the customer bot, watch the Activity feed update on Statistics (poll/refresh), confirm IPN delivery still works, confirm OrdersPage drawer opens via the URL link.
