// Navigation data
export const navLinks = [
  { label: 'Product', href: '#product', hasDropdown: true },
  { label: 'Connectors', href: '#connectors' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Use cases', href: '#use-cases' },
  { label: 'Developers', href: '#developers', hasDropdown: true },
  { label: 'Pricing', href: '#pricing' },
];

export const productDropdown = [
  { label: 'Platform Overview', description: 'See the full commerce data layer', href: '#product' },
  { label: 'Connectors', description: 'Connect your commerce platforms', href: '#connectors' },
  { label: 'Data Resources', description: 'Unified commerce data schema', href: '#data-resources' },
];

export const developerDropdown = [
  { label: 'Documentation', description: 'Full API and SDK reference', href: '#docs' },
  { label: 'API Reference', description: 'Explore endpoints and responses', href: '#api' },
  { label: 'Status', description: 'System health and uptime', href: '#status' },
];

// Platform logos / connectors
export const platforms = [
  { name: 'Shopify', id: 'shopify' },
  { name: 'WooCommerce', id: 'woocommerce' },
  { name: 'Amazon', id: 'amazon' },
  { name: 'Adobe Commerce', id: 'adobe' },
  { name: 'Custom REST', id: 'custom-rest' },
  { name: 'GraphQL APIs', id: 'graphql' },
];

// How it works steps
export const howItWorksSteps = [
  {
    number: '01',
    title: 'Connect',
    description: 'Choose a commerce platform and securely authenticate one or multiple stores using its supported access method.',
    tags: ['Shopify', 'WooCommerce', 'Amazon', 'Adobe Commerce', 'Custom API'],
  },
  {
    number: '02',
    title: 'Discover',
    description: 'Automatically identify available commerce resources and the API capabilities supported by each connected store.',
    tags: ['Orders', 'Products', 'Customers', 'Inventory', 'Payments'],
  },
  {
    number: '03',
    title: 'Extract',
    description: 'Bring orders, products, customers, inventory, payments, refunds and fulfillments into the unified data layer.',
    tags: ['Incremental sync', 'Full refresh', 'Real-time events'],
  },
  {
    number: '04',
    title: 'Use',
    description: 'Feed trusted commerce data into analytics, dashboards, warehouses, AI systems and automated workflows.',
    tags: ['Warehouse', 'BI', 'AI', 'Automation', 'Reporting'],
  },
];

// Multi-store connections mock data
export const storeConnections = [
  {
    id: 1,
    name: 'North America Store',
    url: 'na-store.myshopify.com',
    platform: 'Shopify',
    status: 'Healthy',
    statusColor: 'success',
    lastSync: '2 min ago',
  },
  {
    id: 2,
    name: 'Marketplace US',
    url: 'Seller ID: A2E3Q1BT5CB82',
    platform: 'Amazon',
    status: 'Healthy',
    statusColor: 'success',
    lastSync: '5 min ago',
  },
  {
    id: 3,
    name: 'Wholesale Store',
    url: 'wholesale.brand.com',
    platform: 'WooCommerce',
    status: 'Syncing',
    statusColor: 'warning',
    lastSync: 'now',
  },
];

export const storeStats = [
  { value: '3', label: 'Active connections' },
  { value: '16', label: 'Resources synced' },
  { value: '304k', label: 'Records available' },
];

// Data schema resources
export const schemaResources = [
  { id: 'orders', label: 'Orders' },
  { id: 'products', label: 'Products' },
  { id: 'customers', label: 'Customers' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'payments', label: 'Payments' },
  { id: 'refunds', label: 'Refunds' },
  { id: 'fulfillments', label: 'Fulfillments' },
];

export const schemaFields = {
  orders: {
    title: 'Orders',
    subtitle: 'Commerce event',
    totalFields: 10,
    fields: [
      { name: 'order_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'store_id', type: 'string', notes: '—' },
      { name: 'customer_id', type: 'string', notes: '—' },
      { name: 'currency', type: 'string (ISO 4217)', notes: '—' },
      { name: 'total_amount', type: 'decimal', notes: '—' },
      { name: 'line_items', type: 'array<LineItem>', notes: '—' },
      { name: 'status', type: 'enum', notes: '—' },
      { name: 'fulfillment_status', type: 'enum', notes: '—' },
    ],
  },
  products: {
    title: 'Products',
    subtitle: 'Catalog item',
    totalFields: 12,
    fields: [
      { name: 'product_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'store_id', type: 'string', notes: '—' },
      { name: 'title', type: 'string', notes: '—' },
      { name: 'description', type: 'string', notes: 'HTML or plain text' },
      { name: 'vendor', type: 'string', notes: '—' },
      { name: 'price', type: 'decimal', notes: '—' },
      { name: 'variants', type: 'array<Variant>', notes: '—' },
      { name: 'status', type: 'enum', notes: 'active | archived | draft' },
    ],
  },
  customers: {
    title: 'Customers',
    subtitle: 'Identity record',
    totalFields: 9,
    fields: [
      { name: 'customer_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'store_id', type: 'string', notes: '—' },
      { name: 'email', type: 'string', notes: 'Normalized lowercase' },
      { name: 'first_name', type: 'string', notes: '—' },
      { name: 'last_name', type: 'string', notes: '—' },
      { name: 'phone', type: 'string', notes: 'E.164 format' },
      { name: 'orders_count', type: 'integer', notes: '—' },
      { name: 'total_spent', type: 'decimal', notes: '—' },
    ],
  },
  inventory: {
    title: 'Inventory',
    subtitle: 'Stock level',
    totalFields: 7,
    fields: [
      { name: 'inventory_item_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'variant_id', type: 'string', notes: '—' },
      { name: 'location_id', type: 'string', notes: '—' },
      { name: 'available', type: 'integer', notes: 'On-hand minus reserved' },
      { name: 'reserved', type: 'integer', notes: '—' },
      { name: 'incoming', type: 'integer', notes: '—' },
      { name: 'updated_at', type: 'timestamp', notes: 'ISO 8601' },
    ],
  },
  payments: {
    title: 'Payments',
    subtitle: 'Financial transaction',
    totalFields: 8,
    fields: [
      { name: 'payment_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'order_id', type: 'string', notes: '—' },
      { name: 'amount', type: 'decimal', notes: '—' },
      { name: 'currency', type: 'string (ISO 4217)', notes: '—' },
      { name: 'gateway', type: 'string', notes: '—' },
      { name: 'status', type: 'enum', notes: 'pending | paid | failed | refunded' },
      { name: 'created_at', type: 'timestamp', notes: 'ISO 8601' },
    ],
  },
  refunds: {
    title: 'Refunds',
    subtitle: 'Return transaction',
    totalFields: 6,
    fields: [
      { name: 'refund_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'order_id', type: 'string', notes: '—' },
      { name: 'amount', type: 'decimal', notes: '—' },
      { name: 'reason', type: 'string', notes: '—' },
      { name: 'line_items', type: 'array<RefundLineItem>', notes: '—' },
      { name: 'created_at', type: 'timestamp', notes: 'ISO 8601' },
    ],
  },
  fulfillments: {
    title: 'Fulfillments',
    subtitle: 'Shipment record',
    totalFields: 8,
    fields: [
      { name: 'fulfillment_id', type: 'string', notes: 'Platform-native identifier' },
      { name: 'order_id', type: 'string', notes: '—' },
      { name: 'tracking_number', type: 'string', notes: '—' },
      { name: 'carrier', type: 'string', notes: '—' },
      { name: 'status', type: 'enum', notes: 'pending | shipped | delivered' },
      { name: 'line_items', type: 'array<FulfillmentLineItem>', notes: '—' },
      { name: 'shipped_at', type: 'timestamp', notes: 'ISO 8601' },
    ],
  },
};

// Build on top / use cases
export const buildOnTopItems = [
  {
    id: 'analytics',
    title: 'Analytics & BI',
    tags: ['Reporting', 'Dashboards', 'KPIs'],
    description: 'Power dashboards and reporting from consistent commerce data. Connect to Looker, Metabase, Tableau, or any BI tool your team already uses.',
  },
  {
    id: 'warehouses',
    title: 'Data Warehouses',
    tags: ['BigQuery', 'Snowflake', 'Redshift'],
    description: 'Deliver structured commerce datasets directly to your analytics stack. BigQuery, Snowflake, Redshift, and others receive normalized, ready-to-query data.',
  },
  {
    id: 'ai',
    title: 'AI Applications',
    tags: ['LLMs', 'Embeddings', 'RAG pipelines'],
    description: 'Give AI systems trusted business context instead of fragmented source data. Build on structured commerce entities rather than raw API responses.',
  },
  {
    id: 'automation',
    title: 'Automation',
    tags: ['Event-driven', 'Webhooks', 'Workflows'],
    description: 'Trigger workflows using normalized events and commerce activity. Fulfillment updates, inventory thresholds, customer actions — all from one reliable source.',
  },
];

// FAQ items
export const faqItems = [
  {
    id: 1,
    question: 'Can I connect more than one store?',
    answer: 'Yes. NexusCommerce is designed for multi-store from the ground up. You can connect as many stores as needed — across the same platform or different platforms — and all data flows into a single unified view.',
  },
  {
    id: 2,
    question: 'What kind of commerce data can be extracted?',
    answer: 'We support Orders, Products, Customers, Inventory, Payments, Refunds, and Fulfillments. Each resource is normalized into a consistent schema regardless of which platform it originates from.',
  },
  {
    id: 3,
    question: 'Do I need a separate integration for every store?',
    answer: 'No. One connection per store authenticates with the platform and the system automatically discovers available resources. Adding a new store of the same platform type takes minutes.',
  },
  {
    id: 4,
    question: 'Can the data be used outside the platform?',
    answer: 'Absolutely. You can push data to any warehouse, BI tool, AI system, or automation workflow. We provide APIs, webhooks, and native connectors to popular destinations.',
  },
  {
    id: 5,
    question: 'How is store access handled?',
    answer: 'Access credentials are encrypted at rest and in transit. We use OAuth where available and follow the principle of least privilege — requesting only the permissions necessary for data access.',
  },
];

// Footer links
export const footerLinks = [
  {
    category: 'Product',
    links: [
      { label: 'Connectors', href: '#connectors' },
      { label: 'Platform', href: '#product' },
      { label: 'Data resources', href: '#data-resources' },
      { label: 'Pricing', href: '#pricing' },
    ],
  },
  {
    category: 'Developers',
    links: [
      { label: 'Documentation', href: '#docs' },
      { label: 'API reference', href: '#api' },
      { label: 'Status', href: '#status' },
    ],
  },
  {
    category: 'Company',
    links: [
      { label: 'About', href: '#about' },
      { label: 'Contact', href: '#contact' },
      { label: 'Security', href: '#security' },
    ],
  },
  {
    category: 'Legal',
    links: [
      { label: 'Terms of Service', href: '/terms' },
      { label: 'Privacy Policy', href: '/privacy' },
      { label: 'Data Processing Agreement', href: '/dpa' },
      { label: 'Cookie Policy', href: '/cookies' },
      { label: 'Data Retention & Deletion', href: '/data-retention' },
    ],
  },
];
