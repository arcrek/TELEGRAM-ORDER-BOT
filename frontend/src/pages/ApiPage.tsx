import { useState } from 'react'
import {
  ChevronDown, ChevronRight, Copy, Check,
  ShieldCheck, Globe, Zap, List, Eye, History,
  Package, Wallet, Bot,
} from 'lucide-react'
import './ApiPage.css'

// ─── helpers ────────────────────────────────────────────────────────────────

function useCopy(text: string, ms = 1500) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), ms)
    })
  }
  return { copied, copy }
}

function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const { copied, copy } = useCopy(text)
  return (
    <button type="button" className={`api-copy-btn ${copied ? 'api-copy-btn--copied' : ''}`} onClick={copy}>
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? 'Đã sao chép' : label}
    </button>
  )
}

function MethodBadge({ method }: { method: 'GET' | 'POST' | 'DELETE' }) {
  return <span className={`api-method api-method--${method.toLowerCase()}`}>{method}</span>
}

function CodeBlock({ code, lang = 'json' }: { code: string; lang?: string }) {
  return (
    <div className="api-code-block">
      <div className="api-code-block__header">
        <span className="api-code-block__lang">{lang}</span>
        <CopyButton text={code} />
      </div>
      <pre className="api-code-block__body"><code>{code}</code></pre>
    </div>
  )
}

function Endpoint({
  method, path, summary, description, auth = true,
  request, response, error,
}: {
  method: 'GET' | 'POST' | 'DELETE'
  path: string
  summary: string
  description?: string
  auth?: boolean
  request?: { title: string; body: string }
  response: { title: string; body: string }
  error?: { title: string; body: string }
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className={`api-endpoint ${open ? 'api-endpoint--open' : ''}`}>
      <button
        type="button"
        className="api-endpoint__header"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <span className="api-endpoint__left">
          <MethodBadge method={method} />
          <code className="api-endpoint__path">/api/v1{path}</code>
          {auth && <span className="api-endpoint__auth-badge" title="Requires Bearer token">🔑</span>}
        </span>
        <span className="api-endpoint__summary">{summary}</span>
        {open
          ? <ChevronDown size={15} className="api-endpoint__chevron" />
          : <ChevronRight size={15} className="api-endpoint__chevron" />}
      </button>

      {open && (
        <div className="api-endpoint__body">
          {description && <p className="api-endpoint__desc">{description}</p>}

          {request && (
            <div className="api-endpoint__section">
              <h4 className="api-endpoint__section-title">Request body</h4>
              <CodeBlock code={request.body} />
            </div>
          )}

          <div className="api-endpoint__section">
            <h4 className="api-endpoint__section-title">{response.title}</h4>
            <CodeBlock code={response.body} />
          </div>

          {error && (
            <div className="api-endpoint__section">
              <h4 className="api-endpoint__section-title api-endpoint__section-title--error">
                {error.title}
              </h4>
              <CodeBlock code={error.body} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="api-section">
      <h2 className="api-section__title">
        <span className="api-section__icon">{icon}</span>
        {title}
      </h2>
      {children}
    </section>
  )
}

// ─── page ────────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8001'

export function ApiPage() {
  return (
    <div className="api-shell">
      {/* Standalone topbar — no auth required */}
      <header className="api-shell__topbar">
        <div className="api-shell__topbar-inner">
          <div className="api-shell__brand">
            <Bot size={18} className="api-shell__brand-icon" />
            <span className="api-shell__brand-name">MTK Admin</span>
            <span className="api-shell__brand-sep">/</span>
            <span className="api-shell__brand-page">API Reference</span>
          </div>
          <span className="api-shell__badge">v1</span>
        </div>
      </header>

      <main className="api-shell__main">
        <div className="api-page">
          {/* Hero */}
          <div className="api-hero">
            <h1 className="api-hero__title">API Reference</h1>
            <p className="api-hero__sub">
              Public Order-via-API — tích hợp đặt hàng từ ứng dụng ngoài.
              Lấy token bằng lệnh <code>/apitoken</code> trong Telegram.
            </p>
          </div>

          {/* Base URL */}
          <Section icon={<Globe size={15} />} title="Base URL">
            <div className="api-base-url">
              <code className="api-base-url__value">{BASE_URL}</code>
              <CopyButton text={BASE_URL} label="Sao chép" />
            </div>
            <p className="api-prose">
              Tất cả endpoints bắt đầu bằng <code>/api/v1</code>. Chỉ chấp nhận sản phẩm loại{' '}
              <strong>PRE_UPLOADED</strong> — thanh toán bằng số dư tài khoản.
            </p>
          </Section>

          {/* Auth */}
          <Section icon={<ShieldCheck size={15} />} title="Xác thực">
            <p className="api-prose">
              Mỗi request cần header <code>Authorization: Bearer &lt;token&gt;</code>.
              Token gắn với một BotUser cụ thể — mọi thao tác đều thực hiện nhân danh người dùng đó.
            </p>
            <div className="api-auth-cards api-auth-cards--single">
              <div className="api-auth-card">
                <div className="api-auth-card__icon"><Zap size={15} /></div>
                <div>
                  <strong>Lấy token</strong>
                  <p>Gõ <code>/apitoken</code> trong Telegram để tự tạo / làm mới token của bạn.</p>
                </div>
              </div>
            </div>
            <CodeBlock
              lang="bash"
              code={`curl -H "Authorization: Bearer <token>" ${BASE_URL}/api/v1/balance`}
            />
            <div className="api-error-table">
              <div className="api-error-table__row">
                <span className="api-http-code api-http-code--error">401</span>
                <span>Token thiếu hoặc không hợp lệ</span>
              </div>
              <div className="api-error-table__row">
                <span className="api-http-code api-http-code--error">503</span>
                <span>Bot Telegram chưa khởi động — hệ thống chưa sẵn sàng nhận đơn</span>
              </div>
            </div>
          </Section>

          {/* Products */}
          <Section icon={<Package size={15} />} title="Sản phẩm">
            <Endpoint
              method="GET"
              path="/products"
              summary="Danh sách sản phẩm PRE_UPLOADED"
              description="Trả về các sản phẩm đang hoạt động kèm biến thể và tồn kho thực tế. Query params: page, per_page."
              response={{
                title: '200 OK',
                body: JSON.stringify({
                  items: [
                    {
                      id: 'abc123',
                      name: 'Netflix Premium 1 Tháng',
                      description: 'Tài khoản Netflix Premium',
                      delivery_type: 'pre_uploaded',
                      is_active: true,
                      variations: [
                        { id: 'var_1', name: '1 tháng', price: 75000, stock: 12, is_active: true },
                        { id: 'var_2', name: '3 tháng', price: 200000, stock: 5, is_active: true },
                      ],
                    },
                  ],
                  page: 1,
                  per_page: 20,
                  total: 1,
                  note: 'Pages may contain fewer than per_page items because filtering to PRE_UPLOADED delivery type is applied after pagination.',
                }, null, 2),
              }}
            />
            <Endpoint
              method="GET"
              path="/products/{product_id}"
              summary="Chi tiết sản phẩm"
              description="Lấy một sản phẩm theo ID. Trả 404 nếu không tồn tại, không active, hoặc không phải PRE_UPLOADED."
              response={{
                title: '200 OK',
                body: JSON.stringify({
                  id: 'abc123',
                  name: 'Netflix Premium 1 Tháng',
                  description: 'Tài khoản Netflix Premium',
                  delivery_type: 'pre_uploaded',
                  is_active: true,
                  variations: [
                    { id: 'var_1', name: '1 tháng', price: 75000, stock: 12, is_active: true },
                  ],
                }, null, 2),
              }}
              error={{
                title: '404 Not Found',
                body: JSON.stringify({ detail: 'Product not found or not available via API' }, null, 2),
              }}
            />
          </Section>

          {/* Balance */}
          <Section icon={<Wallet size={15} />} title="Số dư">
            <Endpoint
              method="GET"
              path="/balance"
              summary="Xem số dư hiện tại"
              description="Trả về số dư (VND) của người dùng gắn với token."
              response={{
                title: '200 OK',
                body: JSON.stringify({ balance: 350000 }, null, 2),
              }}
            />
          </Section>

          {/* Orders */}
          <Section icon={<List size={15} />} title="Đơn hàng">
            <Endpoint
              method="POST"
              path="/orders"
              summary="Đặt hàng (trừ số dư)"
              description="Tạo đơn hàng và trả tiền ngay từ số dư. Nếu thành công, nội dung số (product_data) được trả về trong response. Rate limit: 10 requests/minute."
              request={{
                title: 'Request body',
                body: JSON.stringify({ variation_id: 'var_1', quantity: 1 }, null, 2),
              }}
              response={{
                title: '200 OK — đơn đã giao',
                body: JSON.stringify({
                  id: 'a1b2c3d4',
                  status: 'delivered',
                  total_amount: 75000,
                  discount_amount: 0,
                  payment_transaction_id: null,
                  created_at: '2026-06-06T10:00:00',
                  updated_at: '2026-06-06T10:00:05',
                  items: [
                    {
                      id: 'item_a1b2c3d4',
                      quantity: 1,
                      bonus_quantity: 0,
                      total_items: 1,
                      unit_price: 75000,
                      subtotal: 75000,
                      discount_amount: 0,
                      product_id: 'abc123',
                      product_name: 'Netflix Premium 1 Tháng',
                      variation_id: 'var_1',
                      variation_name: '1 tháng',
                      delivered_count: 1,
                      delivered_products: [
                        {
                          id: 'pu_xyz',
                          used_at: '2026-06-06T10:00:05',
                          display: 'email: user@mail.com\npassword: secret123',
                          data: { email: 'user@mail.com', password: 'secret123' },
                        },
                      ],
                    },
                  ],
                }, null, 2),
              }}
              error={{
                title: 'Lỗi có thể gặp',
                body: [
                  '402 Payment Required  — số dư không đủ',
                  '409 Conflict          — hết hàng hoặc đơn xử lý trùng',
                  '422 Unprocessable     — sản phẩm không phải PRE_UPLOADED / không active',
                  '503 Service Unavail.  — bot Telegram chưa sẵn sàng (thử lại sau)',
                  '502 Bad Gateway       — đã trừ tiền nhưng giao hàng thất bại\n'
                  + '                       → trường charged=true, liên hệ admin',
                ].join('\n'),
              }}
            />
            <Endpoint
              method="GET"
              path="/orders"
              summary="Lịch sử đơn hàng"
              description="Danh sách đơn hàng của người dùng (mới nhất trước). Query params: limit (mặc định 50), status."
              response={{
                title: '200 OK',
                body: JSON.stringify([
                  { id: 'a1b2c3d4', status: 'delivered', total_amount: 75000, created_at: '2026-06-06T10:00:00' },
                  { id: 'b2c3d4e5', status: 'cancelled', total_amount: 200000, created_at: '2026-06-05T14:30:00' },
                ], null, 2),
              }}
            />
            <Endpoint
              method="GET"
              path="/orders/{order_id}"
              summary="Chi tiết đơn hàng"
              description="Toàn bộ thông tin đơn kèm nội dung đã giao. Chỉ xem được đơn của chính mình (404 nếu đơn không tồn tại / không phải của bạn)."
              response={{
                title: '200 OK',
                body: JSON.stringify({
                  id: 'a1b2c3d4',
                  status: 'delivered',
                  total_amount: 75000,
                  discount_amount: 0,
                  payment_transaction_id: null,
                  created_at: '2026-06-06T10:00:00',
                  updated_at: '2026-06-06T10:00:05',
                  items: [
                    {
                      id: 'item_a1b2c3d4',
                      quantity: 1,
                      bonus_quantity: 0,
                      total_items: 1,
                      unit_price: 75000,
                      subtotal: 75000,
                      discount_amount: 0,
                      product_id: 'abc123',
                      product_name: 'Netflix Premium 1 Tháng',
                      variation_id: 'var_1',
                      variation_name: '1 tháng',
                      delivered_count: 1,
                      delivered_products: [
                        {
                          id: 'pu_xyz',
                          used_at: '2026-06-06T10:00:05',
                          display: 'email: user@mail.com\npassword: secret123',
                          data: { email: 'user@mail.com', password: 'secret123' },
                        },
                      ],
                    },
                  ],
                }, null, 2),
              }}
            />
          </Section>

          {/* Status codes */}
          <Section icon={<Eye size={15} />} title="HTTP Status Codes">
            <div className="api-status-grid">
              {[
                { code: '200', label: 'OK', color: 'success' },
                { code: '401', label: 'Unauthorized — token thiếu / sai', color: 'error' },
                { code: '402', label: 'Payment Required — không đủ số dư', color: 'error' },
                { code: '404', label: 'Not Found — sản phẩm / đơn không tồn tại', color: 'error' },
                { code: '409', label: 'Conflict — hết hàng / đơn đã xử lý', color: 'warning' },
                { code: '422', label: 'Unprocessable — sai loại sản phẩm / inactive', color: 'warning' },
                { code: '429', label: 'Rate Limited — 10 req/min cho POST /orders', color: 'warning' },
                { code: '502', label: 'Charged but undelivered — charged=true, liên hệ admin', color: 'error' },
                { code: '503', label: 'Service Unavailable — bot chưa sẵn sàng', color: 'warning' },
              ].map(({ code, label, color }) => (
                <div key={code} className="api-status-row">
                  <span className={`api-http-code api-http-code--${color}`}>{code}</span>
                  <span className="api-status-label">{label}</span>
                </div>
              ))}
            </div>
          </Section>

          {/* Quick-start */}
          <Section icon={<History size={15} />} title="Ví dụ nhanh">
            <CodeBlock
              lang="bash"
              code={`# 1. Xem sản phẩm
curl -H "Authorization: Bearer <TOKEN>" \\
  ${BASE_URL}/api/v1/products

# 2. Kiểm tra số dư
curl -H "Authorization: Bearer <TOKEN>" \\
  ${BASE_URL}/api/v1/balance

# 3. Đặt hàng
curl -X POST \\
  -H "Authorization: Bearer <TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{"variation_id":"var_1","quantity":1}' \\
  ${BASE_URL}/api/v1/orders`}
            />
          </Section>
        </div>
      </main>
    </div>
  )
}
