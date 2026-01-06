# MTK Bot Order - Admin Dashboard Frontend

Glassmorphism UI framework for the admin dashboard.

## Features

- ✅ React 18 with TypeScript
- ✅ **Dark Mode UI with Soft Neumorphism/Glassmorphism**
  - Dark background (#1a1b2e) with high-contrast cards (#1e2746, #252b4a)
  - Purple/blue accent colors (#8b5cf6, #a78bfa)
  - Soft depth with gradients and subtle shadows (not full glass blur)
  - Clean spacing, rounded cards (12px border-radius)
- ✅ Lucide Icons integration (no emojis)
- ✅ Dark/Light theme support (default: dark)
- ✅ Responsive layout
- ✅ JWT authentication
- ✅ React Router for navigation
- ✅ Comprehensive test coverage (33 tests)

## Setup

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Run tests
npm test

# Build for production
npm run build
```

## Project Structure

```
frontend/
├── src/
│   ├── components/      # Reusable UI components (Card, Button, Input)
│   ├── contexts/       # React contexts (Theme, Auth)
│   ├── layouts/        # Layout components
│   ├── pages/          # Page components
│   ├── styles/         # Theme and styling utilities
│   ├── test/           # Test files
│   └── App.tsx         # Main app component
├── package.json
└── vite.config.ts
```

## Components

### Card
Modern card component with clean design and subtle shadows.

### Button
Modern button with variants (primary, secondary, outline) and sizes. Supports Lucide icons.

### Input
Modern input with label and error handling.

## Icons

This project uses **Lucide Icons** for all iconography. Icons are imported from `lucide-react`:

```tsx
import { Moon, Sun, BarChart3, Package, ShoppingCart } from 'lucide-react'

<Moon size={18} />
<Sun size={18} />
```

Common icons used:
- Navigation: `BarChart3`, `Package`, `ShoppingCart`
- Theme: `Moon`, `Sun`
- Actions: `LogOut`, `Search`, `Edit`, `Trash2`, `Plus`

## Theme System

The theme system uses **Dark Mode UI with Soft Neumorphism/Glassmorphism**:
- **Dark Background**: Deep blue/purple (#1a1b2e) with secondary background (#16213e)
- **High-Contrast Cards**: Surface colors (#1e2746, #252b4a) that stand out from background
- **Accent Colors**: Purple/blue gradient (#8b5cf6, #a78bfa)
- **Soft Neumorphism**: Subtle gradients and shadows (not full glass blur)
- **Clean Spacing**: Modern minimal design with 12px rounded corners
- **Smooth Transitions**: All color and style changes are animated

## Environment Variables

Create a `.env` file:

```
VITE_API_BASE_URL=http://localhost:8001
```

## Testing

All components are tested using Vitest and React Testing Library:

```bash
npm test              # Run tests
npm test -- --ui      # Run tests with UI
npm test -- --coverage # Run tests with coverage
```

## Next Steps

- Task 7.4: Order Statistics Dashboard
- Task 7.5: Product Management UI
- Task 7.11: Order Management UI

