import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Table as TableIcon, Database, RefreshCw, Search, Filter, 
  ChevronLeft, ChevronRight, Download, ExternalLink, Eye, 
  AlertCircle, CheckCircle2, ShoppingCart, Package, Users, 
  Layers, ArrowUpDown, X, FileJson, Copy, Check
} from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import { downloadCsv } from '../../lib/csv';

const ENTITY_CONFIG = {
  orders: {
    label: 'Orders',
    singular: 'Order',
    icon: ShoppingCart,
    description: 'Synced multi-channel order transactions, line items, and fulfillment statuses.',
    badgeColor: 'blue',
  },
  products: {
    label: 'Products',
    singular: 'Product',
    icon: Package,
    description: 'Unified product catalog, variants, pricing, inventory levels, and SKU mappings.',
    badgeColor: 'emerald',
  },
  customers: {
    label: 'Customers',
    singular: 'Customer',
    icon: Users,
    description: 'Customer profiles, order frequency, total spend, and contact addresses.',
    badgeColor: 'purple',
  },
};

export default function TableViewTab({ initialEntity = 'orders', activeStore = 'All stores', onOpenConnectors }) {
  const { tenantId } = useAuth();
  const [currentEntity, setCurrentEntity] = useState(initialEntity);
  const [sources, setSources] = useState([]);
  const [selectedSource, setSelectedSource] = useState('all');
  const [tableData, setTableData] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [error, setError] = useState(null);
  const [inspectRow, setInspectRow] = useState(null);
  const [copiedInspect, setCopiedInspect] = useState(false);

  // Sync initialEntity if changed from sidebar navigation
  useEffect(() => {
    if (initialEntity && ENTITY_CONFIG[initialEntity]) {
      setCurrentEntity(initialEntity);
      setPage(1);
    }
  }, [initialEntity]);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // 1. Fetch available data sources from GET /api/v1/tables/sources
  const fetchSources = useCallback(async () => {
    if (!tenantId) return;
    setSourcesLoading(true);
    try {
      const res = await api.tableSources(tenantId);
      // Handles either { sources: [...] } or array or { items: [...] }
      const sourceList = Array.isArray(res) 
        ? res 
        : (res?.sources || res?.items || res?.data || []);
      setSources(sourceList);
    } catch (err) {
      console.warn('Could not fetch table sources:', err.message);
      // Graceful fallback to avoid blocking the UI if sources endpoint is empty
      setSources([]);
    } finally {
      setSourcesLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // 2. Fetch paginated table data from GET /api/v1/tables/{entity}
  const fetchTableData = useCallback(async () => {
    if (!tenantId || !currentEntity) return;
    setIsLoading(true);
    setError(null);

    const queryParams = {
      tenant_id: tenantId,
      page,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    };

    if (selectedSource && selectedSource !== 'all') {
      queryParams.source = selectedSource;
      queryParams.connection_id = selectedSource;
    }

    if (debouncedSearch) {
      queryParams.search = debouncedSearch;
      queryParams.q = debouncedSearch;
    }

    try {
      const res = await api.tableData(currentEntity, queryParams);
      
      // Parse flexible paginated response structure
      let rows = [];
      let total = 0;

      if (Array.isArray(res)) {
        rows = res;
        total = res.length;
      } else if (res && typeof res === 'object') {
        rows = res.items || res.rows || res.data || res.records || [];
        total = res.total ?? res.count ?? res.total_count ?? rows.length;
      }

      setTableData(rows);
      setTotalCount(typeof total === 'number' ? total : rows.length);
    } catch (err) {
      console.error(`Error fetching table data for ${currentEntity}:`, err);
      setError(err.message || `Failed to load ${currentEntity} data. Please try again.`);
      setTableData([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  }, [tenantId, currentEntity, page, pageSize, selectedSource, debouncedSearch]);

  useEffect(() => {
    fetchTableData();
  }, [fetchTableData]);

  // Handle entity switch
  const handleSelectEntity = (entityKey) => {
    if (entityKey === currentEntity) return;
    setCurrentEntity(entityKey);
    setPage(1);
    setSearchQuery('');
    setInspectRow(null);
  };

  // Derive dynamic columns from returned records
  const dynamicColumns = useMemo(() => {
    if (!tableData || tableData.length === 0) return [];
    
    // Collect all unique keys across records
    const keySet = new Set();
    tableData.forEach((row) => {
      if (row && typeof row === 'object') {
        Object.keys(row).forEach((k) => keySet.add(k));
      }
    });

    const allKeys = Array.from(keySet);

    // Preferred sort order for primary columns
    const priority = [
      'id', 'order_number', 'order_id', 'code', 'sku', 'name', 'title', 
      'email', 'status', 'financial_status', 'fulfillment_status', 
      'total_amount', 'total_price', 'price', 'amount', 'currency', 
      'quantity', 'inventory_quantity', 'items_count', 'customer_name', 
      'source', 'platform', 'store_name', 'created_at', 'updated_at'
    ];

    allKeys.sort((a, b) => {
      const aIdx = priority.indexOf(a.toLowerCase());
      const bIdx = priority.indexOf(b.toLowerCase());
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;
      return a.localeCompare(b);
    });

    // Limit to max 9 main columns for crisp layout, user can inspect row for full details
    return allKeys.slice(0, 9);
  }, [tableData]);

  // Format cell value cleanly
  const formatCellValue = (val, key) => {
    if (val === null || val === undefined) {
      return <span className="cell-muted">—</span>;
    }
    if (typeof val === 'boolean') {
      return (
        <span className={`cell-badge ${val ? 'cell-badge--green' : 'cell-badge--gray'}`}>
          {val ? 'True' : 'False'}
        </span>
      );
    }
    if (typeof val === 'object') {
      if (Array.isArray(val)) {
        return <span className="cell-badge cell-badge--blue">{val.length} items</span>;
      }
      return <span className="cell-badge cell-badge--gray">{Object.keys(val).length} keys</span>;
    }

    const strVal = String(val);
    const lowerKey = key.toLowerCase();

    // Status styling
    if (lowerKey.includes('status')) {
      const s = strVal.toLowerCase();
      let badgeClass = 'cell-badge--gray';
      if (['paid', 'completed', 'active', 'fulfilled', 'delivered', 'healthy', 'success'].includes(s)) {
        badgeClass = 'cell-badge--green';
      } else if (['pending', 'processing', 'unfulfilled', 'in_transit'].includes(s)) {
        badgeClass = 'cell-badge--amber';
      } else if (['cancelled', 'refunded', 'failed', 'error', 'archived'].includes(s)) {
        badgeClass = 'cell-badge--red';
      }
      return <span className={`cell-badge ${badgeClass}`}>{strVal}</span>;
    }

    // Price / Amount formatting
    if (lowerKey.includes('price') || lowerKey.includes('amount') || lowerKey.includes('total')) {
      const num = Number(val);
      if (!isNaN(num)) {
        return <span className="cell-numeric font-mono">${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>;
      }
    }

    // Date formatting
    if (lowerKey.includes('_at') || lowerKey.includes('date')) {
      const date = new Date(val);
      if (!isNaN(date.getTime())) {
        return <span className="cell-date" title={date.toISOString()}>{date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>;
      }
    }

    // Truncate long strings
    if (strVal.length > 50) {
      return <span title={strVal}>{strVal.slice(0, 48)}…</span>;
    }

    return strVal;
  };

  // Export to CSV
  const handleExport = () => {
    if (!tableData || tableData.length === 0) return;
    downloadCsv(tableData, `${currentEntity}-export-${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const currentEntityConfig = ENTITY_CONFIG[currentEntity] || {
    label: currentEntity,
    singular: currentEntity,
    icon: Database,
    description: `Database records for ${currentEntity}`,
  };
  const CurrentIcon = currentEntityConfig.icon;

  const copyRowJson = () => {
    if (!inspectRow) return;
    navigator.clipboard.writeText(JSON.stringify(inspectRow, null, 2));
    setCopiedInspect(true);
    setTimeout(() => setCopiedInspect(false), 2000);
  };

  return (
    <div className="table-view-container">
      {/* Top Header Bar */}
      <div className="table-view-header">
        <div className="table-view-header__title-wrap">
          <div className="table-view-header__icon-box">
            <CurrentIcon size={20} className="text-blue-400" />
          </div>
          <div>
            <div className="table-view-header__title-row">
              <h1 className="table-view-header__title">{currentEntityConfig.label} Table</h1>
              <span className="table-view-header__count-badge">
                {isLoading ? '...' : `${totalCount.toLocaleString()} total records`}
              </span>
            </div>
            <p className="table-view-header__subtitle">
              {currentEntityConfig.description}
            </p>
          </div>
        </div>

        <div className="table-view-header__actions">
          <button 
            type="button"
            className="table-action-btn"
            onClick={fetchTableData}
            disabled={isLoading}
            title="Refresh database records"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          <button 
            type="button"
            className="table-action-btn"
            onClick={handleExport}
            disabled={tableData.length === 0}
            title="Export to CSV"
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Entity Selector Tabs Bar */}
      <div className="table-entity-tabs-bar">
        <div className="table-entity-tabs">
          {Object.entries(ENTITY_CONFIG).map(([key, config]) => {
            const Icon = config.icon;
            const isActive = currentEntity === key;
            return (
              <button
                key={key}
                type="button"
                className={`table-entity-tab ${isActive ? 'table-entity-tab--active' : ''}`}
                onClick={() => handleSelectEntity(key)}
              >
                <Icon size={16} />
                <span>{config.label}</span>
              </button>
            );
          })}
        </div>

        {/* Source and Search Filters */}
        <div className="table-filter-controls">
          {/* Data Source Selector */}
          <div className="table-source-select-wrap">
            <Filter size={14} className="filter-icon" />
            <select
              value={selectedSource}
              onChange={(e) => {
                setSelectedSource(e.target.value);
                setPage(1);
              }}
              className="table-source-select"
              disabled={sourcesLoading}
              title="Filter by connected source"
            >
              <option value="all">All Sources</option>
              {sources.map((src, i) => {
                const id = typeof src === 'string' ? src : (src.id || src.code || src.name);
                const name = typeof src === 'string' ? src : (src.name || src.platform_name || src.code || id);
                return (
                  <option key={id || i} value={id}>
                    {name}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Search Box */}
          <div className="table-search-box">
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder={`Search ${currentEntityConfig.label.toLowerCase()}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button 
                type="button" 
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                title="Clear search"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="table-view-body">
        {/* Loading State */}
        {isLoading && (
          <div className="table-skeleton-wrap">
            <div className="table-skeleton-header">
              <div className="skeleton-bar skeleton-bar--head" />
            </div>
            {[...Array(8)].map((_, i) => (
              <div key={i} className="table-skeleton-row">
                <div className="skeleton-bar" style={{ width: '18%' }} />
                <div className="skeleton-bar" style={{ width: '28%' }} />
                <div className="skeleton-bar" style={{ width: '15%' }} />
                <div className="skeleton-bar" style={{ width: '12%' }} />
                <div className="skeleton-bar" style={{ width: '15%' }} />
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <div className="table-error-state">
            <div className="table-error-icon">
              <AlertCircle size={32} />
            </div>
            <h3 className="table-error-title">Failed to load database records</h3>
            <p className="table-error-desc">{error}</p>
            <div className="table-error-actions">
              <button type="button" className="btn-table-primary" onClick={fetchTableData}>
                <RefreshCw size={14} /> Retry Query
              </button>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && tableData.length === 0 && (
          <div className="table-empty-state">
            <div className="table-empty-icon-wrap">
              <Database size={40} />
            </div>
            <h3 className="table-empty-title">No {currentEntityConfig.label} found</h3>
            <p className="table-empty-desc">
              {debouncedSearch 
                ? `No matching records found for "${debouncedSearch}". Try adjusting your search query.`
                : `Connect a commerce store or ingest CSV datasets to populate the ${currentEntityConfig.label.toLowerCase()} database.`}
            </p>
            <div className="table-empty-actions">
              {debouncedSearch ? (
                <button type="button" className="btn-table-secondary" onClick={() => setSearchQuery('')}>
                  Clear Search Filter
                </button>
              ) : (
                <button 
                  type="button" 
                  className="btn-table-primary"
                  onClick={onOpenConnectors}
                >
                  <ShoppingCart size={14} /> Manage Store Connections
                </button>
              )}
            </div>
          </div>
        )}

        {/* Data Table */}
        {!isLoading && !error && tableData.length > 0 && (
          <div className="table-grid-scroll-wrap">
            <table className="nexus-data-table">
              <thead>
                <tr>
                  <th className="th-index">#</th>
                  {dynamicColumns.map((colKey) => (
                    <th key={colKey} className="th-header-cell">
                      <div className="th-content">
                        <span>{colKey.replace(/_/g, ' ').toUpperCase()}</span>
                      </div>
                    </th>
                  ))}
                  <th className="th-action">Inspect</th>
                </tr>
              </thead>
              <tbody>
                {tableData.map((row, rowIdx) => {
                  const itemIndex = (page - 1) * pageSize + rowIdx + 1;
                  return (
                    <tr 
                      key={row.id || row._id || rowIdx}
                      className="table-row-item"
                      onClick={() => setInspectRow(row)}
                    >
                      <td className="td-index">{itemIndex}</td>
                      {dynamicColumns.map((colKey) => (
                        <td key={colKey} className="td-cell">
                          {formatCellValue(row[colKey], colKey)}
                        </td>
                      ))}
                      <td className="td-action" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          className="row-inspect-btn"
                          onClick={() => setInspectRow(row)}
                          title="View complete record JSON"
                        >
                          <Eye size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination Footer */}
      {!isLoading && !error && tableData.length > 0 && (
        <div className="table-pagination-footer">
          <div className="table-pagination-info">
            <span>
              Showing <strong>{(page - 1) * pageSize + 1}</strong> to{' '}
              <strong>{Math.min(page * pageSize, totalCount)}</strong> of{' '}
              <strong>{totalCount.toLocaleString()}</strong> results
            </span>
          </div>

          <div className="table-pagination-controls">
            <div className="page-size-selector">
              <span>Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>

            <div className="pagination-buttons">
              <button
                type="button"
                className="pagination-nav-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                title="Previous Page"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="pagination-page-indicator">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="pagination-nav-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                title="Next Page"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Slide-out Row Inspector Drawer */}
      {inspectRow && (
        <div className="row-inspector-backdrop" onClick={() => setInspectRow(null)}>
          <div className="row-inspector-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="row-inspector-header">
              <div className="row-inspector-title-wrap">
                <FileJson size={18} className="text-blue-400" />
                <div>
                  <h3 className="row-inspector-title">Record Details</h3>
                  <span className="row-inspector-subtitle">
                    {inspectRow.id || inspectRow._id || 'Raw Payload'}
                  </span>
                </div>
              </div>
              <div className="row-inspector-actions">
                <button
                  type="button"
                  className="inspector-action-btn"
                  onClick={copyRowJson}
                  title="Copy JSON to clipboard"
                >
                  {copiedInspect ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                  <span>{copiedInspect ? 'Copied' : 'Copy JSON'}</span>
                </button>
                <button
                  type="button"
                  className="inspector-close-btn"
                  onClick={() => setInspectRow(null)}
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="row-inspector-body">
              <div className="inspector-fields-grid">
                {Object.entries(inspectRow).map(([k, v]) => (
                  <div key={k} className="inspector-field-card">
                    <span className="inspector-field-key">{k}</span>
                    <span className="inspector-field-val">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}
                    </span>
                  </div>
                ))}
              </div>

              <div className="inspector-json-section">
                <span className="inspector-json-title">Raw JSON</span>
                <pre className="inspector-json-pre">
                  <code>{JSON.stringify(inspectRow, null, 2)}</code>
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
