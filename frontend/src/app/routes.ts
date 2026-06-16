export interface RouteDefinition {
  path: string
  key: string
  labelKey: string
  group?: 'overview' | 'catalog' | 'operations' | 'settings'
  iconName: string
  roles?: string[]
  enabled?: boolean
}

export const ROUTES: RouteDefinition[] = [
  // Overview
  { path: '/statistics', key: 'statistics', labelKey: 'nav.statistics', group: 'overview', iconName: 'BarChart2' },
  // Catalog
  { path: '/products', key: 'products', labelKey: 'nav.products', group: 'catalog', iconName: 'Package' },
  { path: '/variations', key: 'variations', labelKey: 'nav.variations', group: 'catalog', iconName: 'Layers' },
  { path: '/manuals', key: 'manuals', labelKey: 'nav.manuals', group: 'catalog', iconName: 'BookOpen' },
  // Operations
  { path: '/orders', key: 'orders', labelKey: 'nav.orders', group: 'operations', iconName: 'ShoppingCart' },
  { path: '/notifications', key: 'notifications', labelKey: 'nav.notifications', group: 'operations', iconName: 'Bell' },
  { path: '/product-upload', key: 'productUpload', labelKey: 'nav.productUpload', group: 'operations', iconName: 'Upload' },
  { path: '/pre-uploaded', key: 'preUploaded', labelKey: 'nav.preUploaded', group: 'operations', iconName: 'Database' },
  { path: '/inventory-update', key: 'inventoryUpdate', labelKey: 'nav.inventoryUpdate', group: 'operations', iconName: 'Boxes' },
  { path: '/bonus-summary', key: 'bonusSummary', labelKey: 'nav.bonusSummary', group: 'operations', iconName: 'Gift' },
  // Operations (continued)
  { path: '/balances', key: 'balances', labelKey: 'nav.balances', group: 'operations', iconName: 'Wallet' },
  { path: '/suppliers', key: 'suppliers', labelKey: 'nav.suppliers', group: 'operations', iconName: 'Users' },
  // Settings
  { path: '/bot-ui-settings', key: 'botUiSettings', labelKey: 'nav.botUiSettings', group: 'settings', iconName: 'Settings' },
  { path: '/general-settings', key: 'generalSettings', labelKey: 'nav.generalSettings', group: 'settings', iconName: 'Star' },
]

export const ROUTE_GROUPS: { key: NonNullable<RouteDefinition['group']>; labelKey: string }[] = [
  { key: 'overview', labelKey: 'nav.groups.overview' },
  { key: 'catalog', labelKey: 'nav.groups.catalog' },
  { key: 'operations', labelKey: 'nav.groups.operations' },
  { key: 'settings', labelKey: 'nav.groups.settings' },
]

export function routesByGroup(group: NonNullable<RouteDefinition['group']>): RouteDefinition[] {
  return ROUTES.filter(r => r.group === group)
}
