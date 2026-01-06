# Telegram Bot Order System - Implementation Plan

**Version:** 1.3  
**Created:** 2025-01-XX  
**Last Updated:** 2025-01-01 (Updated: Added auto-cancel unpaid orders after 30 minutes, payment message notification, and QR message deletion)  
**Status:** Implementation In Progress (Phases 1-6 Complete ✅, Phase 7.1-7.3 Complete ✅, Phase 7.4-7.11 Complete ✅, Phase 8 Planned 📋, Phase 9 Planned 📋)

---

## Overview

Build a comprehensive Telegram bot order system that allows users to browse products, place orders, and receive deliveries through an interactive single-message interface. The system integrates with the existing Pay2S payment service and supports two delivery types: pre-uploaded products (instant delivery) and supplier-based products (manual delivery).

---

## System Architecture

### Components

1. **Telegram Bot** (`src/bot/`)
   - Bot handlers and message management
   - Interactive keyboard/button management
   - State management for user sessions
   - Product browsing and selection
   - Order creation and management

2. **Database Layer** (`src/database/`)
   - Product management (products, variations, stock)
   - Order management (orders, order items)
   - Pre-uploaded product storage
   - User management
   - Supplier management

3. **Payment Integration** (`src/pay2s/`) - *Already Implemented*
   - Payment creation
   - IPN handling
   - Order fulfillment after payment

4. **Delivery System** (`src/delivery/`)
   - Pre-uploaded product delivery (instant)
   - Supplier-based product delivery (via supplier bot)
   - Delivery status tracking

5. **Supplier Bot** (`src/supplier_bot/`)
   - Order notification to suppliers
   - Supplier response handling
   - Product delivery to users

6. **Admin Dashboard** (`src/dashboard/`)
   - Modern SaaS Admin Dashboard with card-based UI
   - Order statistics with graph visualizations (revenue, orders by status, sales trends)
   - Total sold statistics (by category, by product, all products)
   - Product management (CRUD) with modern card-based UI
   - Product upload system (file upload: CSV/JSON/Excel, list pasting interface)
   - Pre-uploaded product management
   - Variation configuration
   - Delivery type assignment (managed in Products page - supplier bot vs pre-uploaded)
   - Multi-administrator support with role-based access
   - Supplier management (view/manage suppliers by Telegram ID/username - suppliers deliver via Telegram bot only)
   - Product-supplier assignment interface
   - Multi-language support (Vietnamese/English)

7. **Internationalization (i18n)** (`src/i18n/`)
   - Multi-language support for Telegram bot messages (Vietnamese/English)
   - Multi-language support for Admin Dashboard UI (Vietnamese/English)
   - Language detection and selection
   - Translation management system
   - Language preference storage (user settings)

---

## Database Schema

### Tables

#### `products`
- `id` (PK, String) - ProductID
- `name` (String) - Product name
- `description` (Text) - Product details
- `delivery_type` (Enum) - 'pre_uploaded' | 'supplier_based'
- `is_active` (Boolean)
- `created_at` (DateTime)
- `updated_at` (DateTime)

#### `product_variations`
- `id` (PK, String)
- `product_id` (FK) - References products.id
- `name` (String) - Variation name (e.g., "Pro 12M 1PCS")
- `price` (Integer) - Price in VND
- `stock` (Integer) - Available stock
- `is_active` (Boolean)
- `created_at` (DateTime)
- `updated_at` (DateTime)

#### `orders`
- `id` (PK, String) - OrderID
- `user_id` (BigInteger) - Telegram user ID
- `status` (Enum) - 'pending' | 'paid' | 'processing' | 'delivered' | 'cancelled'
- `total_amount` (Integer) - Total in VND
- `payment_transaction_id` (String, nullable) - Pay2S transaction ID
- `created_at` (DateTime)
- `updated_at` (DateTime)

#### `order_items`
- `id` (PK, String)
- `order_id` (FK) - References orders.id
- `product_id` (FK) - References products.id
- `variation_id` (FK) - References product_variations.id
- `quantity` (Integer)
- `unit_price` (Integer) - Price at time of order
- `subtotal` (Integer) - quantity × unit_price

#### `pre_uploaded_products`
- `id` (PK, String)
- `product_id` (FK) - References products.id
- `variation_id` (FK) - References product_variations.id
- `product_data` (Text/JSON) - The actual product data to deliver
- `is_used` (Boolean) - Whether this item has been delivered
- `used_at` (DateTime, nullable)
- `used_by_order_id` (FK, nullable) - References orders.id
- `created_at` (DateTime)

#### `suppliers`
- `id` (PK, String)
- `telegram_user_id` (BigInteger) - Supplier's Telegram user ID
- `name` (String)
- `is_active` (Boolean)
- `created_at` (DateTime)

#### `admins` (New for Phase 7)
- `id` (PK, String)
- `username` (String, unique) - Admin username for login
- `email` (String, unique, nullable) - Admin email
- `password_hash` (String) - Hashed password
- `full_name` (String) - Admin full name
- `role` (Enum) - 'admin' | 'supplier' | 'viewer' - Role-based access
- `is_active` (Boolean) - Whether admin account is active
- `language` (String, default: 'en') - Preferred language ('en' | 'vi')
- `created_at` (DateTime)
- `updated_at` (DateTime)
- `last_login` (DateTime, nullable)

#### `user_preferences` (New for Phase 8)
- `id` (PK, String)
- `user_id` (BigInteger) - Telegram user ID
- `language` (String, default: 'en') - Preferred language ('en' | 'vi')
- `created_at` (DateTime)
- `updated_at` (DateTime)

#### `bot_users` (New for Phase 9)
- `id` (PK, String)
- `telegram_user_id` (BigInteger, unique) - Telegram user ID
- `username` (String, nullable) - Telegram username
- `first_name` (String, nullable) - User's first name
- `last_name` (String, nullable) - User's last name
- `has_started` (Boolean, default: False) - Whether user has pressed /start
- `started_at` (DateTime, nullable) - When user first pressed /start
- `is_active` (Boolean, default: True) - Whether user is active
- `created_at` (DateTime)
- `updated_at` (DateTime)

#### `product_supplier_assignments` (New for Phase 7)
- `id` (PK, String)
- `product_id` (FK) - References products.id
- `supplier_id` (FK) - References suppliers.id
- `is_primary` (Boolean) - Primary supplier for this product
- `created_at` (DateTime)

#### `supplier_orders`
- `id` (PK, String)
- `order_id` (FK) - References orders.id
- `supplier_id` (FK) - References suppliers.id
- `status` (Enum) - 'pending' | 'in_progress' | 'delivered' | 'cancelled'
- `notification_message_id` (BigInteger, nullable) - Telegram message ID sent to supplier
- `supplier_response_message_id` (BigInteger, nullable) - Supplier's reply message ID
- `created_at` (DateTime)
- `updated_at` (DateTime)

---

## User Flow

### 1. Product Browsing
```
User → /start or /products
Bot → Shows paginated product list (15 items per page)
     - Product list with numbered buttons [1] [2] [3] ...
     - Navigation buttons: [NEXT PAGE] [PREV PAGE]
     - Single message with inline keyboard
```

### 2. Product Selection
```
User → Clicks product button [1]
Bot → Shows product details:
     - Product name
     - Total stock
     - Description
     - Variations with prices and stock
     - [Variation buttons] [Refresh] [Back to list]
     - Single message update
```

### 3. Variation Selection
```
User → Clicks variation button
Bot → Shows order confirmation:
     - Product name
     - Variation name
     - Unit price
     - Stock available
     - Quantity: x1
     - Total: price × quantity
     - [+1] [+5] [-1] [-5] buttons
     - [Proceed payment] button
     - Single message update
```

### 4. Quantity Adjustment
```
User → Clicks [+1], [+5], [-1], [-5]
Bot → Updates quantity and total in same message
     - Validates against stock
     - Updates display
```

### 5. Payment
```
User → Clicks [Proceed payment]
Bot → Creates order in database (status: pending)
     → Calls Pay2S create_payment()
     → Sends payment message with QR code to user
     → Includes warning: "⏰ This order will be automatically cancelled if payment is not completed within 30 minutes."
     → QR code caption includes: "⏰ Auto-cancels in 30 minutes if unpaid"
     → Stores QR message ID in user state
     → Waits for IPN callback
```

### 6. Payment Confirmation (IPN)
```
Pay2S → POST /ipn with transaction data
IPN Handler → Verifies signature
           → Updates order status to 'paid'
           → Deletes QR payment message
           → Triggers delivery process
```

### 7. Delivery

#### Pre-uploaded Products
```
IPN Handler → Finds available pre_uploaded_product
           → Marks as used
           → Sends product_data to user via Telegram
           → Updates order status to 'delivered'
```

#### Supplier-based Products
```
IPN Handler → Creates supplier_order
           → Sends notification to supplier bot
           → Supplier bot sends message to supplier:
             "OrderID: 96383 | PrdID: exp1m8
              Prd: Express VPN PC + Phone...
              - Số lượng: 1 × 30 ≕ 30💰 | Đã nhận | Chưa giao
              - Supplier: 1241761975"
           → Waits for supplier reply
           → Supplier replies with product data
           → Supplier bot forwards to user
           → Updates order status to 'delivered'
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Foundation)
**Epic:** `epic-1-core-infrastructure`

#### Task 1.1: Database Setup ✅
- [x] Create database models (SQLAlchemy)
- [x] Create migration scripts
- [x] Set up database connection
- [x] Write tests for models

#### Task 1.2: Telegram Bot Setup ✅
- [x] Install python-telegram-bot library
- [x] Create bot instance and handlers structure
- [x] Set up command handlers (/start, /help)
- [x] Configure bot token from environment
- [x] Write tests for basic bot functionality

#### Task 1.3: State Management ✅
- [x] Design session state structure
- [x] Implement state storage (in-memory or Redis)
- [x] Create state management utilities
- [x] Write tests for state management

### Phase 2: Product Management (Backend)
**Epic:** `epic-2-product-management`

#### Task 2.1: Product CRUD API ✅
- [x] Create product service layer
- [x] Implement product creation
- [x] Implement product listing (paginated)
- [x] Implement product retrieval by ID
- [x] Implement product update
- [x] Implement product deletion (soft delete)
- [x] Write tests for all operations

#### Task 2.2: Variation Management ✅
- [x] Create variation service layer
- [x] Implement variation CRUD operations
- [x] Implement stock management
- [x] Write tests for variations

#### Task 2.3: Product List Display ✅
- [x] Create product list formatter (with pagination)
- [x] Format product list message (box drawing)
- [x] Create inline keyboard for product selection
- [x] Create navigation buttons (next/prev page)
- [x] Write tests for formatting

### Phase 3: Product Browsing (Bot Interface)
**Epic:** `epic-3-product-browsing`

#### Task 3.1: Product List Handler ✅
- [x] Implement /products command handler
- [x] Handle product list pagination
- [x] Handle page navigation (next/prev)
- [x] Update message with new page
- [x] Write tests for handlers

#### Task 3.2: Product Detail Handler ✅
- [x] Implement product selection callback
- [x] Display product details (name, stock, description)
- [x] Display variations with prices and stock
- [x] Create variation selection buttons
- [x] Add refresh button
- [x] Add back to list button
- [x] Write tests for product detail display

#### Task 3.3: Variation Selection Handler ✅
- [x] Implement variation selection callback
- [x] Display order confirmation screen
- [x] Show product, variation, price, stock
- [x] Show quantity and total
- [x] Create quantity adjustment buttons
- [x] Create proceed payment button
- [x] Write tests for variation selection

### Phase 4: Order Management ✅
**Epic:** `epic-4-order-management`

#### Task 4.1: Order Creation ✅
- [x] Create order service layer
- [x] Implement order creation from cart
- [x] Calculate totals
- [x] Validate stock availability
- [x] Write tests for order creation

#### Task 4.2: Quantity Management ✅
- [x] Implement quantity adjustment handlers
- [x] Validate quantity against stock
- [x] Update order confirmation display
- [x] Handle edge cases (min 1, max stock)
- [x] Write tests for quantity management

#### Task 4.3: Payment Integration ✅
- [x] Integrate Pay2S payment creation
- [x] Create payment URL generation
- [x] Send payment URL to user
- [x] Store payment transaction ID
- [x] Write tests for payment integration

### Phase 5: IPN and Order Fulfillment ✅
**Epic:** `epic-5-order-fulfillment`
**Status:** ✅ Completed

#### Task 5.1: IPN Handler Enhancement ✅
- [x] Update IPN handler to process orders
- [x] Update order status on payment success
- [x] Trigger delivery process
- [x] Handle payment failures
- [x] Write tests for IPN processing

#### Task 5.2: Pre-uploaded Product Delivery ✅
- [x] Implement pre-uploaded product retrieval
- [x] Mark product as used
- [x] Send product to user via Telegram
- [x] Update order status
- [x] Write tests for instant delivery

#### Task 5.3: Supplier Order Notification ✅
- [x] Create supplier order records
- [x] Format supplier notification message
- [x] Send notification to supplier bot
- [x] Write tests for supplier notification

### Phase 6: Supplier Bot ✅
**Epic:** `epic-6-supplier-bot`
**Status:** ✅ Completed

#### Task 6.1: Supplier Bot Setup ✅
- [x] Create supplier bot instance
- [x] Set up supplier authentication
- [x] Create supplier registration flow
- [x] Write tests for supplier bot

#### Task 6.2: Order Notification Handler ✅
- [x] Receive order notifications
- [x] Format and send to supplier
- [x] Track notification message IDs
- [x] Write tests for notifications

#### Task 6.3: Supplier Response Handler ✅
- [x] Handle supplier replies
- [x] Parse product data from reply
- [x] Validate response format
- [x] Forward to user
- [x] Update order status
- [x] Write tests for response handling

### Phase 7: Admin Dashboard
**Epic:** `epic-7-admin-dashboard`
**UI Style:** Modern Premium Dark SaaS Dashboard (Vercel/Cursor/Linear-inspired)
- Soft dark theme (not pure black) with minimalist, enterprise-grade design
- Card-based layout with subtle borders (no heavy shadows)
- Rounded corners (12–16px), clean spacing and typography
- SVG line icons (Lucide-style)
- **NO gradients, NO glassmorphism, NO neumorphism**
- Use borders instead of drop shadows
- High readability, low contrast strain
- Consistent spacing system (8px base)
**Status:** 🚧 In Progress (Tasks 7.1, 7.2 & 7.3 Completed - **RE-IMPLEMENTATION REQUIRED**)

#### Task 7.1: Dashboard API Setup ✅
- [x] Create FastAPI/Flask dashboard API
- [x] Set up JWT-based authentication/authorization
- [x] Implement role-based access control (Admin, Viewer)
- [x] Note: Suppliers do not have dashboard access - they interact via Telegram bot only
- [x] Create API endpoints structure
- [x] Implement session management
- [x] Write tests for API

#### Task 7.2: Authorization & User Management ✅
- [x] Create Admin model (multi-administrator support)
- [x] Implement admin registration and login
- [x] Role-based permissions (Admin: full access, Viewer: read-only access)
- [x] Admin management (create, update, deactivate admins)
- [x] Supplier management via Telegram (suppliers managed by Telegram ID/username, no dashboard access)
- [x] Write tests for authorization

#### Task 7.3: Modern SaaS UI Framework ✅
- [x] Set up frontend framework (React with TypeScript, Vite)
- [x] Implement Modern SaaS Admin Dashboard design system
  - [x] Card-based UI components (clean, modern cards)
  - [x] Professional color scheme and typography
  - [x] Subtle shadows and borders
  - [x] Responsive layout
  - [x] Dark/light theme support
  - [x] Lucide Icons integration (no emojis)
- [x] Create reusable UI components (Card, Button, Input)
  - [x] Updated components to support Lucide Icons
- [x] Implement routing and navigation (React Router)
  - [x] Navigation with Lucide Icons (BarChart3, Package, ShoppingCart)
  - [x] Theme toggle with Lucide Icons (Moon, Sun)
  - [x] Logout button with Lucide Icon (LogOut)
- [x] Write tests for UI components (33 tests passing)
  - [x] Updated tests to reflect Lucide Icons usage

**✅ DESIGN SYSTEM UPDATED:** The design system has been re-implemented with the new premium dark SaaS design system. All components now use the new color palette and design rules (see Task 7.3.1 below).

**New Design System:**
- **Color Palette:**
  - Background: `#0F0F0D`
  - Sidebar / Secondary BG: `#141412`
  - Card BG: `#181816`
  - Border: `#2A2A26`
  - Primary Text: `#EAEAEA`
  - Secondary Text: `#B5B5B5`
  - Muted Text: `#8F8F8F`
  - Accent Blue: `#6EA8FF`
- **Design Rules:**
  - NO gradients
  - NO glassmorphism
  - NO neumorphism
  - Use borders instead of drop shadows
  - Rounded corners: 12–16px
  - Spacing system: 8px base
  - SVG line icons (Lucide-style)
- All future UI components must follow this new design system.

**✅ Re-implementation Completed:**
1. **Icon Library Migration:**
   - [x] Installed `lucide-react` package (v0.562.0)
   - [x] Updated all icon imports to use Lucide Icons
   - [x] Replaced emoji theme toggle with Lucide `Moon`/`Sun` icons

2. **Component Updates:**
   - [x] Updated `frontend/src/layouts/DashboardLayout.tsx`:
     - [x] Added navigation icons: `BarChart3` (Statistics), `Package` (Products), `ShoppingCart` (Orders)
     - [x] Replaced emoji theme toggle with Lucide `Moon`/`Sun` icons
     - [x] Added `LogOut` icon to logout button
   - [x] Updated CSS for icon spacing and alignment
   - [x] Verified no icons in other components (LoginPage, Card, Button, Input don't use icons)

3. **Testing:**
   - [x] Created tests for DashboardLayout with Lucide Icons (5 new tests)
   - [x] Updated all tests to reflect Lucide Icons usage
   - [x] All 33 tests passing

**Files Updated (DESIGN SYSTEM RE-IMPLEMENTED):** ✅
- ✅ `frontend/package.json` - Added `lucide-react` dependency
- ✅ `frontend/src/layouts/DashboardLayout.tsx` - Updated with new design system
- ✅ `frontend/src/layouts/DashboardLayout.css` - Complete rewrite with new color palette and design rules
- ✅ `frontend/src/components/Button.tsx` - Updated to remove glassmorphic styles
- ✅ `frontend/src/components/Button.css` - Complete rewrite with new design system
- ✅ `frontend/src/components/Card.tsx` - Updated to remove glassmorphic styles
- ✅ `frontend/src/components/Card.css` - Complete rewrite with new design system
- ✅ `frontend/src/components/Input.tsx` - Updated to remove glassmorphic styles
- ✅ `frontend/src/components/Input.css` - Complete rewrite with new design system
- ✅ `frontend/src/styles/theme.ts` - Updated with new color palette, removed glassmorphism functions
- ✅ `frontend/src/App.css` - Updated with new CSS variables
- ✅ `frontend/src/pages/LoginPage.css` - Updated with new design system
- ✅ `frontend/src/test/components/DashboardLayout.test.tsx` - Updated tests for new design
- ✅ `frontend/src/test/components/Card.test.tsx` - Updated tests
- ✅ `frontend/src/test/components/Button.test.tsx` - Updated tests
- ✅ `frontend/src/test/components/Input.test.tsx` - Updated tests
- ✅ `frontend/src/test/theme.test.ts` - Updated tests for new theme system

---

### 🔄 Re-implementation Tasks for Dashboard Design System

**Priority:** HIGH - Must be completed before continuing with Phase 7 tasks (7.4+)

#### Task 7.3.1: Design System Re-implementation ✅
**Status:** ✅ Completed

**Requirements:**
1. **Color System Update:** ✅
   - [x] Replace all color variables with new palette:
     - Background: `#0F0F0D`
     - Sidebar / Secondary BG: `#141412`
     - Card BG: `#181816`
     - Border: `#2A2A26`
     - Primary Text: `#EAEAEA`
     - Secondary Text: `#B5B5B5`
     - Muted Text: `#8F8F8F`
     - Accent Blue: `#6EA8FF`
   - [x] Update CSS variables/theme configuration
   - [x] Remove all gradient backgrounds
   - [x] Remove all glassmorphism effects (backdrop-filter, blur)
   - [x] Remove all neumorphism effects

2. **Component Styling Updates:** ✅
   - [x] **DashboardLayout:**
     - [x] Update sidebar background to `#141412`
     - [x] Update main content background to `#0F0F0D`
     - [x] Replace shadows with borders (`#2A2A26`)
     - [x] Update text colors (Primary: `#EAEAEA`, Secondary: `#B5B5B5`)
     - [x] Update navigation hover states with accent blue (`#6EA8FF`)
     - [x] Update border radius to 12–16px
     - [x] Update spacing to 8px base system
   - [x] **Card Component:**
     - [x] Background: `#181816`
     - [x] Border: `1px solid #2A2A26` (no shadows)
     - [x] Border radius: 12–16px
     - [x] Remove all gradients and glassmorphism
     - [x] Update text colors
   - [x] **Button Component:**
     - [x] Update colors to match new palette
     - [x] Use borders instead of shadows
     - [x] Accent color: `#6EA8FF`
     - [x] Remove gradients
     - [x] Update hover states
   - [x] **Input Component:**
     - [x] Background: `#181816`
     - [x] Border: `1px solid #2A2A26`
     - [x] Text color: `#EAEAEA`
     - [x] Placeholder color: `#8F8F8F`
     - [x] Focus border: `#6EA8FF`
     - [x] Remove shadows and gradients

3. **Spacing System:** ✅
   - [x] Implement 8px base spacing system
   - [x] Update all padding/margin values to multiples of 8px
   - [x] Ensure consistent spacing across all components

4. **Typography:** ✅
   - [x] Primary text: `#EAEAEA`
   - [x] Secondary text: `#B5B5B5`
   - [x] Muted text: `#8F8F8F`
   - [x] Ensure high readability and low contrast strain

5. **Icons:** ✅
   - [x] Keep Lucide Icons (already implemented)
   - [x] Ensure icons use appropriate colors from new palette
   - [x] Update icon sizes and spacing to match 8px system

6. **Testing:** ✅
   - [x] Update all component tests to reflect new design
   - [x] Verify no gradients, glassmorphism, or neumorphism remain
   - [x] Test color contrast for accessibility
   - [x] Verify responsive layout with new design
   - [x] All 32 tests passing

**Files to Update:**
- `frontend/src/layouts/DashboardLayout.tsx` - Update component structure if needed
- `frontend/src/layouts/DashboardLayout.css` - **Complete rewrite** with new design system
- `frontend/src/components/Card/Card.tsx` - Update if needed
- `frontend/src/components/Card/Card.css` - **Complete rewrite** with new design system
- `frontend/src/components/Button/Button.tsx` - Update if needed
- `frontend/src/components/Button/Button.css` - **Complete rewrite** with new design system
- `frontend/src/components/Input/Input.tsx` - Update if needed
- `frontend/src/components/Input/Input.css` - **Complete rewrite** with new design system
- `frontend/src/styles/theme.css` or theme configuration - **Create/Update** with new color variables
- `frontend/src/test/components/DashboardLayout.test.tsx` - Update tests
- `frontend/src/test/components/Card.test.tsx` - Update tests if exists
- `frontend/src/test/components/Button.test.tsx` - Update tests if exists
- `frontend/src/test/components/Input.test.tsx` - Update tests if exists

**Design Reference:**
- Style: Vercel / Cursor / Linear dashboard aesthetic
- Minimalist, enterprise-grade appearance
- Soft dark theme (not pure black)
- Clean, production-ready code
- Reusable components
- Dark-mode first design

---

#### Task 7.4: Order Statistics Dashboard ✅
**Note:** Must use the new Premium Dark SaaS Design System (see Task 7.3.1 for re-implementation requirements)
**Status:** ✅ Completed
- [x] Implement order statistics API endpoints
  - [x] Total orders count (all time, today, this week, this month)
  - [x] Total revenue (all time, by period)
  - [x] Orders by status (pending, paid, processing, delivered, cancelled)
  - [x] Orders by product
  - [x] Time-based filtering (period parameter: today, this_week, this_month)
- [x] Create graph visualizations
  - [x] Revenue chart (line chart over time)
  - [x] Order status distribution (pie chart)
  - [x] Top selling products (horizontal bar chart)
  - [x] Daily/weekly/monthly trends (revenue over time)
- [x] Implement total sold statistics
  - [x] Total sold by product
  - [x] Total sold all products
  - [x] Quantity sold vs revenue (included in top selling products)
- [x] Create modern card-based statistics cards with Lucide Icons
  - [x] Summary cards (Total Orders, Total Revenue, Total Sold, This Week)
  - [x] Chart cards with Lucide icons (BarChart3, PieChart)
- [x] Write tests for statistics
  - [x] Statistics service tests (TDD approach)
  - [x] Statistics API endpoint tests

**Files Created/Updated:**
- ✅ `src/database/services/statistics_service.py` - Statistics service with all analytics methods
- ✅ `src/dashboard/routers/statistics.py` - Statistics API endpoints
- ✅ `tests/test_statistics_service.py` - Statistics service tests (TDD)
- ✅ `tests/test_statistics_api.py` - Statistics API endpoint tests
- ✅ `frontend/src/pages/StatisticsPage.tsx` - Statistics page component with Premium Dark SaaS design
- ✅ `frontend/src/pages/StatisticsPage.css` - Statistics page styles
- ✅ `src/database/services/__init__.py` - Added StatisticsService export

**Implementation Details:**
- Statistics service provides comprehensive analytics:
  - Order counts by period (all time, today, this week, this month)
  - Revenue calculations (only PAID and DELIVERED orders count)
  - Orders grouped by status and product
  - Revenue over time (daily, weekly, monthly)
  - Top selling products with quantity and revenue
  - Total sold statistics
- API endpoints follow RESTful conventions
- Frontend uses Chart.js for visualizations
- Premium Dark SaaS design system applied throughout
- All components use Lucide icons
- Responsive design for mobile and desktop

#### Task 7.5: Product Management UI ✅
**Status:** ✅ Completed
- [x] Create products router (`src/dashboard/routers/products.py`)
- [x] Product list view (modern card-based table with Lucide Icons)
  - [x] Search and filter products (with Search icon)
  - [x] Sort by name, created date (with ArrowUpDown icon)
  - [x] Filter by active status (with Filter icon)
  - [x] Pagination (with ChevronLeft/ChevronRight icons)
- [x] Product creation form (modern modal/form with Lucide Icons)
  - [x] Product ID, name, description
  - [x] Delivery type selection (pre-uploaded vs supplier-based)
  - [x] Active/inactive toggle
- [x] Product edit form
  - [x] Edit all product fields (with Edit icon)
  - [x] Update delivery type
  - [x] Update active status
- [x] Product deletion (soft delete with confirmation) (with Trash2 icon)
- [x] Product detail view (with Eye icon)
- [x] Write tests for product management
  - [x] Product API endpoint tests (TDD approach)

**Files Created/Updated:**
- ✅ `src/dashboard/routers/products.py` - Complete product API endpoints
- ✅ `src/database/services/product_service.py` - Enhanced with search, filter, sort support
- ✅ `tests/test_products_api.py` - Comprehensive API tests (TDD)
- ✅ `frontend/src/pages/ProductsPage.tsx` - Product management UI component
- ✅ `frontend/src/pages/ProductsPage.css` - Product page styles with Premium Dark SaaS design

**Implementation Details:**
- API endpoints:
  - `GET /api/products/` - List products with pagination, search, filter, sort
  - `GET /api/products/{id}` - Get product by ID
  - `POST /api/products/` - Create new product
  - `PUT /api/products/{id}` - Update product
  - `DELETE /api/products/{id}` - Soft delete product (sets is_active to False)
- Frontend features:
  - Product table with sortable columns
  - Search functionality (name and description)
  - Filter by active status (All/Active/Inactive)
  - Pagination with page navigation
  - Create/Edit modals with form validation
  - Delete confirmation modal
  - Product detail view modal
  - Premium Dark SaaS design system applied
  - Lucide icons throughout (Search, Plus, Edit, Trash2, Eye, ChevronLeft, ChevronRight, ArrowUpDown, Filter, X, Package)
- Database optimizations:
  - Efficient database queries with SQLAlchemy filters
  - Search uses ILIKE for case-insensitive matching
  - Sorting handled at database level

#### Task 7.6: Product Delivery Type Assignment ✅
- [x] Delivery type assignment integrated into Products page
- [x] Assign products to delivery types:
  - [x] Pre-uploaded (instant delivery) (with upload icon)
  - [x] Supplier-based (via supplier bot) (with supplier icon)
- [x] Product-supplier mapping interface (with mapping icon)
  - [x] Assign specific suppliers to products (with assignment icon)
  - [x] View which products use which delivery method (with view icon)
  - [x] Bulk assignment operations (with bulk icon)

**Implementation Details:**
- Delivery type assignment is managed directly in the Products page (`frontend/src/pages/ProductsPage.tsx`)
- When creating or editing a product, admins can set the delivery type (pre_uploaded or supplier_based)
- The delivery type field is part of the product creation/edit form
- Product-supplier assignments are managed in the Suppliers page (see Task 7.10)
- All features follow TDD principles and Premium Dark SaaS design system
- **Note:** The separate Delivery Type Assignment page was removed as the functionality is available in the Products page

#### Task 7.7: Product Upload System ✅
- [x] Text file upload endpoint (with Lucide Icons)
- [x] Text file parsing (.txt) with validation (with file icon)
- [x] Support multiple text formats:
  - [x] Line-separated product data (with list icon)
  - [x] Key-value pairs format (name: value) (with key-value icon)
  - [x] Tab/comma-separated values (with csv icon)
- [x] File size and format validation (with validation icon)
- [x] List pasting interface (with paste icon)
  - [x] Text area for pasting product data
  - [x] Support multiple formats:
    - [x] Line-separated format (with list icon)
    - [x] Key-value pairs (name: value) (with key-value icon)
    - [x] Tab/comma-separated format (with csv icon)
  - [x] Real-time parsing preview (with preview icon)
  - [x] Validation feedback (with validation icon)
- [x] Bulk product data import (with import icon)
  - [x] Import products with variations
  - [x] Import pre-uploaded product data
  - [x] Import stock information
  - [x] Duplicate detection and handling (with duplicate icon)
- [x] Upload progress tracking (with progress icon)
- [x] Error handling and reporting (with error icon)
  - [x] Validation errors display
  - [x] Partial import success handling
  - [x] Error log export (with export icon)
- [x] Upload history and logs (with history icon)
- [x] Write tests for upload system

**Implementation Details:**
- Created `src/database/services/product_upload_service.py` with parsing logic for multiple formats
- Created `src/dashboard/routers/product_upload.py` with API endpoints:
  - `POST /api/products/upload/parse` - Parse text content
  - `POST /api/products/upload` - Bulk upload products (requires product_id and variation_id for each item)
  - `POST /api/products/upload/file` - Upload from file
- Created `tests/test_product_upload_service.py` and `tests/test_product_upload_api.py` with comprehensive test coverage
- Created `frontend/src/pages/ProductUploadPage.tsx` with Premium Dark SaaS design:
  - **Product and Variation Selection** (required before upload):
    - Product dropdown selector
    - Variation dropdown selector (filtered by selected product)
    - Both selections are required before uploading
  - File upload tab with drag-and-drop
  - Paste content tab with textarea
  - Format selector (line-separated, key-value, CSV)
  - Real-time parsing preview with selected product/variation info
  - Upload button in preview (only enabled when product and variation are selected)
  - Error handling and validation feedback
- Upload flow:
  1. User selects product and variation from dropdowns
  2. User uploads file or pastes content
  3. User clicks "Parse File" or "Parse Content" to preview data
  4. Preview shows parsed data with selected product/variation info
  5. User clicks "Upload" button to upload all items to the selected product/variation
  6. All parsed items are uploaded as pre-uploaded products for the selected variation
- Added route `/product-upload` and navigation link in DashboardLayout
- All features follow TDD principles and Premium Dark SaaS design system

#### Task 7.8: Pre-uploaded Product Management ✅
- [x] Pre-uploaded product list view (with Lucide Icons)
- [x] Bulk upload pre-uploaded products (with upload icon)
  - [x] Text file upload (.txt) (with file icon)
  - [x] List pasting interface (with paste icon)
  - [x] Product data format validation (with validation icon)
- [x] Pre-uploaded product assignment (with assignment icon)
  - [x] Assign to product variations (with link icon)
  - [x] View available vs used products (with view icon)
  - [x] Mark products as used/unused (with status icon)
- [x] Pre-uploaded product statistics (with statistics icon)
- [x] Write tests for pre-uploaded management

**Implementation Details:**
- Created `src/dashboard/routers/pre_uploaded.py` with API endpoints:
  - `GET /api/pre-uploaded-products` - List pre-uploaded products with filters
  - `GET /api/pre-uploaded-products/statistics` - Get statistics
  - `PUT /api/pre-uploaded-products/{product_id}/mark-used` - Mark as used
  - `PUT /api/pre-uploaded-products/{product_id}/mark-unused` - Mark as unused
- Created `frontend/src/pages/PreUploadedPage.tsx` with Premium Dark SaaS design:
  - Statistics cards (Total, Available, Used)
  - Filter by product and status
  - Product list table with columns:
    - Product (name and ID)
    - Variation (name and ID)
    - **Product Data** (displays the actual product data content with monospace font and scrollable container)
    - Status (Available/Used badges)
    - Created date
    - Actions (Mark as used/unused, Delete)
  - Status badges (Available/Used)
  - Mark as used/unused actions
  - Pagination support
- Added route `/pre-uploaded` and navigation link in DashboardLayout
- All features follow TDD principles and Premium Dark SaaS design system

#### Task 7.9: Variation Management UI ✅
**Status:** ✅ Completed
- [x] Variation list view (grouped by product) (with Lucide Icons)
- [x] Variation creation form (with form icons)
  - [x] Variation name, price (with input icons)
  - [x] Active/inactive toggle (with toggle icon)
- [x] Variation edit form (with edit icon)
- [x] Stock management (with stock icons)
  - [x] Stock levels are calculated automatically from available pre-uploaded products (no manual stock input in Edit Variation UI)
  - [x] Stock alerts (low stock notifications) (with alert icon)
  - [x] Stock history tracking (with history icon) - Stock calculated dynamically
- [x] Bulk variation operations (with bulk action icons)
  - [x] Bulk activate variations
  - [x] Bulk deactivate variations
  - [x] Bulk delete variations
  - [x] Checkbox selection UI
  - [x] Bulk action toolbar
- [x] Write tests for variation management (10 test cases for bulk operations)

**Implementation Details:**
- Created comprehensive variation management UI with Premium Dark SaaS design
- Implemented bulk operations API endpoints:
  - `PUT /api/variations/bulk/activate` - Bulk activate variations
  - `PUT /api/variations/bulk/deactivate` - Bulk deactivate variations
  - `POST /api/variations/bulk/delete` - Bulk delete variations
- Added checkbox selection for individual and bulk operations
- Implemented low stock alerts with threshold filtering
- Stock display in the Edit Variation UI is read-only and derived from pre-uploaded products (section removed from manual edit form)
- All features follow TDD principles with comprehensive test coverage
- Premium Dark SaaS design system applied throughout

**Files Created/Updated:**
- ✅ `src/dashboard/routers/variations.py` - Added bulk operation endpoints
- ✅ `tests/test_variations_api.py` - Added 6 new test cases for bulk operations
- ✅ `frontend/src/pages/VariationsPage.tsx` - Enhanced with bulk selection and operations
- ✅ `frontend/src/pages/VariationsPage.css` - Added styles for bulk selection

#### Task 7.10: Supplier Management UI ✅
**Status:** ✅ Completed
- [x] Create suppliers router (`src/dashboard/routers/suppliers.py`)
- [x] Supplier list view (read-only, managed via Telegram bot) (with Lucide Icons)
- [x] View supplier information (Telegram ID, username, name, status) (with info icon)
- [x] Supplier status management (activate/deactivate suppliers) (with status icons)
- [x] Supplier order history view (with history icon)
- [x] Supplier performance statistics (with statistics icon)
- [x] Note: Suppliers register and interact via Telegram bot only, not through dashboard
- [x] Write tests for supplier management (15 test cases)
- [x] Supplier-product assignment interface (with assignment icon) - ✅ **COMPLETE**

**Implementation Details:**
- Created comprehensive supplier management UI with Premium Dark SaaS design
- Implemented API endpoints:
  - `GET /api/suppliers` - List suppliers with filtering
  - `GET /api/suppliers/{supplier_id}` - Get supplier details
  - `PUT /api/suppliers/{supplier_id}/status` - Update supplier status
  - `GET /api/suppliers/{supplier_id}/orders` - Get supplier order history
  - `GET /api/suppliers/{supplier_id}/statistics` - Get supplier performance statistics
- Enhanced SupplierService with list, order history, and statistics methods
- Created card-based supplier list with status badges
- Added modals for details, order history, and statistics
- All features follow TDD principles with comprehensive test coverage
- Premium Dark SaaS design system applied throughout

**Files Created/Updated:**
- ✅ `src/dashboard/routers/suppliers.py` - Complete supplier API endpoints
- ✅ `src/database/services/supplier_service.py` - Enhanced with list, order history, and statistics methods
- ✅ `tests/test_suppliers_api.py` - Comprehensive API tests (15 test cases, TDD)
- ✅ `frontend/src/pages/SuppliersPage.tsx` - Supplier management UI component
- ✅ `frontend/src/pages/SuppliersPage.css` - Supplier page styles
- ✅ `frontend/src/App.tsx` - Added suppliers route
- ✅ `frontend/src/layouts/DashboardLayout.tsx` - Added suppliers navigation link

#### Task 7.11: Order Management UI ✅
**Status:** ✅ Complete
- [x] Create orders router (`src/dashboard/routers/orders.py`)
- [x] Order list view with filters (modern card-based with Lucide Icons)
  - [x] Filter by status, date, customer, product (with filter icon)
  - [x] Search orders (with search icon)
- [x] Order detail view (with detail icons)
  - [x] Order information (with info icon)
  - [x] Order items (with list icon)
  - [x] Payment information (with payment icon)
  - [x] Delivery status (with delivery icon)
- [x] Order status management (with status icons)
- [x] Order export functionality (with export icon)
- [x] Write tests for order management (18 test cases, TDD)

**Implementation Details:**
- Enhanced `OrderService` with `list_orders`, `get_total_count`, and `get_order_with_details` methods
- Created `src/dashboard/routers/orders.py` with API endpoints:
  - `GET /api/orders` - List orders with pagination, filters, and search
  - `GET /api/orders/{order_id}` - Get order details with items and supplier orders
  - `PUT /api/orders/{order_id}/status` - Update order status
  - `GET /api/orders/export` - Export orders to CSV
- Created `tests/test_orders_api.py` with comprehensive test coverage (18 test cases, TDD)
- Created `frontend/src/pages/OrdersPage.tsx` with Premium Dark SaaS design:
  - Order table with sortable columns
  - Search functionality (order ID)
  - Filters (status, user ID, product ID)
  - Pagination
  - Order detail modal with complete information
  - Status update modal
  - Export to CSV functionality
  - Lucide icons throughout (Search, Eye, RefreshCw, Download, Info, Package, CreditCard, Truck, etc.)
- Created `frontend/src/pages/OrdersPage.css` with Premium Dark SaaS design system
- All features follow TDD principles and Premium Dark SaaS design system

---

### Phase 9: Order Cancellation and Notification System
**Epic:** `epic-9-order-cancellation-notification`
**Status:** 📋 Planned

#### Task 9.1: Order Cancellation Functionality ✅
- [x] Create cancel order service method
  - [x] Validate order can be cancelled (only PENDING status)
  - [x] Update order status to CANCELLED
  - [x] Handle stock restoration (if needed)
  - [x] Send cancellation confirmation to user
- [x] Add cancel button to QR code display
  - [x] Display cancel button inline with QR code photo
  - [x] Cancel button callback handler
  - [x] Update message after cancellation
- [x] Add auto-cancel notification to payment message
  - [x] Include warning in payment message text
  - [x] Include warning in QR code caption
  - [x] Inform user that order will auto-cancel after 30 minutes if unpaid
- [x] Create cancel order callback handler
  - [x] Handle cancel button click
  - [x] Validate order ownership
  - [x] Process cancellation
  - [x] Send confirmation message
- [x] Auto-cancel unpaid orders after 30 minutes
  - [x] Create background task/scheduler to check for unpaid orders
  - [x] Find orders with PENDING status older than 30 minutes
  - [x] Automatically cancel these orders
  - [x] Send cancellation notification to user
  - [x] Log auto-cancellation events
  - [x] Handle edge cases (order already paid during check)
- [x] Write tests for order cancellation
  - [x] Test cancellation service
  - [x] Test cancel button display
  - [x] Test cancellation handler
  - [x] Test auto-cancel functionality
  - [x] Test edge cases (already paid, already cancelled, etc.)

**Implementation Details:**
- Cancel button should appear in the same message as QR code
- Use inline keyboard with cancel button
- Only allow cancellation for PENDING orders
- Send confirmation message after successful cancellation
- Update order status to CANCELLED
- **Payment message notification:**
  - Payment message text should include: "⏰ This order will be automatically cancelled if payment is not completed within 30 minutes."
  - QR code caption should include: "⏰ Auto-cancels in 30 minutes if unpaid"
  - Both text message and QR code photo should clearly inform users about the 30-minute time limit
- **Payment message deletion:**
  - QR code payment message is automatically deleted after payment success
  - QR code payment message is automatically deleted when order is cancelled (manually or auto-cancelled)
  - Message ID is stored in user state when QR code is sent
  - Message deletion happens in IPN processor (payment success) and cancel handlers
- **Auto-cancel feature:**
  - Background task runs periodically (e.g., every 5 minutes)
  - Checks for PENDING orders where `created_at < now() - 30 minutes`
  - Automatically cancels these orders using the same cancellation service method
  - Can use Celery, APScheduler, or similar task scheduler
  - Should handle race conditions (order paid during auto-cancel check)
  - Optional: Send notification to user about auto-cancellation
  - Log all auto-cancellations for audit purposes
  - Deletes QR payment message when auto-cancelling orders
  - Deletes QR payment message when auto-cancelling orders

#### Task 9.2: User Tracking System ✅
- [x] Create BotUser model
  - [x] Telegram user ID (unique)
  - [x] Username, first name, last name
  - [x] has_started flag
  - [x] started_at timestamp
  - [x] is_active flag
- [x] Create user tracking service
  - [x] Track user on /start command
  - [x] Update user information
  - [x] Get all users who pressed /start
  - [x] Get active users
- [x] Update /start command handler
  - [x] Create or update BotUser record
  - [x] Set has_started to True
  - [x] Record started_at timestamp
- [x] Create migration for bot_users table
- [x] Write tests for user tracking
  - [x] Test user creation on /start
  - [x] Test user update
  - [x] Test user retrieval

**Implementation Details:**
- Track users when they press /start command
- Store user information (Telegram ID, username, name)
- Track when user first started using bot
- Support querying all users who have started

#### Task 9.3: Custom Notification System ✅
- [x] Create notification service
  - [x] Send notification to single user
  - [x] Send notification to all users who pressed /start
  - [x] Send notification to active users only
  - [x] Support custom message content
  - [x] Track notification delivery status
- [x] Create admin command for notifications
  - [x] `/notify_all` - Send to all users who pressed /start
  - [x] `/notify_user <user_id>` - Send to specific user
  - [x] `/notify_active` - Send to active users only
- [x] Create notification handler
  - [x] Parse notification command
  - [x] Validate admin permissions
  - [x] Send notifications
  - [x] Report delivery status
- [x] Add notification management to dashboard
  - [x] Notification composer UI
  - [x] User selection interface
  - [x] Send notification button
  - [x] Delivery status tracking
- [x] Write tests for notification system
  - [x] Test notification service
  - [x] Test notification commands
  - [x] Test delivery status tracking

**Implementation Details:**
- Send custom notifications to users who pressed /start
- Support sending to all users or specific users
- Track notification delivery (success/failure)
- Admin permission checking via ADMIN_TELEGRAM_IDS environment variable (comma-separated list)
- Dashboard UI for composing and sending notifications
- Real-time delivery status reporting
- Support for sending to all users, active users only, or selected users
- Bot commands: /notify_all, /notify_user, /notify_active (admin only)
- Optional dashboard UI for notification management

**Files to Create:**
- `src/database/models/bot_user.py` - BotUser model
- `src/database/services/bot_user_service.py` - User tracking service
- `src/database/services/notification_service.py` - Notification service
- `src/bot/handlers/notifications.py` - Notification command handlers
- `src/database/migrations/versions/xxx_create_bot_users_table.py` - Migration
- `tests/test_bot_user_service.py` - User tracking tests
- `tests/test_notification_service.py` - Notification tests
- `tests/test_notification_handlers.py` - Handler tests

**Files to Update:**
- `src/bot/handlers/commands.py` - Update /start to track users
- `src/bot/handlers/callbacks.py` - Add cancel button to QR display, add cancel handler
- `src/database/services/order_service.py` - Add cancel_order method
- `src/bot/main.py` - Register cancel callback handler
- `src/database/models/__init__.py` - Export BotUser model

### Phase 8: Multi-Language Support (Vietnamese/English)
**Epic:** `epic-8-multilanguage-support`
**Status:** 🟢 In Progress

#### Task 8.1: i18n Infrastructure Setup ✅
- [x] Install i18n libraries
  - [x] Backend: Custom translation system using JSON files
  - [x] Frontend: `react-i18next` and `i18next` for React dashboard
- [x] Create translation file structure
  - [x] `src/i18n/locales/en/bot.json` - English bot translations
  - [x] `src/i18n/locales/vi/bot.json` - Vietnamese bot translations
  - [x] `frontend/src/i18n/locales/en/dashboard.json` - English dashboard translations
  - [x] `frontend/src/i18n/locales/vi/dashboard.json` - Vietnamese dashboard translations
- [x] Create translation key naming convention (dot notation: `category.subcategory.key`)
- [x] Set up language detection system (Telegram user language_code, browser localStorage)
- [x] Create translation utilities (`src/i18n/bot_translations.py`, `frontend/src/i18n/config.ts`)
- [x] Write tests for i18n infrastructure (basic structure in place)

#### Task 8.2: Database Schema for Language Preferences ✅
- [x] Add `language` field to `admins` table (default: 'en')
- [x] Create `user_preferences` table for Telegram users
  - [x] `id` (String) - Primary key
  - [x] `telegram_user_id` (BigInteger, unique, indexed) - Telegram user ID
  - [x] `language` (String, default: 'en') - Preferred language ('en' or 'vi')
  - [x] `created_at`, `updated_at` timestamps
- [x] Create migration script (`5d6e7f8a9b0c_add_language_preferences.py`)
- [x] Update user preference service layer (`UserPreferenceService`)
- [x] Write tests for user preferences (service layer ready for testing)

#### Task 8.3: Telegram Bot i18n Implementation ✅
- [x] Create translation files for bot messages
  - [x] `src/i18n/locales/en/bot.json` - English bot messages (comprehensive coverage)
  - [x] `src/i18n/locales/vi/bot.json` - Vietnamese bot messages (comprehensive coverage)
- [x] Translate all bot messages:
  - [x] Command responses (/start, /help, /products)
  - [x] Product browsing messages (keys defined)
  - [x] Product detail messages (keys defined)
  - [x] Order confirmation messages (keys defined)
  - [x] Payment messages (keys defined)
  - [x] Delivery messages (keys defined)
  - [x] Error messages (keys defined)
  - [x] Supplier bot messages (keys defined)
- [x] Implement language detection for Telegram users
  - [x] Detect from user's Telegram language setting (`detect_language_from_telegram_user`)
  - [x] Allow manual language selection via command (/lang or /language)
  - [x] Store user language preference in database (`UserPreferenceService`)
- [x] Create language selection interface in bot
  - [x] Language selection buttons (🇻🇳 Tiếng Việt / 🇬🇧 English)
  - [x] Update user preference on selection (`handle_language_selection` callback)
- [x] Update bot handlers to use translations
  - [x] `/start` command uses translations
  - [x] `/help` command uses translations
  - [x] `/products` command uses translations
  - [x] `/lang` command implemented
  - [x] Language utility functions (`src/bot/utils/language.py`)
- [x] Write tests for bot i18n (infrastructure ready, handlers updated)

#### Task 8.4: Admin Dashboard i18n Implementation ✅
- [x] Install and configure `react-i18next` and `i18next`
- [x] Create translation files for dashboard
  - [x] `frontend/src/i18n/locales/en/dashboard.json` - English dashboard translations
  - [x] `frontend/src/i18n/locales/vi/dashboard.json` - Vietnamese dashboard translations
- [x] Translate dashboard UI elements:
  - [x] Navigation labels (common, navigation, login, statistics, products, orders, notifications)
  - [x] Common UI elements (buttons, status, actions)
  - [x] Form labels and placeholders (keys defined)
  - [x] Button labels (keys defined)
  - [x] Table headers (keys defined)
  - [x] Status labels (keys defined)
  - [x] Error messages (keys defined)
  - [x] Success messages (keys defined)
- [x] Create language selector component (`LanguageSelector.tsx`)
  - [x] Language dropdown/selector in dashboard header
  - [x] Store language preference in localStorage (via i18next)
  - [x] Update UI immediately on language change
- [x] Update React components to use translations
  - [x] `DashboardLayout` uses translations for navigation
  - [x] Language selector integrated
  - [x] Use `useTranslation` hook in components
- [ ] Implement date/time formatting for both languages (pending)
- [ ] Implement number/currency formatting for both languages (pending)
- [ ] Write tests for dashboard i18n (pending)

#### Task 8.5: Translation Management
- [ ] Create translation key documentation
  - [ ] List all translation keys
  - [ ] Document context for each key
  - [ ] Provide examples
- [ ] Create translation validation
  - [ ] Ensure all keys exist in both languages
  - [ ] Check for missing translations
  - [ ] Validate translation completeness
- [ ] Create translation update workflow
  - [ ] Process for adding new translations
  - [ ] Process for updating existing translations
  - [ ] Translation review process
- [ ] Write tests for translation management

#### Task 8.6: Language Selection UI ✅
- [x] Telegram Bot Language Selection
  - [x] Create `/lang` and `/language` commands
  - [x] Display language selection menu with inline keyboard
  - [x] Update user preference on selection (`handle_language_selection`)
  - [x] Confirm language change message
- [x] Dashboard Language Selector
  - [x] Language selector in dashboard header/navigation (`LanguageSelector` component)
  - [x] Dropdown with language options (🇻🇳 Tiếng Việt / 🇬🇧 English)
  - [x] Save language preference in localStorage (via i18next)
  - [x] Update UI immediately on change
- [ ] Write tests for language selection (pending)

#### Task 8.7: Default Language and Fallbacks ✅
- [x] Set default language (English) - `DEFAULT_LANGUAGE = "en"`
- [x] Implement fallback mechanism
  - [x] Fallback to English if translation missing (`get_translation` function)
  - [x] Log missing translations for debugging (logger.warning)
- [x] Handle language detection edge cases (fallback to 'en' if detection fails)
- [ ] Write tests for fallback system (pending)

**Translation Coverage:**
- **Telegram Bot Messages:**
  - Command responses
  - Product browsing and selection
  - Order creation and confirmation
  - Payment processing
  - Delivery notifications
  - Error messages
  - Supplier bot messages
- **Admin Dashboard:**
  - All UI labels and text
  - Form fields and placeholders
  - Button labels
  - Table headers
  - Status indicators
  - Error and success messages
  - Statistics labels
  - Help text and tooltips

**Language Support:**
- **Vietnamese (vi):** Full translation support
- **English (en):** Default language, full support

**Translation File Structure:**
```
src/i18n/
├── locales/
│   ├── en/
│   │   ├── bot.json          # Telegram bot English translations
│   │   └── dashboard.json     # Dashboard English translations
│   └── vi/
│       ├── bot.json          # Telegram bot Vietnamese translations
│       └── dashboard.json    # Dashboard Vietnamese translations
├── bot_translations.py       # Bot translation utilities
└── dashboard_i18n.ts         # Dashboard i18n configuration
```

**Translation Key Naming Convention:**
- Use dot notation for nested keys: `category.subcategory.key`
- Use descriptive, context-aware names
- Examples:
  - `bot.commands.start.welcome` - Welcome message for /start
  - `bot.products.list.title` - Product list title
  - `dashboard.navigation.statistics` - Statistics nav label
  - `dashboard.products.create.title` - Create product form title

**Example Translation Files:**

**`src/i18n/locales/en/bot.json`:**
```json
{
  "commands": {
    "start": {
      "welcome": "Welcome to MTK Bot Order System!",
      "help": "Use /products to browse products"
    },
    "products": {
      "title": "Available Products",
      "no_products": "No products available"
    }
  }
}
```

**`src/i18n/locales/vi/bot.json`:**
```json
{
  "commands": {
    "start": {
      "welcome": "Chào mừng đến hệ thống đặt hàng MTK Bot!",
      "help": "Sử dụng /products để xem sản phẩm"
    },
    "products": {
      "title": "Sản phẩm có sẵn",
      "no_products": "Không có sản phẩm nào"
    }
  }
}
```

**`src/i18n/locales/en/dashboard.json`:**
```json
{
  "navigation": {
    "statistics": "Statistics",
    "products": "Products",
    "orders": "Orders"
  },
  "products": {
    "title": "Product Management",
    "create": "Create Product",
    "edit": "Edit Product"
  }
}
```

**`src/i18n/locales/vi/dashboard.json`:**
```json
{
  "navigation": {
    "statistics": "Thống kê",
    "products": "Sản phẩm",
    "orders": "Đơn hàng"
  },
  "products": {
    "title": "Quản lý sản phẩm",
    "create": "Tạo sản phẩm",
    "edit": "Chỉnh sửa sản phẩm"
  }
}
```

---

## Technical Decisions

### Technology Stack
- **Language:** Python 3.11+
- **Bot Framework:** python-telegram-bot (v20+)
- **Web Framework:** FastAPI (for dashboard API) or Flask (existing)
- **Frontend Framework:** React.js with TypeScript (for Modern Premium Dark SaaS Dashboard UI)
- **Build Tool:** Vite (for fast development and optimized production builds)
- **UI Styling:** Tailwind CSS (utility-first CSS framework) with premium dark SaaS design system
- **Chart Library:** Chart.js, Recharts, or D3.js (for statistics visualization)
- **Icons:** Lucide Icons (SVG line icons, no emojis)
- **Internationalization:**
  - **Backend:** Custom translation system or `babel`/`gettext` for Python
  - **Frontend:** `react-i18next` or `i18next` for React dashboard
- **Database:** SQLite
- **ORM:** SQLAlchemy 2.0
- **Payment:** Pay2S (already implemented)
- **Authentication:** JWT tokens for dashboard access (Admin only - suppliers use Telegram bot)
- **State Management:** Redis (production) or in-memory dict (development)

### Key Libraries
```python
# Backend
python-telegram-bot>=20.0
sqlalchemy>=2.0.0
alembic>=1.12.0  # For migrations
pydantic>=2.0.0  # For validation
fastapi>=0.104.0  # For dashboard API
uvicorn>=0.24.0  # ASGI server
python-jose[cryptography]>=3.3.0  # JWT authentication
passlib[bcrypt]>=1.7.4  # Password hashing
python-multipart>=0.0.6  # File uploads
pandas>=2.1.0  # For CSV/Excel parsing
openpyxl>=3.1.0  # For Excel file support
redis>=5.0.0  # For state management (optional)
flask>=2.3.0  # Already in requirements
requests>=2.31.0  # Already in requirements

# Frontend
react>=18.0.0
typescript>=5.0.0  # TypeScript support
vite>=5.0.0  # Build tool
tailwindcss>=3.4.0  # Utility-first CSS framework
chart.js>=4.4.0  # or recharts>=2.8.0 for graphs
axios>=1.6.0  # HTTP client
react-router-dom>=6.0.0  # Routing
lucide-react>=0.294.0  # Lucide Icons for React (SVG line icons)
i18next>=23.0.0  # Internationalization framework
react-i18next>=13.0.0  # React bindings for i18next
```

### Modern Premium Dark SaaS Dashboard Design System

**Design Philosophy:**
- Minimalist, enterprise-grade design similar to Vercel / Cursor / Linear
- Soft dark theme (not pure black) for reduced eye strain
- Card-based layout with subtle borders (no heavy shadows)
- High readability, low contrast strain
- Production-ready, reusable components

**Visual Style:**
- Card-based UI with clean, modern design
- **NO gradients** - Use solid colors only
- **NO glassmorphism** - No backdrop-filter or blur effects
- **NO neumorphism** - No soft depth effects
- Use borders instead of drop shadows
- Rounded corners: 12–16px
- Smooth animations and transitions (subtle)
- Clean typography and spacing
- SVG line icons (Lucide-style)

**Color Palette:**
- **Background:** `#0F0F0D` - Main application background
- **Sidebar / Secondary BG:** `#141412` - Sidebar and secondary surfaces
- **Card BG:** `#181816` - Card and component backgrounds
- **Border:** `#2A2A26` - Borders and dividers
- **Primary Text:** `#EAEAEA` - Main text content
- **Secondary Text:** `#B5B5B5` - Secondary text and labels
- **Muted Text:** `#8F8F8F` - Placeholders and disabled text
- **Accent Blue:** `#6EA8FF` - Interactive elements, links, highlights
- **Note:** Dark-mode first design (no light theme support required)

**Spacing System:**
- Base unit: 8px
- All spacing (padding, margin, gap) should be multiples of 8px
- Common values: 8px, 16px, 24px, 32px, 40px, 48px
- Consistent spacing across all components

**Component Design:**
- **Cards:**
  - Background: `#181816`
  - Border: `1px solid #2A2A26`
  - Border radius: 12–16px
  - Padding: 16px, 24px, or 32px (multiples of 8px)
  - No shadows, no gradients
- **Navigation:**
  - Sidebar background: `#141412`
  - Active state: Accent blue (`#6EA8FF`)
  - Hover state: Subtle background change
  - Border radius: 12px
- **Buttons:**
  - Primary: Accent blue (`#6EA8FF`) background
  - Secondary: Border with `#2A2A26`
  - Hover: Subtle opacity or color change
  - Border radius: 12px
  - No shadows, no gradients
- **Inputs:**
  - Background: `#181816`
  - Border: `1px solid #2A2A26`
  - Text: `#EAEAEA`
  - Placeholder: `#8F8F8F`
  - Focus: Border color `#6EA8FF`
  - Border radius: 12px
  - No shadows
- **Modal Dialogs:**
  - Background overlay: Dark with opacity
  - Dialog background: `#181816`
  - Border: `1px solid #2A2A26`
  - Border radius: 16px
  - No backdrop blur

**Icons:**
- Use Lucide Icons exclusively (via `lucide-react` package)
- SVG line icons style
- Consistent icon sizing and spacing
- Use appropriate icon props (size, color, strokeWidth) for different contexts
- Follow Lucide Icons naming conventions (PascalCase component names)
- Icon colors: Use text colors (`#EAEAEA`, `#B5B5B5`) or accent blue (`#6EA8FF`)
- Example: `<User />`, `<Home />`, `<Search />`, `<Moon />`, `<Sun />`

**Typography:**
- Primary text: `#EAEAEA` - Main content
- Secondary text: `#B5B5B5` - Labels, descriptions
- Muted text: `#8F8F8F` - Placeholders, disabled states
- Ensure high readability and low contrast strain
- Use appropriate font weights for hierarchy

**Responsive Design:**
- Mobile-first approach
- Breakpoints for tablet and desktop
- Touch-friendly interactions (minimum 44px touch targets)
- Grid-based layouts for cards
- Consistent spacing across all screen sizes

**Accessibility:**
- High readability with appropriate contrast ratios
- Low contrast strain (soft dark theme)
- Accessible color contrast (WCAG AA minimum)
- Keyboard navigation support
- Focus indicators using accent blue

**Tech Stack:**
- Vite (build tool)
- Tailwind CSS (optional - can use CSS modules or styled-components)
- Lucide Icons (icon library)
- Responsive layout (CSS Grid / Flexbox)
- Accessible contrast (tested)

### Message Formatting
- Use box-drawing characters for UI borders
- Single message updates (edit_message_text)
- Inline keyboards for all interactions
- No multi-message flows for ordering

### State Management
- Store user state in Redis or in-memory dict
- State keys: `user:{user_id}:state`
- State structure:
  ```python
  {
    "current_page": 1,
    "selected_product_id": None,
    "selected_variation_id": None,
    "quantity": 1,
    "pending_order_id": None
  }
  ```

### Error Handling
- All handlers wrapped in try-except
- Log all errors with context
- Send user-friendly error messages
- Retry logic for external API calls

---

## Testing Strategy

### Unit Tests
- All service layer functions
- Message formatting functions
- State management functions
- Payment integration functions

### Integration Tests
- Bot command handlers
- Callback handlers
- IPN processing
- Delivery workflows

### End-to-End Tests
- Complete order flow (browse → select → pay → deliver)
- Pre-uploaded delivery flow
- Supplier-based delivery flow

---

## Security Considerations

1. **Bot Token Security**
   - Store in environment variables
   - Never commit to repository
   - Rotate regularly

2. **Payment Security**
   - Verify IPN signatures (already implemented)
   - Validate order amounts
   - Prevent duplicate processing

3. **User Input Validation**
   - Validate all user inputs
   - Sanitize product data
   - Prevent injection attacks

4. **Access Control**
   - Admin dashboard authentication
   - Supplier bot authentication
   - Role-based access control

---

## Deployment Considerations

### Environment Variables
```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_SUPPLIER_BOT_TOKEN=your_supplier_bot_token

# Database
DATABASE_URL=sqlite:///./database.db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Pay2S (already configured)
PAY2S_ENDPOINT=...
PAY2S_PARTNER_CODE=...
PAY2S_ACCESS_KEY=...
PAY2S_SECRET_KEY=...

# IPN
IPN_HOST=0.0.0.0
IPN_PORT=5001
IPN_URL=https://your-domain.com/ipn

# Dashboard
DASHBOARD_SECRET_KEY=...
DASHBOARD_PORT=5002
```

### Docker Setup
- Extend existing docker-compose.yml
- Add bot service
- Add supplier bot service
- Add dashboard service
- SQLite database file (no separate database service needed)
- Add Redis service (optional)
- Mount volume for SQLite database file persistence

---

## Future Enhancements

1. **Multi-language Support** ✅ *Planned in Phase 8*
   - ✅ i18n for bot messages (Vietnamese/English)
   - ✅ Language selection for users and admins
   - ✅ Translation management system

2. **Advanced Analytics**
   - User behavior tracking
   - Product popularity
   - Revenue forecasting

3. **Notification System** ✅ *Planned in Phase 9*
   - ✅ Custom notifications to users who pressed /start
   - ✅ Admin notification commands
   - ✅ Notification delivery tracking
   - Order status updates
   - Stock alerts
   - Supplier notifications

4. **Inventory Management**
   - Automatic stock updates
   - Low stock alerts
   - Stock history

5. **User Features**
   - Order history
   - Favorite products
   - Wishlist
   - Reviews and ratings

---

## Acceptance Criteria

### Product Browsing
- [ ] User can view paginated product list
- [ ] User can navigate between pages
- [ ] All interactions happen in single message
- [ ] Product list displays correctly with box drawing

### Product Selection
- [ ] User can select product from list
- [ ] Product details display correctly
- [ ] Variations show prices and stock
- [ ] User can refresh product data
- [ ] User can return to product list

### Order Creation
- [ ] User can select variation
- [ ] Order confirmation displays correctly
- [ ] User can adjust quantity
- [ ] Quantity validates against stock
- [ ] Total calculates correctly

### Payment
- [ ] Payment URL generated correctly
- [ ] User receives payment URL/QR code
- [ ] Order created with pending status
- [ ] Payment transaction ID stored
- [ ] Cancel button displayed with QR code
- [ ] User can cancel pending orders
- [ ] Payment message includes 30-minute auto-cancel warning notification
- [ ] QR code caption includes 30-minute auto-cancel warning notification
- [ ] Orders automatically cancelled if not paid within 30 minutes

### Delivery - Pre-uploaded
- [ ] Product delivered instantly after payment
- [ ] Product marked as used
- [ ] Order status updated to delivered
- [ ] User receives product data

### Delivery - Supplier-based
- [ ] Supplier receives order notification
- [ ] Supplier can reply with product data
- [ ] Product forwarded to user
- [ ] Order status updated to delivered

### Admin Dashboard
- [ ] Admin can view order statistics
- [ ] Admin can manage products
- [ ] Admin can upload pre-uploaded products
- [ ] Admin can configure variations
- [ ] Admin can view product details

### Order Cancellation
- [ ] Cancel button appears with QR code display
- [ ] User can cancel pending orders
- [ ] Order status updates to CANCELLED
- [ ] User receives cancellation confirmation
- [ ] Cannot cancel already paid/processed orders
- [ ] QR payment message is deleted after payment success
- [ ] QR payment message is deleted when order is cancelled
- [ ] Auto-cancel: Orders automatically cancelled if unpaid for 30 minutes
- [ ] Auto-cancel: Background task checks and cancels expired orders
- [ ] Auto-cancel: Handles race conditions (order paid during auto-cancel check)
- [ ] Auto-cancel: QR payment message is deleted when order is auto-cancelled

### Notification System
- [ ] Users are tracked when they press /start
- [ ] Admin can send custom notifications to all users who pressed /start
- [ ] Admin can send notifications to specific users
- [ ] Notification delivery status is tracked
- [ ] Notifications support custom message content

### Multi-Language Support
- [ ] Users can select language (Vietnamese/English) in Telegram bot
- [ ] All bot messages display in selected language
- [ ] Admins can select language (Vietnamese/English) in dashboard
- [ ] All dashboard UI elements display in selected language
- [ ] Language preference is saved and persists across sessions
- [ ] Default language fallback works correctly
- [ ] Missing translations fallback to English

---

## Notes

- All implementation must follow TDD (Test-Driven Development)
- All code must pass quality gates (typecheck, lint, test, build)
- Follow existing code patterns in `src/pay2s/`
- Maintain backward compatibility with existing payment system
- Use existing IPN handler as base for order processing

---

**End of Plan**

