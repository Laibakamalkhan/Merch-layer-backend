# NexusCommerce

<p align="center">
  <strong>One connection layer for every commerce system.</strong><br>
  Connect stores, marketplaces, and commerce APIs into a unified, deterministic data foundation.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-19.2-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/Vite-8.3-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/Framer_Motion-13.4-black?style=flat-square&logo=framer&logoColor=white" alt="Framer Motion" />
  <img src="https://img.shields.io/badge/Lucide_Icons-1.47-F05032?style=flat-square" alt="Lucide Icons" />
  <img src="https://img.shields.io/badge/Oxlint-Linter-orange?style=flat-square" alt="Oxlint" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" />
</p>

---

## 🌟 Overview

**NexusCommerce** is an enterprise-grade commerce data orchestration and ingestion platform interface. It solves the fragmentation problem in modern e-commerce by establishing a single, standardized pipeline that connects multiple storefronts, marketplaces, and bespoke APIs into a single source of truth.

Whether handling multi-region Shopify setups, Amazon Seller marketplaces, WooCommerce instances, or custom GraphQL endpoints, NexusCommerce normalizes commerce entities into clean, ready-to-query schemas for analytics, warehouses, AI pipelines, and operational automation.

---

## 🚀 Key Features

- **⚡ Multi-Store & Multi-Platform Connectors**: Native support for Shopify, WooCommerce, Amazon Marketplace, Adobe Commerce (Magento), and Custom REST / GraphQL APIs.
- **🧬 Unified Commerce Schema**: Out-of-the-box normalized models for:
  - `Orders` (Line items, customer references, financial & fulfillment states)
  - `Products` (Variants, pricing, vendor attributes, multi-channel status)
  - `Customers` (Unified identities, total spend, normalized contact info)
  - `Inventory` (Multi-location on-hand, reserved, and incoming stock levels)
  - `Payments` (Multi-currency transactions, payment gateway references)
  - `Refunds` & `Fulfillments` (Item-level tracking and shipment statuses)
- **🔄 Ingestion & Sync Lifecycle**:
  1. **Connect**: Secure OAuth authentication and credential management.
  2. **Discover**: Automatic capability detection and resource schema introspection.
  3. **Extract**: Real-time webhook capture, incremental syncs, and full refreshes.
  4. **Use**: Push cleaned datasets to data warehouses, BI tools, and AI workflows.
- **📊 Downstream Integration Ecosystem**:
  - **Data Warehouses**: Snowflake, Google BigQuery, Amazon Redshift, PostgreSQL.
  - **Analytics & BI**: Looker, Metabase, Tableau, PowerBI.
  - **AI & Automation**: LLM embeddings, RAG business context, event-driven webhooks.
- **💎 Modern Interactive UI**:
  - Rich dark theme with glassmorphism and subtle micro-animations.
  - Interactive live Schema Inspector with real-time field viewers.
  - Multi-store connection health monitor and sync status widgets.
  - Fully responsive, accessible, and SEO-optimized architecture.

---

## 🛠️ Tech Stack

- **Framework**: [React 19](https://react.dev/)
- **Bundler & Dev Server**: [Vite](https://vite.dev/)
- **Animation**: [Framer Motion](https://www.framer.com/motion/)
- **Iconography**: [Lucide React](https://lucide.dev/)
- **Styling**: Modern Vanilla CSS with design token architecture (CSS variables, responsive layouts, glassmorphism)
- **Linter**: [Oxlint](https://oxc.rs/)

---

## 📁 Project Structure

```text
Nexus Commerce/
├── public/                    # Static public assets & favicons
├── src/
│   ├── assets/                # Images, icons, and SVG illustrations
│   ├── components/
│   │   ├── layout/            # Global navigation & footer
│   │   │   ├── Navbar.jsx     # Header navigation with interactive dropdowns
│   │   │   ├── Navbar.css
│   │   │   ├── Footer.jsx     # Site footer with categorised link sections
│   │   │   └── Footer.css
│   │   ├── sections/          # Feature sections for the landing & app page
│   │   │   ├── HeroSection.jsx        # Hero banner with dynamic pipeline preview
│   │   │   ├── PlatformBar.jsx        # Supported platform connector highlights
│   │   │   ├── ProblemSolution.jsx    # Fragmentation vs. Nexus unified layer
│   │   │   ├── HowItWorks.jsx         # 4-step pipeline lifecycle breakdown
│   │   │   ├── MultiStoreSection.jsx  # Multi-store sync & live status dashboard
│   │   │   ├── DataSchemaSection.jsx  # Interactive unified schema explorer
│   │   │   ├── BuildOnTop.jsx         # Downstream warehouse/BI/AI use cases
│   │   │   ├── FAQSection.jsx         # Accordion FAQ
│   │   │   └── CTASection.jsx         # Call-to-action & developer onboarding
│   │   └── ui/                # Atomic reusable UI primitives
│   │       ├── Button.jsx     # Styled buttons (primary, secondary, outline)
│   │       ├── Card.jsx       # Glassmorphic card container
│   │       ├── Badge.jsx      # Status & tag pills
│   │       └── ...
│   ├── data/
│   │   └── siteData.js        # Schemas, mock connections, navigation data
│   ├── hooks/                 # Custom React hooks
│   ├── styles/
│   │   └── animations.css     # Keyframe animations & motion primitives
│   ├── App.jsx                # Application root composition
│   ├── index.css              # Global design tokens, typography, and reset
│   └── main.jsx               # React DOM root mounting
├── index.html                 # HTML entry point with metadata & Google Fonts
├── package.json               # Dependencies and npm scripts
└── vite.config.js             # Vite configuration
```

---

## 🚦 Getting Started

### Prerequisites

Ensure you have **Node.js** (version 18 or higher) and **npm** installed on your system.

```bash
node -v
npm -v
```

### Installation

1. **Clone or open the repository**:
   ```bash
   git clone <repository-url>
   cd "Nexus Commerce"
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

### Running the Development Server

Start the local development server with hot module replacement (HMR):

```bash
npm run dev
```

Open your browser and navigate to `http://localhost:5173` (or the port specified in terminal output).

---

## 📜 Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Starts Vite dev server with instant HMR |
| `npm run build` | Builds optimized production bundle in `/dist` |
| `npm run preview` | Locally preview the production build |
| `npm run lint` | Runs Oxlint for fast code analysis |

---

## 📊 Data Schema Reference

NexusCommerce standardizes heterogeneous payload structures across providers into canonical entities:

| Entity | Description | Sample Core Fields |
|---|---|---|
| **`Orders`** | Canonical commerce transactions | `order_id`, `store_id`, `currency`, `total_amount`, `line_items`, `status` |
| **`Products`** | Catalog item records & variants | `product_id`, `store_id`, `title`, `price`, `variants`, `status`, `vendor` |
| **`Customers`** | Normalized customer identity | `customer_id`, `store_id`, `email`, `first_name`, `orders_count`, `total_spent` |
| **`Inventory`** | Multi-location stock positions | `inventory_item_id`, `location_id`, `available`, `reserved`, `incoming` |
| **`Payments`** | Gateway transaction logs | `payment_id`, `order_id`, `amount`, `currency`, `gateway`, `status` |
| **`Refunds`** | Return adjustments & refunds | `refund_id`, `order_id`, `amount`, `reason`, `line_items` |
| **`Fulfillments`**| Shipment & tracking records | `fulfillment_id`, `order_id`, `tracking_number`, `carrier`, `status` |

---

## 🔒 Security & Best Practices

- **Zero Plaintext Storage**: API keys and webhook secrets encrypted at rest and in transit.
- **Granular Scopes**: Principle of least privilege applied across all store access tokens.
- **Idempotent Ingestion**: Event deduplication ensuring consistent downstream warehouse states.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
