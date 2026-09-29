from commerce_connector.platform.sql_guard import SQLGuard


def test_sql_guard_accepts_tenant_scoped_select():
    result = SQLGuard().validate(
        "select metric_date, net_sales from gold.daily_sales where tenant_id = :tenant_id"
    )
    assert result.ok is True
    assert "%(tenant_id)s" in result.sql
    assert "LIMIT" in result.sql


def test_sql_guard_blocks_mutation():
    result = SQLGuard().validate(
        "delete from silver.orders where tenant_id = :tenant_id"
    )
    assert result.ok is False


def test_sql_guard_requires_tenant_filter():
    result = SQLGuard().validate("select * from gold.daily_sales")
    assert result.ok is False


def test_sql_guard_requires_tenant_filter_on_each_analytics_table():
    result = SQLGuard().validate(
        "select o.id, p.net_sales "
        "from silver.orders o "
        "join gold.product_daily p on p.product_id = o.id "
        "where o.tenant_id = :tenant_id"
    )
    assert result.ok is False
    assert "Tenant filter missing for gold.product_daily" in (result.reason or "")


def test_sql_guard_accepts_alias_scoped_tenant_filters():
    result = SQLGuard().validate(
        "select o.id, p.net_sales "
        "from silver.orders o "
        "join gold.product_daily p on p.product_id = o.id "
        "where o.tenant_id = :tenant_id and p.tenant_id = :tenant_id"
    )
    assert result.ok is True
