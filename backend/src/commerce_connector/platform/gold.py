from __future__ import annotations

from commerce_connector.platform.db import PostgresGateway


class GoldRefresher:
    """Idempotent Gold refresh built from standardized Silver tables."""

    def __init__(self, db: PostgresGateway):
        self.db = db

    def refresh_tenant(self, tenant_id: str) -> None:
        with self.db.connection() as conn, conn.cursor() as cur:
            # Rebuild only this tenant's marts. This is deliberately simple and
            # deterministic for the current backend; production can move to
            # incremental/dbt models later without changing upstream contracts.
            for table in (
                "gold.daily_sales",
                "gold.product_daily",
                "gold.customer_metrics",
                "gold.inventory_snapshot_daily",
                "gold.refund_daily",
                "gold.fulfillment_daily",
                "gold.channel_daily",
            ):
                cur.execute(f"delete from {table} where tenant_id=%s", (tenant_id,))

            cur.execute(
                """
                insert into gold.daily_sales(
                  tenant_id,connection_id,metric_date,currency_code,orders_count,units_sold,
                  gross_sales,discounts,shipping,tax,refunds,net_sales,average_order_value,
                  new_customers,returning_customers
                )
                select
                  o.tenant_id,o.connection_id,coalesce(o.processed_at,o.source_created_at)::date,
                  coalesce(o.currency_code,'UNKNOWN'),count(*)::bigint,
                  coalesce(sum(li.units),0),coalesce(sum(o.gross_amount),0),
                  coalesce(sum(o.discount_amount),0),coalesce(sum(o.shipping_amount),0),
                  coalesce(sum(o.tax_amount),0),coalesce(sum(o.refunded_amount),0),
                  coalesce(sum(o.net_amount),0),
                  case when count(*)=0 then null else sum(o.net_amount)/count(*) end,
                  0,0
                from silver.orders o
                left join (
                  select order_id,sum(quantity) as units from silver.order_items group by order_id
                ) li on li.order_id=o.id
                where o.tenant_id=%s and coalesce(o.processed_at,o.source_created_at) is not null
                group by o.tenant_id,o.connection_id,coalesce(o.processed_at,o.source_created_at)::date,
                         coalesce(o.currency_code,'UNKNOWN')
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                insert into gold.product_daily(
                  tenant_id,connection_id,metric_date,product_id,variant_id,currency_code,
                  orders_count,units_sold,gross_sales,discounts,refunds,net_sales
                )
                select
                  oi.tenant_id,oi.connection_id,coalesce(o.processed_at,o.source_created_at)::date,
                  oi.product_id,oi.variant_id,coalesce(oi.currency_code,o.currency_code,'UNKNOWN'),
                  count(distinct oi.order_id),sum(oi.quantity),sum(oi.gross_amount),
                  sum(oi.discount_amount),0,sum(oi.net_amount)
                from silver.order_items oi
                join silver.orders o on o.id=oi.order_id
                where oi.tenant_id=%s and oi.product_id is not null
                  and coalesce(o.processed_at,o.source_created_at) is not null
                group by oi.tenant_id,oi.connection_id,coalesce(o.processed_at,o.source_created_at)::date,
                         oi.product_id,oi.variant_id,coalesce(oi.currency_code,o.currency_code,'UNKNOWN')
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                insert into gold.customer_metrics(
                  tenant_id,connection_id,customer_id,currency_code,first_order_at,last_order_at,
                  orders_count,gross_sales,refunds,net_sales,average_order_value,lifetime_value,
                  days_since_last_order
                )
                select
                  o.tenant_id,o.connection_id,o.customer_id,min(o.currency_code),
                  min(coalesce(o.processed_at,o.source_created_at)),
                  max(coalesce(o.processed_at,o.source_created_at)),count(*)::bigint,
                  sum(o.gross_amount),sum(o.refunded_amount),sum(o.net_amount),
                  case when count(*)=0 then null else sum(o.net_amount)/count(*) end,
                  sum(o.net_amount),
                  (current_date-max(coalesce(o.processed_at,o.source_created_at))::date)
                from silver.orders o
                where o.tenant_id=%s and o.customer_id is not null
                group by o.tenant_id,o.connection_id,o.customer_id
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                insert into gold.inventory_snapshot_daily(
                  tenant_id,connection_id,snapshot_date,location_id,product_id,variant_id,
                  available,on_hand,committed,incoming,inventory_value,currency_code
                )
                select tenant_id,connection_id,current_date,location_id,product_id,variant_id,
                       available,on_hand,committed,incoming,
                       coalesce(on_hand,available,0)*coalesce(unit_cost,0),currency_code
                from silver.inventory_levels where tenant_id=%s
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                insert into gold.refund_daily(
                  tenant_id,connection_id,metric_date,currency_code,refund_count,refunded_orders,
                  refund_amount,refund_rate
                )
                select r.tenant_id,r.connection_id,r.source_created_at::date,
                       coalesce(r.currency_code,'UNKNOWN'),count(*)::bigint,
                       count(distinct r.order_id)::bigint,sum(r.amount),null
                from silver.refunds r
                where r.tenant_id=%s and r.source_created_at is not null
                group by r.tenant_id,r.connection_id,r.source_created_at::date,
                         coalesce(r.currency_code,'UNKNOWN')
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                insert into gold.fulfillment_daily(
                  tenant_id,connection_id,metric_date,fulfillments_count,delivered_count,
                  cancelled_count,avg_hours_to_ship,avg_hours_to_deliver,on_time_delivery_rate
                )
                select f.tenant_id,f.connection_id,coalesce(f.shipped_at,f.source_created_at)::date,
                       count(*)::bigint,
                       count(*) filter (where lower(coalesce(f.status,'')) in ('delivered','success'))::bigint,
                       count(*) filter (where lower(coalesce(f.status,'')) in ('cancelled','canceled'))::bigint,
                       avg(extract(epoch from (f.shipped_at-o.source_created_at))/3600.0),
                       avg(extract(epoch from (f.delivered_at-f.shipped_at))/3600.0),null
                from silver.fulfillments f
                left join silver.orders o on o.id=f.order_id
                where f.tenant_id=%s and coalesce(f.shipped_at,f.source_created_at) is not null
                group by f.tenant_id,f.connection_id,coalesce(f.shipped_at,f.source_created_at)::date
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                insert into gold.channel_daily(
                  tenant_id,platform_id,metric_date,currency_code,active_connections,orders_count,
                  units_sold,gross_sales,refunds,net_sales,average_order_value
                )
                select d.tenant_id,c.platform_id,d.metric_date,d.currency_code,
                       count(distinct d.connection_id)::bigint,sum(d.orders_count),sum(d.units_sold),
                       sum(d.gross_sales),sum(d.refunds),sum(d.net_sales),
                       case when sum(d.orders_count)=0 then null else sum(d.net_sales)/sum(d.orders_count) end
                from gold.daily_sales d
                join control.connections c on c.id=d.connection_id
                where d.tenant_id=%s
                group by d.tenant_id,c.platform_id,d.metric_date,d.currency_code
                """,
                (tenant_id,),
            )
