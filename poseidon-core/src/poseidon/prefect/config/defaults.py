"""Static manifest fallbacks for Prefect reporting flows."""

from __future__ import annotations

SALES_MV_CONFIG = [
    {
        "name": "res_partner_location_mv",
        "create_sql": "sql/create_res_partner_location_mv.sql",
        "refresh_sql": "cda_it_custom.res_partner_location_mv",
    },
    {
        "name": "sale_order_invoiced_mv",
        "create_sql": "sql/create_sale_order_invoiced_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_invoiced_mv",
    },
    {
        "name": "sale_order_uninvoiced_mv",
        "create_sql": "sql/create_sale_order_uninvoiced_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_uninvoiced_mv",
    },
    {
        "name": "sale_order_line_invoiced_amounts_mv",
        "create_sql": "sql/create_sale_order_line_invoiced_amounts_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_line_invoiced_amounts_mv",
    },
    {
        "name": "account_move_invoice_mv",
        "create_sql": "sql/create_account_move_invoice_mv.sql",
        "refresh_sql": "cda_it_custom.account_move_invoice_mv",
    },
    {
        "name": "account_move_line_amounts_mv",
        "create_sql": "sql/create_account_move_line_amounts_mv.sql",
        "refresh_sql": "cda_it_custom.account_move_line_amounts_mv",
    },
    {
        "name": "sale_order_line_uninvoiced_amounts_mv",
        "create_sql": "sql/create_sale_order_line_uninvoiced_amounts_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_line_uninvoiced_amounts_mv",
    },
    {
        "name": "account_move_line_unordered_invoice_mv",
        "create_sql": "sql/create_account_move_line_unordered_invoice_mv.sql",
        "refresh_sql": "cda_it_custom.account_move_line_unordered_invoice_mv",
    },
    {
        "name": "product_pricelist_item_last_price_mv",
        "create_sql": "sql/create_product_pricelist_item_last_price_mv.sql",
        "refresh_sql": "cda_it_custom.product_pricelist_item_last_price_mv",
    },
    {
        "name": "sale_order_history_mv",
        "create_sql": "sql/create_sale_order_history_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_history_mv",
    },
    {
        "name": "account_move_line_basetable_staging_mv",
        "create_sql": "sql/create_account_move_line_basetable_staging_mv.sql",
        "refresh_sql": "cda_it_custom.account_move_line_basetable_staging_mv",
    },
    {
        "name": "sale_order_line_basetable_staging_mv",
        "create_sql": "sql/create_sale_order_line_basetable_staging_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_line_basetable_staging_mv",
    },
    {
        "name": "fact_sales_mv",
        "create_sql": "sql/create_fact_sales_mv.sql",
        "refresh_sql": "cda_it_custom.fact_sales_mv",
    },
    {
        "name": "sale_order_line_basetable_union_history_mv",
        "create_sql": "sql/create_sale_order_line_basetable_union_history_mv.sql",
        "refresh_sql": "cda_it_custom.sale_order_line_basetable_union_history_mv",
    },
]


ACCOUNTING_MV_CONFIG = [
    {
        "name": "account_analytic_line_plan_long_mv",
        "create_sql": "sql/create_account_analytic_line_plan_long_mv.sql",
        "refresh_sql": "cda_it_custom.account_analytic_line_plan_long_mv",
    },
    {
        "name": "fact_accounting_budget_mv",
        "create_sql": "sql/create_fact_accounting_budget_mv.sql",
        "refresh_sql": "cda_it_custom.fact_accounting_budget_mv",
    },
    {
        "name": "fact_accounting_journal_mv",
        "create_sql": "sql/create_fact_accounting_journal_mv.sql",
        "refresh_sql": "cda_it_custom.fact_accounting_journal_mv",
    },
]


PRODUCTION_MV_CONFIG = [
    {
        "name": "fact_workorder_mv",
        "create_sql": "sql/create_fact_workorder_mv.sql",
        "refresh_sql": "cda_it_custom.fact_workorder_mv",
    },
    {
        "name": "production_target_mv",
        "create_sql": "sql/create_production_target_mv.sql",
        "refresh_sql": "cda_it_custom.production_target_mv",
    },
    {
        "name": "rework_consumption_mv",
        "create_sql": "sql/create_rework_consumption_mv.sql",
        "refresh_sql": "cda_it_custom.rework_consumption_mv",
    },
    {
        "name": "fact_production_component_mv",
        "create_sql": "sql/create_fact_production_component_mv.sql",
        "refresh_sql": "cda_it_custom.fact_production_component_mv",
    },
    {
        "name": "fact_production_mv",
        "create_sql": "sql/create_fact_production_mv.sql",
        "refresh_sql": "cda_it_custom.fact_production_mv",
    },
    {
        "name": "fact_scrap_mv",
        "create_sql": "sql/create_fact_scrap_mv.sql",
        "refresh_sql": "cda_it_custom.fact_scrap_mv",
    },
    {
        "name": "agg_production_item_daily_mv",
        "create_sql": "sql/create_agg_production_item_daily_mv.sql",
        "refresh_sql": "cda_it_custom.agg_production_item_daily_mv",
    },
    {
        "name": "agg_production_order_daily_mv",
        "create_sql": "sql/create_agg_production_order_daily_mv.sql",
        "refresh_sql": "cda_it_custom.agg_production_order_daily_mv",
    },
    {
        "name": "agg_production_order_component_daily_mv",
        "create_sql": "sql/create_agg_production_order_component_daily_mv.sql",
        "refresh_sql": "cda_it_custom.agg_production_order_component_daily_mv",
    },
]
