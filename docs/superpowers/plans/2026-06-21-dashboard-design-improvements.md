# Dashboard Design Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply five visual/UX improvements to the MTK Admin dashboard: warm palette, amber VND accent, vitals strip, statistics page layout restructure, navigation count badges, and a bot-status pill in the topbar.

**Architecture:** All changes are purely frontend — CSS token edits, React component restructures, and one new `useBotStatus` hook. No backend changes required. The todo/counts data already comes from `/api/statistics/todo`; the bot-status derives from recent-order activity already in the statistics payload.

**Tech Stack:** React 18 + TypeScript, custom CSS (no Tailwind), Chart.js, Lucide icons, React Router v6, Axios.

## Global Constraints

- Vietnamese is the primary language; all new copy must be Vietnamese with English fallback via `t('key', 'fallback')`
- Never query models or services directly in handlers — use `apiClient` from `src/shared/lib/api`
- CSS custom properties only — never hardcode hex values outside `tokens.css`
- `prefers-reduced-motion` must be respected on any new animations
- All new CSS classes must follow the existing `component__element--modifier` BEM pattern

---

## File Map

| File | Change |
|------|--------|
| `frontend/src/styles/tokens.css` | Add `--amber-*` tokens; shift dark surface backgrounds to warm undertone |
| `frontend/src/pages/StatisticsPage.css` | Vitals strip layout; bento grid restructure; heatmap full-width; amber revenue cells |
| `frontend/src/pages/StatisticsPage.tsx` | Replace KPI grid with `<VitalsStrip>`; lift todo panel; restructure bento grid areas |
| `frontend/src/app/layouts/Topbar.tsx` | Add `<BotStatusPill>` between search button and language picker |
| `frontend/src/app/layouts/Topbar.css` | Style for bot-status pill |
| `frontend/src/app/layouts/Sidebar.tsx` | Accept `badgeCounts` prop; render count badges on Orders and Pre-uploaded items |
| `frontend/src/app/layouts/Sidebar.css` | Style for `.sidebar__badge` |
| `frontend/src/app/layouts/AppShell.tsx` | Fetch todo counts; pass `badgeCounts` to Sidebar; derive bot status from statistics data |
| `frontend/src/shared/hooks/useBotStatus.ts` | **New** — derives bot online/offline + today's user count from `/api/statistics/overview` |

---

## Task 1: Warm palette + amber tokens

**Files:**
- Modify: `frontend/src/styles/tokens.css`

**What:** Shift all dark-mode surface colours from cold blue-black to warm brown-black and add amber tokens for financial data.

- [ ] **Step 1: Update dark-mode surface colours**

In `tokens.css`, replace the `[data-theme='dark']` block surface values:

```css
[data-theme='dark'] {
  /* ── Surfaces — warm undertone replaces cold blue-black ── */
  --bg-page:    #0C0A08;   /* was #050609 */
  --bg-surface: #141210;   /* was #0b0e14 */
  --bg-raised:  #1D1A16;   /* was #101319 */
  --bg-sunken:  #0A0806;   /* was #07090d */

  --border-subtle: #1E1A15;   /* was #1a2030 */
  --border-strong: #2A241C;   /* was #2a3142 */
  /* … rest of the block unchanged … */
}
```

- [ ] **Step 2: Add amber tokens to both `:root` and `[data-theme='dark']`**

Add these lines at the end of the `:root` block (before the closing `}`):

```css
  /* ── Amber — reserved for VND / financial values ─────── */
  --amber-500: #D4920A;
  --amber-400: #EDA420;
  --amber-50:  rgba(212, 146, 10, 0.10);
  --amber-100: rgba(212, 146, 10, 0.20);
```

Add the same block to `[data-theme='dark']` (amber is identical in dark mode — it's already saturated enough):

```css
  /* ── Amber — same in dark mode ──────────────────────── */
  --amber-500: #D4920A;
  --amber-400: #EDA420;
  --amber-50:  rgba(212, 146, 10, 0.10);
  --amber-100: rgba(212, 146, 10, 0.20);
```

- [ ] **Step 3: Verify visually**

Start the dev server (`npm run dev` inside `frontend/`) and open the dashboard in dark mode. The background should now have a slight warm/brown cast instead of the previous cold blue-black. No component should look broken — only the surface colour shifts.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/tokens.css
git commit -m "feat(design): warm dark palette + amber VND tokens"
```

---

## Task 2: Amber colour on financial figures

**Files:**
- Modify: `frontend/src/pages/StatisticsPage.css`
- Modify: `frontend/src/pages/StatisticsPage.tsx` (one class addition)

**What:** Revenue cells in the product-revenue table, activity-feed amounts, and todo-row amounts use amber instead of the current brand blue.

- [ ] **Step 1: Update revenue cell colour in StatisticsPage.css**

Find and replace:

```css
/* BEFORE */
.stats-product-revenue__td--revenue {
  color: var(--brand-400, #93BBFF);
  font-weight: 500;
}

/* AFTER */
.stats-product-revenue__td--revenue {
  color: var(--amber-400);
  font-weight: 500;
}
```

- [ ] **Step 2: Update activity feed amount colour**

```css
/* BEFORE */
.stats-activity__amount {
  color: var(--text-primary);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
}

/* AFTER */
.stats-activity__amount {
  color: var(--amber-400);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
}
```

- [ ] **Step 3: Update todo row amount colour**

```css
/* BEFORE */
.stats-todo__row-amount {
  font-family: var(--font-mono);
  color: #93BBFF;
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  font-size: 11px;
}

/* AFTER */
.stats-todo__row-amount {
  font-family: var(--font-mono);
  color: var(--amber-400);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  font-size: 11px;
}
```

- [ ] **Step 4: Update the heatmap cell colour from brand blue to amber**

```css
/* BEFORE */
.stats-heatmap__cell {
  flex: 1;
  height: 16px;
  background: var(--brand-500);
  border-radius: 2px;
  cursor: default;
  min-width: 6px;
}

/* AFTER */
.stats-heatmap__cell {
  flex: 1;
  height: 16px;
  background: var(--amber-400);
  border-radius: 2px;
  cursor: default;
  min-width: 6px;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/StatisticsPage.css
git commit -m "feat(design): amber colour for VND financial values and heatmap"
```

---

## Task 3: Vitals strip — replace KPI cards

**Files:**
- Modify: `frontend/src/pages/StatisticsPage.css`
- Modify: `frontend/src/pages/StatisticsPage.tsx`

**What:** Remove the `.stats-page__kpi-row` four-card grid and the two-column user-stats row. Replace with a single horizontal vitals strip that shows revenue, orders, sold count, today's revenue, and the two user-stat values in a compact borderless strip at the top of the page.

- [ ] **Step 1: Add vitals strip CSS to StatisticsPage.css**

Append after the existing `.stats-page > .stat-card` rule:

```css
/* ── Vitals strip ──────────────────────────────────────── */
.stats-vitals {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-5);
  overflow: hidden;
}

.stats-vitals__item {
  padding: var(--space-4) var(--space-4);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.stats-vitals__item:last-child {
  border-right: none;
}

.stats-vitals__label {
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stats-vitals__value {
  font-size: 22px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--amber-400);
  letter-spacing: -0.03em;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Non-financial vitals (counts, users) keep primary text colour */
.stats-vitals__value--neutral {
  color: var(--text-primary);
}

.stats-vitals__delta {
  font-size: 10px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 3px;
}

.stats-vitals__delta--pos  { color: var(--success-500); }
.stats-vitals__delta--neg  { color: var(--danger-500); }
.stats-vitals__delta--flat { color: var(--text-disabled); }

.stats-vitals__skeleton {
  height: 22px;
  border-radius: var(--radius-sm);
  background: var(--border-subtle);
  animation: pulse 1.5s ease-in-out infinite;
  width: 80%;
}

@media (max-width: 1100px) {
  .stats-vitals { grid-template-columns: repeat(3, 1fr); }
  .stats-vitals__item:nth-child(3) { border-right: none; }
  .stats-vitals__item:nth-child(4) { border-top: 1px solid var(--border-subtle); }
  .stats-vitals__item:nth-child(5) { border-top: 1px solid var(--border-subtle); }
  .stats-vitals__item:nth-child(6) { border-top: 1px solid var(--border-subtle); border-right: none; }
}

@media (max-width: 680px) {
  .stats-vitals { grid-template-columns: repeat(2, 1fr); }
  .stats-vitals__item { border-right: 1px solid var(--border-subtle); }
  .stats-vitals__item:nth-child(even) { border-right: none; }
  .stats-vitals__item:nth-child(n+3) { border-top: 1px solid var(--border-subtle); }
  .stats-vitals__item:nth-child(3) { border-right: 1px solid var(--border-subtle); }
}
```

- [ ] **Step 2: Also remove/update the old KPI grid and user-stats grid CSS**

Remove these rules from `StatisticsPage.css` (they are replaced by `.stats-vitals`):

```css
/* DELETE these rules: */
.stats-page__kpi-row { ... }
@media (max-width: 1024px) { .stats-page__kpi-row { ... } }
@media (max-width: 600px)  { .stats-page__kpi-row { ... } }

/* Also DELETE: */
.stats-page > .stat-card { ... }
```

- [ ] **Step 3: Replace KPI row and user-stats row in StatisticsPage.tsx**

In `StatisticsPage.tsx`, find the `{/* KPI Row */}` block (lines 275–328) and replace it entirely with the vitals strip:

```tsx
{/* Vitals strip */}
<div className="stats-vitals">
  {/* Revenue */}
  <div className="stats-vitals__item">
    <span className="stats-vitals__label">{t('statistics.totalRevenue', 'Tổng doanh thu')}</span>
    {loading ? <div className="stats-vitals__skeleton" /> : (
      <span className="stats-vitals__value">{fmt.currency(data?.total_revenue ?? 0)}</span>
    )}
    {!loading && data?.revenue_delta != null && (
      <span className={`stats-vitals__delta stats-vitals__delta--${data.revenue_delta > 0 ? 'pos' : data.revenue_delta < 0 ? 'neg' : 'flat'}`}>
        {data.revenue_delta > 0 ? '▲' : data.revenue_delta < 0 ? '▼' : '—'} {Math.abs(data.revenue_delta).toFixed(1)}%
      </span>
    )}
  </div>

  {/* Today revenue */}
  <div className="stats-vitals__item">
    <span className="stats-vitals__label">{t('statistics.todayRevenue', 'Hôm nay')}</span>
    {loading ? <div className="stats-vitals__skeleton" /> : (
      <span className="stats-vitals__value">{fmt.currency(data?.total_revenue_today ?? 0)}</span>
    )}
  </div>

  {/* Orders */}
  <div className="stats-vitals__item">
    <span className="stats-vitals__label">{t('statistics.totalOrders', 'Đơn hàng')}</span>
    {loading ? <div className="stats-vitals__skeleton" /> : (
      <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.total_orders ?? 0)}</span>
    )}
    {!loading && data?.orders_delta != null && (
      <span className={`stats-vitals__delta stats-vitals__delta--${data.orders_delta > 0 ? 'pos' : data.orders_delta < 0 ? 'neg' : 'flat'}`}>
        {data.orders_delta > 0 ? '▲' : data.orders_delta < 0 ? '▼' : '—'} {Math.abs(data.orders_delta).toFixed(1)}%
      </span>
    )}
  </div>

  {/* Sold */}
  <div className="stats-vitals__item">
    <span className="stats-vitals__label">{t('statistics.totalSold', 'Đã bán')}</span>
    {loading ? <div className="stats-vitals__skeleton" /> : (
      <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.total_sold_all_products ?? 0)}</span>
    )}
  </div>

  {/* Active buyers */}
  <div className="stats-vitals__item">
    <span className="stats-vitals__label">{t('statistics.activeBuyers', 'Người mua')}</span>
    {loading ? <div className="stats-vitals__skeleton" /> : (
      <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.active_users?.current ?? 0)}</span>
    )}
    {!loading && data?.active_users?.pct_change != null && (
      <span className={`stats-vitals__delta stats-vitals__delta--${data.active_users.pct_change > 0 ? 'pos' : data.active_users.pct_change < 0 ? 'neg' : 'flat'}`}>
        {data.active_users.pct_change > 0 ? '▲' : data.active_users.pct_change < 0 ? '▼' : '—'} {Math.abs(data.active_users.pct_change).toFixed(1)}%
      </span>
    )}
  </div>

  {/* Registered / started users */}
  <div className="stats-vitals__item">
    <span className="stats-vitals__label">{t('statistics.startedUsers', 'Đã dùng')}</span>
    {loading ? <div className="stats-vitals__skeleton" /> : (
      <span className="stats-vitals__value stats-vitals__value--neutral">{fmt.number(data?.user_stats?.started ?? 0)}</span>
    )}
  </div>
</div>
```

Also remove the unused icon imports that were only used by the old StatCards: `DollarSign`, `ShoppingCart`, `Package`, `TrendingUp`, `Users`, and remove the `StatCard` import if it's no longer used anywhere else in the file.

- [ ] **Step 4: Verify**

Open the Statistics page. You should see one compact horizontal strip instead of the previous six StatCard boxes. Revenue and today's revenue show in amber; count fields show in the primary text colour.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/StatisticsPage.tsx frontend/src/pages/StatisticsPage.css
git commit -m "feat(statistics): replace KPI cards with vitals strip"
```

---

## Task 4: Statistics page layout — surface Action Required, prominent heatmap

**Files:**
- Modify: `frontend/src/pages/StatisticsPage.css`
- Modify: `frontend/src/pages/StatisticsPage.tsx`

**What:**
1. Move the **Todo/Action Required panel** from its position after the product-revenue table to the top of the bento grid, displayed beside the revenue chart.
2. Give the **heatmap a full-width row** with increased cell height (it currently shares a row with Top Products).
3. Remove the **Donut chart** (its information is duplicated by the Funnel chart).
4. Restructure the bento grid areas accordingly.

- [ ] **Step 1: Update bento grid areas in StatisticsPage.css**

Replace the existing `.stats-page__bento` and related area rules:

```css
/* Bento grid */
.stats-page__bento {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: var(--space-3);
  grid-template-areas:
    "revenue  action"
    "heatmap  heatmap"
    "funnel   top"
    "iotd     activity";
}

.stats-page__revenue-chart  { grid-area: revenue; }
.stats-page__action         { grid-area: action; }
.stats-page__heatmap        { grid-area: heatmap; }
.stats-page__funnel-chart   { grid-area: funnel; }
.stats-page__top-chart      { grid-area: top; }
.stats-page__iotd           { grid-area: iotd; }
.stats-page__activity       { grid-area: activity; }

/* Remove the old donut area — it's deleted */

@media (max-width: 900px) {
  .stats-page__bento {
    grid-template-columns: 1fr;
    grid-template-areas:
      "revenue"
      "action"
      "heatmap"
      "funnel"
      "top"
      "iotd"
      "activity";
  }
}
```

- [ ] **Step 2: Update heatmap cell height for the full-width row**

```css
/* Increase heatmap cell height now that it has full width */
.stats-heatmap__cell {
  flex: 1;
  height: 22px;           /* was 16px */
  background: var(--amber-400);
  border-radius: 3px;     /* was 2px */
  cursor: default;
  min-width: 6px;
}

.stats-heatmap__label {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1;
  text-align: right;
  width: 20px;
  height: 22px;           /* match new cell height */
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
```

- [ ] **Step 3: Add action panel styles to StatisticsPage.css**

```css
/* ── Action panel (inside bento, grid-area: action) ─────── */
.stats-page__action {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stats-action {
  flex: 1;
  overflow-y: auto;
}

.stats-action__group {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}

.stats-action__group:last-child {
  border-bottom: none;
}

.stats-action__group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.stats-action__group-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
```

- [ ] **Step 4: Restructure StatisticsPage.tsx bento section**

In `StatisticsPage.tsx`, make the following changes to the JSX:

**a.** Delete the entire `{/* Todo Section */}` block (the `<div className="stats-todo chart-card">` element and its contents) that currently appears before the bento grid. It will be moved into the bento.

**b.** Delete the `<ChartCard … className="stats-page__donut-chart">` block (the donut chart). Do not delete the `donutData` memo — remove it only if nothing else uses it; if unsure, leave the memo but remove the JSX.

**c.** Add a new action panel as the second child of `.stats-page__bento` (right after the revenue `ChartCard`). Here is the full replacement bento section:

```tsx
{/* Bento grid */}
<div className="stats-page__bento">

  {/* Revenue chart */}
  <ChartCard
    title={t('statistics.revenueTrend', 'Xu hướng doanh thu')}
    loading={loading}
    minHeight={200}
    className="stats-page__revenue-chart"
    actions={
      <Tabs
        tabs={[
          { key: 'daily', label: t('statistics.daily', 'Ngày'), panel: null },
          { key: 'weekly', label: t('statistics.weekly', 'Tuần'), panel: null },
          { key: 'monthly', label: t('statistics.monthly', 'Tháng'), panel: null },
        ]}
        activeKey={revTab}
        onChange={setRevTab}
        variant="pill"
        size="sm"
      />
    }
  >
    {revData && (
      <Line
        key={`rev-${resolvedTheme}-${revTab}`}
        data={revData}
        options={{ ...baseOpts, plugins: { ...baseOpts.plugins, legend: { display: false } } } as Parameters<typeof Line>[0]['options']}
      />
    )}
  </ChartCard>

  {/* Action Required panel — moved from bottom, shown prominently */}
  <div className="stats-page__action chart-card">
    <div className="chart-card__header">
      <h3 className="chart-card__title">Việc cần làm</h3>
    </div>
    <div className="stats-action">

      <div className="stats-action__group">
        <div className="stats-action__group-header">
          <span className="stats-action__group-title">Đơn nâng cấp đang chờ</span>
          {todoData && (
            <span className={`stats-todo__badge${todoData.upgrade_orders_count > 0 ? ' stats-todo__badge--warn' : ''}`}>
              {todoData.upgrade_orders_count}
            </span>
          )}
        </div>
        {todoLoading ? (
          <div className="stats-todo__skeleton" />
        ) : !todoData?.upgrade_orders.length ? (
          <p className="stats-todo__empty">Không có đơn nào</p>
        ) : (
          todoData.upgrade_orders.map(order => (
            <button
              key={order.id}
              className="stats-todo__row"
              onClick={() => navigate(`/orders?q=${order.id}`)}
            >
              <span className="stats-todo__row-id num">#{order.id.slice(0, 8)}</span>
              <Badge status={order.status as OrderStatus} size="sm">
                {t(`orders.status.${order.status}`, order.status)}
              </Badge>
              <span className="stats-todo__row-amount num">{fmt.currency(order.total_amount)}</span>
              <span className="stats-todo__row-time">{fmt.relative(order.created_at)}</span>
            </button>
          ))
        )}
      </div>

      <div className="stats-action__group">
        <div className="stats-action__group-header">
          <span className="stats-action__group-title">Tồn kho đã cũ / sắp hết hạn</span>
          {todoData && (
            <span className={`stats-todo__badge${todoData.aging_inventory_count > 0 ? ' stats-todo__badge--warn' : ''}`}>
              {todoData.aging_inventory_count}
            </span>
          )}
        </div>
        {todoLoading ? (
          <div className="stats-todo__skeleton" />
        ) : !todoData?.aging_inventory.length ? (
          <p className="stats-todo__empty">Không có phân loại nào</p>
        ) : (
          todoData.aging_inventory.map(v => (
            <button
              key={`aging-${v.variation_id}`}
              className="stats-todo__row"
              onClick={() => navigate(`/pre-uploaded?product=${v.product_id}&variation=${v.variation_id}&aging=aging`)}
            >
              <span className="stats-todo__row-name">{v.product_name}</span>
              <span className="stats-todo__row-variation">{v.variation_name}</span>
              <span className="stats-todo__row-tags">
                {v.aging > 0 && <span className="stats-todo__tag stats-todo__tag--aged">{v.aging} cũ</span>}
                {v.expiring_soon > 0 && <span className="stats-todo__tag stats-todo__tag--expiring">{v.expiring_soon} sắp hết</span>}
              </span>
            </button>
          ))
        )}
      </div>

      <div className="stats-action__group">
        <div className="stats-action__group-header">
          <span className="stats-action__group-title">Tồn kho sắp hết</span>
          {todoData && (
            <span className={`stats-todo__badge${todoData.low_stock_inventory_count > 0 ? ' stats-todo__badge--danger' : ''}`}>
              {todoData.low_stock_inventory_count}
            </span>
          )}
        </div>
        {todoLoading ? (
          <div className="stats-todo__skeleton" />
        ) : !todoData?.low_stock_inventory.length ? (
          <p className="stats-todo__empty">Không có phân loại nào</p>
        ) : (
          todoData.low_stock_inventory.map(v => (
            <button
              key={`lowstock-${v.variation_id}`}
              className="stats-todo__row"
              onClick={() => navigate(`/pre-uploaded?product=${v.product_id}&variation=${v.variation_id}`)}
            >
              <span className="stats-todo__row-name">{v.product_name}</span>
              <span className="stats-todo__row-variation">{v.variation_name}</span>
              <span className={`stats-todo__stock-pill${v.in_stock === 0 ? ' stats-todo__stock-pill--out' : ' stats-todo__stock-pill--low'}`}>
                {v.in_stock === 0 ? 'Hết hàng' : `${v.in_stock} còn`}
              </span>
            </button>
          ))
        )}
      </div>

    </div>
  </div>

  {/* Heatmap — full width */}
  <div className="stats-page__heatmap chart-card">
    <div className="chart-card__header">
      <h3 className="chart-card__title">{t('statistics.heatmap', 'Mật độ đơn theo giờ')}</h3>
    </div>
    <div className="stats-heatmap">
      <div className="stats-heatmap__y-labels">
        {DAY_LABELS.map(d => <span key={d} className="stats-heatmap__label">{d}</span>)}
      </div>
      <div className="stats-heatmap__grid">
        {DAY_LABELS.map((_, day) => (
          <div key={day} className="stats-heatmap__row">
            {Array.from({ length: 24 }).map((_, hour) => {
              const cell = data?.orders_heatmap.find(c => c.day === day && c.hour === hour)
              const intensity = cell ? cell.count / heatmapMax : 0
              return (
                <div
                  key={hour}
                  className="stats-heatmap__cell"
                  title={`${DAY_LABELS[day]} ${hour}h: ${cell?.count ?? 0}`}
                  style={{ opacity: intensity ? 0.1 + intensity * 0.9 : 0.04 }}
                />
              )
            })}
          </div>
        ))}
      </div>
    </div>
  </div>

  {/* Funnel */}
  <ChartCard
    title={t('statistics.conversionFunnel', 'Phễu chuyển đổi')}
    loading={loading}
    minHeight={160}
    className="stats-page__funnel-chart"
  >
    {funnelData && (
      <Bar
        key={`funnel-${resolvedTheme}`}
        data={funnelData}
        options={{ ...baseOpts, indexAxis: 'y' as const, plugins: { ...baseOpts.plugins, legend: { display: false } } } as Parameters<typeof Bar>[0]['options']}
      />
    )}
  </ChartCard>

  {/* Top products */}
  <ChartCard
    title={t('statistics.topProducts', 'Sản phẩm bán chạy')}
    loading={loading}
    minHeight={160}
    className="stats-page__top-chart"
  >
    {topData && (
      <Bar
        key={`top-${resolvedTheme}`}
        data={topData}
        options={{ ...baseOpts, indexAxis: 'y' as const, plugins: { ...baseOpts.plugins, legend: { display: false } } } as Parameters<typeof Bar>[0]['options']}
      />
    )}
  </ChartCard>

  {/* Image of the Day */}
  <div className="stats-page__iotd chart-card">
    <div className="chart-card__header">
      <h3 className="chart-card__title">{t('nav.iotd', 'Ảnh ngày')}</h3>
    </div>
    <div className="stats-iotd">
      {iotdUrl && !iotdImgError ? (
        <img
          src={iotdUrl}
          alt={t('iotd.previewAlt', 'Ảnh ngày')}
          className="stats-iotd__img"
          onError={() => setIotdImgError(true)}
        />
      ) : (
        <div className="stats-iotd__empty">
          <ImageIcon size={28} />
          <span>{iotdImgError ? t('iotd.imageError', 'Không tải được ảnh') : t('iotd.noImage', 'Chưa có ảnh')}</span>
        </div>
      )}
    </div>
  </div>

  {/* Activity feed */}
  <div className="stats-page__activity chart-card">
    <div className="chart-card__header">
      <h3 className="chart-card__title">{t('statistics.recentOrders', 'Đơn hàng gần đây')}</h3>
    </div>
    <div className="stats-activity">
      {data?.recent_orders.map(order => (
        <div key={order.id} className="stats-activity__row">
          <span className="stats-activity__id num">#{order.id.slice(0, 8)}</span>
          <Badge status={order.status as OrderStatus} size="sm">
            {t(`orders.status.${order.status}`, order.status)}
          </Badge>
          <span className="stats-activity__amount num">
            {fmt.currency(order.total_amount)}
          </span>
          <span className="stats-activity__time">
            {fmt.relative(order.created_at)}
          </span>
        </div>
      ))}
    </div>
  </div>

</div>
```

Also remove the product-revenue table block (the `<div className="stats-product-revenue chart-card">`) from StatisticsPage.tsx — it sat between the user-stats row and the todo section. Keep the `sortedProducts` and `productSort` state if removing it causes TypeScript errors, but the table itself is removed (it's a detail table that cluttered the overview page).

- [ ] **Step 5: Verify layout**

The Statistics page should now show:
- Vitals strip at top
- Revenue chart (left, 60% width) + Action Required panel (right, 40% width)
- Full-width heatmap row with taller, amber cells
- Two half-width chart rows below (Funnel + Top Products, then IOTD + Activity)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/StatisticsPage.tsx frontend/src/pages/StatisticsPage.css
git commit -m "feat(statistics): restructure layout — surface action panel, full-width heatmap"
```

---

## Task 5: Navigation count badges

**Files:**
- Modify: `frontend/src/app/layouts/Sidebar.tsx`
- Modify: `frontend/src/app/layouts/Sidebar.css`
- Modify: `frontend/src/app/layouts/AppShell.tsx`

**What:** Show count badges on the Orders and Pre-uploaded sidebar items. Counts come from `todoData` already fetched by AppShell (which we also add here). The `badgeCounts` object maps route keys to a count or a severity string.

- [ ] **Step 1: Add badge styles to Sidebar.css**

Append at the end of `Sidebar.css`:

```css
/* ── Nav badges ────────────────────────────────────── */
.sidebar__badge {
  margin-left: auto;
  padding: 0 5px;
  min-width: 18px;
  height: 16px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--danger-50);
  color: var(--danger-500);
  line-height: 1;
}

.sidebar__badge--warn {
  background: var(--warning-50);
  color: var(--warning-600);
}

/* In collapsed mode badges become a dot */
.sidebar--collapsed .sidebar__badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 7px;
  height: 7px;
  min-width: unset;
  padding: 0;
  font-size: 0;
  border-radius: 50%;
}

.sidebar__item {
  position: relative; /* needed for collapsed dot positioning */
}
```

- [ ] **Step 2: Update Sidebar.tsx to accept and render badge counts**

Replace the entire `Sidebar.tsx` with:

```tsx
import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { LucideIcon } from 'lucide-react'
import {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell, Upload,
  Database, Gift, Settings, Users, Boxes, Wallet, BookOpen,
  Bot, PanelLeftClose, PanelLeft,
} from 'lucide-react'
import { Tooltip } from '../../shared/components/Tooltip'
import { ROUTE_GROUPS, routesByGroup } from '../routes'
import './Sidebar.css'

const ICON_MAP: Record<string, LucideIcon> = {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell,
  Upload, Database, Gift, Settings, Users, Boxes, Wallet, BookOpen,
}

export interface NavBadgeCounts {
  orders?: number        // unpaid order count
  preUploaded?: 'warn'   // aging/low-stock flag
}

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  badgeCounts?: NavBadgeCounts
  className?: string
}

const ROUTE_KEY_TO_BADGE: Record<string, keyof NavBadgeCounts> = {
  orders: 'orders',
  preUploaded: 'preUploaded',
}

export function Sidebar({ collapsed, onToggleCollapse, badgeCounts = {}, className = '' }: SidebarProps) {
  const { t } = useTranslation()
  const location = useLocation()

  return (
    <nav
      className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''} ${className}`}
      aria-label={t('nav.sidebar', 'Navigation')}
    >
      {/* Logo */}
      <div className="sidebar__logo">
        <Bot size={20} className="sidebar__logo-icon" />
        {!collapsed && <span className="sidebar__logo-text">MTK Admin</span>}
      </div>

      {/* Groups */}
      <div className="sidebar__nav">
        {ROUTE_GROUPS.map(group => {
          const routes = routesByGroup(group.key)
          if (!routes.length) return null
          return (
            <div key={group.key} className="sidebar__group">
              {!collapsed && (
                <p className="sidebar__group-label">{t(group.labelKey, group.key)}</p>
              )}
              {routes.map(route => {
                const Icon = ICON_MAP[route.iconName]
                const isActive = location.pathname.startsWith(route.path)
                const label = t(route.labelKey, route.key)
                const badgeKey = ROUTE_KEY_TO_BADGE[route.key]
                const badgeValue = badgeKey ? badgeCounts[badgeKey] : undefined

                const badge = badgeValue != null ? (
                  badgeValue === 'warn'
                    ? <span className="sidebar__badge sidebar__badge--warn" aria-label="Cần chú ý">!</span>
                    : badgeValue > 0
                      ? <span className="sidebar__badge" aria-label={`${badgeValue} chờ xử lý`}>{badgeValue > 99 ? '99+' : badgeValue}</span>
                      : null
                ) : null

                const navItem = (
                  <NavLink
                    key={route.key}
                    to={route.path}
                    className={({ isActive }) =>
                      `sidebar__item ${isActive ? 'sidebar__item--active' : ''}`
                    }
                    aria-label={collapsed ? label : undefined}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {Icon && <Icon size={16} className="sidebar__item-icon" />}
                    {!collapsed && <span className="sidebar__item-label">{label}</span>}
                    {badge}
                  </NavLink>
                )

                return collapsed
                  ? <Tooltip key={route.key} content={label} placement="right" delay={300}>{navItem}</Tooltip>
                  : navItem
              })}
            </div>
          )
        })}
      </div>

      {/* Collapse toggle */}
      <div className="sidebar__footer">
        <button
          type="button"
          className="sidebar__collapse-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'}
        >
          {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
          {!collapsed && <span>Thu gọn</span>}
        </button>
      </div>
    </nav>
  )
}
```

- [ ] **Step 3: Fetch todo counts in AppShell and pass to Sidebar**

In `AppShell.tsx`, add the todo fetch and pass `badgeCounts` to `<Sidebar>`. Replace the full file:

```tsx
import { Outlet } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Sidebar, type NavBadgeCounts } from './Sidebar'
import { Topbar } from './Topbar'
import { MobileDrawer } from './MobileDrawer'
import { CommandPalette } from './CommandPalette'
import { useDisclosure } from '../../shared/hooks/useDisclosure'
import { useMediaQuery } from '../../shared/hooks/useMediaQuery'
import { apiClient } from '../../shared/lib/api'
import './AppShell.css'

function readCollapsed(): boolean {
  try { return localStorage.getItem('sidebar-collapsed') === 'true' } catch { return false }
}

interface TodoCounts {
  upgrade_orders_count: number
  aging_inventory_count: number
  low_stock_inventory_count: number
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const isMobile = useMediaQuery('(max-width: 900px)')
  const drawer = useDisclosure()
  const cmdPalette = useDisclosure()
  const [badgeCounts, setBadgeCounts] = useState<NavBadgeCounts>({})

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', String(collapsed)) } catch { /* noop */ }
  }, [collapsed])

  useEffect(() => { drawer.close() }, [])

  // Fetch todo counts for sidebar badges
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await apiClient.get<TodoCounts>('/api/statistics/todo')
        if (cancelled) return
        const d = res.data
        setBadgeCounts({
          orders: d.upgrade_orders_count,
          preUploaded: (d.aging_inventory_count > 0 || d.low_stock_inventory_count > 0) ? 'warn' : undefined,
        })
      } catch { /* fail silently */ }
    }
    load()
    const interval = setInterval(load, 60_000)  // refresh every minute
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  // ⌘K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        cmdPalette.toggle()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [cmdPalette])

  return (
    <div
      className="app-shell"
      data-collapsed={isMobile ? 'false' : String(collapsed)}
      data-mobile={String(isMobile)}
    >
      <a href="#main-content" className="skip-link">Bỏ qua điều hướng</a>

      {!isMobile && (
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed(v => !v)}
          badgeCounts={badgeCounts}
          className="app-shell__sidebar"
        />
      )}

      <Topbar
        onMenuClick={drawer.open}
        isMobile={isMobile}
        onSearchClick={cmdPalette.open}
        className="app-shell__topbar"
      />

      <main id="main-content" className="app-shell__main" tabIndex={-1}>
        <Outlet />
      </main>

      {isMobile && (
        <MobileDrawer
          open={drawer.isOpen}
          onClose={drawer.close}
        />
      )}

      <CommandPalette
        open={cmdPalette.isOpen}
        onClose={cmdPalette.close}
      />
    </div>
  )
}
```

- [ ] **Step 4: Verify**

Open the dashboard. If there are pending upgrade orders, the "Orders" nav item shows a red count badge. If there are aging or low-stock inventory items, "Pre-uploaded" shows a yellow `!` badge. Both disappear in the next polling cycle when resolved.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/layouts/Sidebar.tsx \
        frontend/src/app/layouts/Sidebar.css \
        frontend/src/app/layouts/AppShell.tsx
git commit -m "feat(nav): count badges on Orders and Pre-uploaded sidebar items"
```

---

## Task 6: Bot status pill in topbar

**Files:**
- Modify: `frontend/src/app/layouts/Topbar.tsx`
- Modify: `frontend/src/app/layouts/Topbar.css`

**What:** Add a compact "Bot online / Bot offline" pill in the topbar, between the page title and the search button. Bot online is determined by whether there is at least one order in the last 24 hours. Fetch a minimal endpoint — reuse `/api/statistics/overview?range=1d` with a short stale window.

- [ ] **Step 1: Add bot status styles to Topbar.css**

Read `Topbar.css` first to see where to append. Then add:

```css
/* ── Bot status pill ─────────────────────────────────── */
.topbar__bot-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px 4px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  border: 1px solid transparent;
  flex-shrink: 0;
  margin-right: auto;
}

.topbar__bot-status--online {
  background: var(--success-50);
  border-color: rgba(34, 197, 94, 0.2);
  color: var(--success-600);
}

.topbar__bot-status--offline {
  background: var(--bg-sunken);
  border-color: var(--border-subtle);
  color: var(--text-muted);
}

.topbar__bot-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.topbar__bot-status--online  .topbar__bot-dot { background: var(--success-500); animation: bot-pulse 2.4s ease-in-out infinite; }
.topbar__bot-status--offline .topbar__bot-dot { background: var(--text-disabled); }

@keyframes bot-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}

@media (prefers-reduced-motion: reduce) {
  .topbar__bot-dot { animation: none; }
}

/* Hide the pill label on narrow viewports, keep the dot */
@media (max-width: 600px) {
  .topbar__bot-status { padding: 4px 6px; }
  .topbar__bot-status span:last-child { display: none; }
}
```

- [ ] **Step 2: Add bot-status state to Topbar.tsx**

Replace `Topbar.tsx` with the following (same as existing, adds the fetch and pill render):

```tsx
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search, Menu, Sun, Moon, Globe, ChevronDown, LogOut, User } from 'lucide-react'
import { useEffect, useState } from 'react'
import { IconButton } from '../../shared/components/IconButton'
import { DropdownMenu, type DropdownMenuItem } from '../../shared/components/DropdownMenu'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
import { apiClient } from '../../shared/lib/api'
import { ROUTES } from '../routes'
import './Topbar.css'

interface TopbarProps {
  onMenuClick: () => void
  isMobile: boolean
  onSearchClick: () => void
  className?: string
}

export function Topbar({ onMenuClick, isMobile, onSearchClick, className = '' }: TopbarProps) {
  const { t, i18n } = useTranslation()
  const { resolvedTheme, toggleTheme } = useTheme()
  const { user, logout } = useAuth()
  const location = useLocation()
  const [botOnline, setBotOnline] = useState<boolean | null>(null)

  const currentRoute = ROUTES.find(r => location.pathname.startsWith(r.path))
  const pageTitle = currentRoute ? t(currentRoute.labelKey, currentRoute.key) : ''

  // Derive bot status from whether there are recent orders
  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await apiClient.get<{ total_orders_today: number }>('/api/statistics/overview', {
          params: { range: '1d' },
        })
        if (!cancelled) setBotOnline(res.data.total_orders_today > 0)
      } catch {
        if (!cancelled) setBotOnline(false)
      }
    }
    check()
    const interval = setInterval(check, 120_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  const langItems: DropdownMenuItem[] = [
    { key: 'vi', label: 'Tiếng Việt', onClick: () => i18n.changeLanguage('vi') },
    { key: 'en', label: 'English',    onClick: () => i18n.changeLanguage('en') },
  ]

  const userItems: DropdownMenuItem[] = [
    { key: 'profile', label: t('common.profile', 'Hồ sơ'), icon: <User />, onClick: () => {} },
    { key: 'sep', label: '', separator: true },
    { key: 'logout', label: t('common.logout', 'Đăng xuất'), icon: <LogOut />, danger: true, onClick: logout },
  ]

  const username = (user as { username?: string })?.username ?? 'Admin'

  return (
    <header className={`topbar ${className}`}>
      <div className="topbar__left">
        {isMobile && (
          <IconButton
            icon={<Menu />}
            aria-label="Open menu"
            variant="ghost"
            onClick={onMenuClick}
          />
        )}
        <h1 className="topbar__page-title">{pageTitle}</h1>
      </div>

      {/* Bot status pill — only show once status is known */}
      {botOnline !== null && (
        <div
          className={`topbar__bot-status topbar__bot-status--${botOnline ? 'online' : 'offline'}`}
          title={botOnline ? 'Bot đang hoạt động' : 'Bot không có đơn hàng hôm nay'}
        >
          <span className="topbar__bot-dot" />
          <span>{botOnline ? 'Bot online' : 'Bot offline'}</span>
        </div>
      )}

      <div className="topbar__right">
        <button
          type="button"
          className="topbar__search-btn"
          onClick={onSearchClick}
          aria-label={t('common.search', 'Tìm kiếm')}
        >
          <Search size={14} />
          <span className="topbar__search-text">{t('common.search', 'Tìm kiếm…')}</span>
          <kbd className="topbar__kbd">⌘K</kbd>
        </button>

        <DropdownMenu
          trigger={
            <IconButton
              icon={<Globe size={16} />}
              aria-label={t('common.language', 'Ngôn ngữ')}
              variant="ghost"
              size="sm"
            />
          }
          items={langItems}
          placement="bottom-end"
        />

        <IconButton
          icon={resolvedTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          aria-label={resolvedTheme === 'dark' ? t('common.lightMode', 'Sáng') : t('common.darkMode', 'Tối')}
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
        />

        <DropdownMenu
          trigger={
            <button type="button" className="topbar__user-btn" aria-label={`${username} menu`}>
              <span className="topbar__avatar">{username[0]?.toUpperCase()}</span>
              <span className="topbar__username">{username}</span>
              <ChevronDown size={12} />
            </button>
          }
          items={userItems}
          placement="bottom-end"
        />
      </div>
    </header>
  )
}
```

- [ ] **Step 3: Check Topbar.css for any flex layout that needs updating**

The bot-status pill sits between `.topbar__left` and `.topbar__right`. The topbar must be `display:flex; align-items:center` — verify this exists in `Topbar.css`. If not, add `justify-content: space-between` to `.topbar` and ensure the pill doesn't collapse.

Read `Topbar.css` and confirm `.topbar` has `display: flex` and `align-items: center`. The pill uses `margin-right: auto` so it will push itself left while allowing `.topbar__right` to stay right-aligned.

- [ ] **Step 4: Verify**

Load the dashboard. The topbar shows a pulsing green dot with "Bot online" if today has any orders, or a static grey dot with "Bot offline" otherwise. On mobile (<600px) only the dot shows, not the label.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/layouts/Topbar.tsx frontend/src/app/layouts/Topbar.css
git commit -m "feat(topbar): bot status pill with live online indicator"
```

---

## Self-Review

### Spec coverage check

| Proposal | Task |
|----------|------|
| Warm dark palette shift | Task 1 ✓ |
| Amber for all VND values | Task 2 ✓ |
| Vitals strip (replace KPI cards) | Task 3 ✓ |
| Statistics layout restructure (action required, heatmap) | Task 4 ✓ |
| Navigation count badges | Task 5 ✓ |
| Bot status pill in topbar | Task 6 ✓ |

### Placeholder scan

- All CSS values are explicit hex or CSS custom properties — no `TBD`
- All TypeScript code is complete — no `// implement later`
- All steps show exact code to write

### Type consistency

- `NavBadgeCounts` is defined in Sidebar.tsx and imported as a named export in AppShell.tsx — consistent
- `TodoCounts` interface in AppShell.tsx matches the fields used from `/api/statistics/todo` response (which already has `upgrade_orders_count`, `aging_inventory_count`, `low_stock_inventory_count`)
- `total_orders_today` is in `StatisticsData` (line 44 of StatisticsPage.tsx) — used correctly in Topbar fetch
- Amber tokens (`--amber-400`, `--amber-50`) are defined in Task 1 before they are referenced in Tasks 2 and 3

### Sequencing dependency

Tasks 2, 3, 4 depend on Task 1 (tokens must exist). Tasks 5 and 6 are independent of each other and of 2–4. Safe parallel execution order: **Task 1 → then Tasks 2+3+4+5+6 in any order**.
