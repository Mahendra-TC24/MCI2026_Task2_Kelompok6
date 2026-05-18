"""
DAG: Orders Pipeline Orchestration
Modul 2 & 3 - Pipeline Orchestration & Data Visualization
Dataset: http://96.9.212.102:8000/orders

Schema (dari data aktual):
  Orders  : order_id, user_id, order_number, order_dow, order_hour_of_day,
             days_since_prior_order, eval_set
  Products: product_id, product_name, aisle_id, aisle, department_id,
             department, add_to_cart_order, reordered
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import requests
import json
import logging


# Default Arguments
default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "start_date": days_ago(1),
}

# Konfigurasi
API_URL             = "http://96.9.212.102:8000/orders"
CLICKHOUSE_HOST     = "clickhouse"    # Ganti sesuai host ClickHouse kalian
CLICKHOUSE_PORT     = 8123
CLICKHOUSE_DB       = "ecommerce"
CLICKHOUSE_USER     = "default"
CLICKHOUSE_PASSWORD = "admin"            # Ganti jika pakai password

RAW_PATH        = "/tmp/orders_raw.json"
FLAT_ORDERS     = "/tmp/orders_flat.json"
FLAT_ITEMS      = "/tmp/order_items_flat.json"


# Task 1: EXTRACT
def extract_orders(**context):
    """Ambil data dari REST API endpoint /orders."""
    logging.info(f"Fetching: {API_URL}")
    resp = requests.get(API_URL, timeout=60)
    resp.raise_for_status()

    payload = resp.json()
    with open(RAW_PATH, "w") as f:
        json.dump(payload, f)

    orders = payload.get("orders", payload if isinstance(payload, list) else [])
    logging.info(f"Extracted {len(orders)} orders")
    context["ti"].xcom_push(key="raw_order_count", value=len(orders))
    return len(orders)


# Task 2: TRANSFORM
DOW_MAP = {
    0: "Sunday", 1: "Monday", 2: "Tuesday",
    3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday",
}

def transform_orders(**context):
    """Bersihkan & flatten data orders."""
    with open(RAW_PATH) as f:
        payload = json.load(f)

    raw_orders = payload.get("orders", payload if isinstance(payload, list) else [])

    flat_orders = []
    flat_items  = []

    for o in raw_orders:
        order_id = o["order_id"]
        products = o.get("products", [])

        #Tabel orders
        flat_orders.append({
            "order_id":               order_id,
            "user_id":                o.get("user_id"),
            "order_number":           o.get("order_number"),
            "order_dow":              o.get("order_dow"),           # 0=Sun … 6=Sat
            "order_dow_name":         DOW_MAP.get(o.get("order_dow"), "Unknown"),
            "order_hour_of_day":      o.get("order_hour_of_day"),
            "days_since_prior_order": o.get("days_since_prior_order"),  # float, nullable
            "eval_set":               o.get("eval_set", "prior"),
            "total_items":            len(products),
            "total_reordered":        sum(1 for p in products if p.get("reordered") == 1),
        })

        #Tabel order_items
        for p in products:
            flat_items.append({
                "order_id":          order_id,
                "user_id":           o.get("user_id"),
                "product_id":        p.get("product_id"),
                "product_name":      p.get("product_name", "").strip(),
                "aisle_id":          p.get("aisle_id"),
                "aisle":             p.get("aisle", "").strip(),
                "department_id":     p.get("department_id"),
                "department":        p.get("department", "").strip(),
                "add_to_cart_order": p.get("add_to_cart_order"),
                "reordered":         int(p.get("reordered", 0)),
            })

    with open(FLAT_ORDERS, "w") as f:
        json.dump(flat_orders, f)
    with open(FLAT_ITEMS, "w") as f:
        json.dump(flat_items, f)

    logging.info(f"Transform done: {len(flat_orders)} orders, {len(flat_items)} items")
    context["ti"].xcom_push(key="order_count",      value=len(flat_orders))
    context["ti"].xcom_push(key="order_item_count", value=len(flat_items))
    return len(flat_orders), len(flat_items)


# Task 3: LOAD to ClickHouse (HTTP Interface)
def _ch_insert(table, rows):
    """Insert rows (list of dicts) ke ClickHouse via HTTP JSONEachRow."""
    query = f"INSERT INTO {CLICKHOUSE_DB}.{table} FORMAT JSONEachRow"
    url   = (
        f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
        f"?query={requests.utils.quote(query)}"
        f"&user={CLICKHOUSE_USER}&password={CLICKHOUSE_PASSWORD}"
    )
    payload = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
    resp = requests.post(url, data=payload, timeout=120)
    resp.raise_for_status()


def load_to_clickhouse(**context):
    """Load orders + order_items ke ClickHouse."""
    with open(FLAT_ORDERS) as f:
        orders = json.load(f)
    with open(FLAT_ITEMS) as f:
        items = json.load(f)

    if orders:
        _ch_insert("orders", orders)
        logging.info(f"Loaded {len(orders)} rows → ecommerce.orders")

    if items:
        _ch_insert("order_items", items)
        logging.info(f"Loaded {len(items)} rows → ecommerce.order_items")

    return len(orders), len(items)

# Task 4: VALIDATE
def validate_load(**context):
    """Verifikasi jumlah record di ClickHouse vs hasil transform."""
    def _count(table):
        url = (
            f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
            f"?query=SELECT+count(*)+FROM+{CLICKHOUSE_DB}.{table}"
            f"&user={CLICKHOUSE_USER}&password={CLICKHOUSE_PASSWORD}"
        )
        return int(requests.get(url, timeout=30).text.strip())

    orders_in_ch = _count("orders")
    items_in_ch  = _count("order_items")
    logging.info(f"ClickHouse count → orders: {orders_in_ch}, order_items: {items_in_ch}")

    exp_orders = context["ti"].xcom_pull(key="order_count",      task_ids="transform_orders")
    exp_items  = context["ti"].xcom_pull(key="order_item_count", task_ids="transform_orders")

    if exp_orders and orders_in_ch < exp_orders:
        raise ValueError(f"orders mismatch: expected {exp_orders}, got {orders_in_ch}")
    if exp_items and items_in_ch < exp_items:
        raise ValueError(f"order_items mismatch: expected {exp_items}, got {items_in_ch}")

    return {"orders": orders_in_ch, "order_items": items_in_ch}

# DAG Definition
with DAG(
    dag_id="orders_pipeline",
    description="ETL: Orders API → ClickHouse (orders + order_items)",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
    tags=["orders", "etl", "clickhouse"],
) as dag:

    t_extract = PythonOperator(
        task_id="extract_orders",
        python_callable=extract_orders,
        provide_context=True,
    )
    t_transform = PythonOperator(
        task_id="transform_orders",
        python_callable=transform_orders,
        provide_context=True,
    )
    t_load = PythonOperator(
        task_id="load_to_clickhouse",
        python_callable=load_to_clickhouse,
        provide_context=True,
    )
    t_validate = PythonOperator(
        task_id="validate_load",
        python_callable=validate_load,
        provide_context=True,
    )
    t_cleanup = BashOperator(
        task_id="cleanup_temp_files",
        bash_command=f"rm -f {RAW_PATH} {FLAT_ORDERS} {FLAT_ITEMS} && echo 'Cleanup done'",
    )

    #Pipeline Flow
    t_extract >> t_transform >> t_load >> t_validate >> t_cleanup
