import argparse
import json
import logging
import os
import requests
import sys
from datetime import datetime

# Tambahkan folder scripts ke path jika dijalankan dari luar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from fetch_orders   import fetch_orders
from process_orders import flatten_orders

# ── Konfigurasi ───────────────────────────────────────────
CLICKHOUSE_HOST     = os.getenv("CLICKHOUSE_HOST",     "localhost")
CLICKHOUSE_PORT     = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB       = os.getenv("CLICKHOUSE_DB",       "ecommerce")
CLICKHOUSE_USER     = os.getenv("CLICKHOUSE_USER",     "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin")

RAW_PATH    = "/tmp/orders_raw.json"
ORDERS_PATH = "/tmp/orders_flat.json"
ITEMS_PATH  = "/tmp/order_items_flat.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


#Helpers 
def ch_url(query: str) -> str:
    return (
        f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
        f"?query={requests.utils.quote(query)}"
        f"&user={CLICKHOUSE_USER}&password={CLICKHOUSE_PASSWORD}"
    )


def ch_insert(table: str, rows: list) -> None:
    query   = f"INSERT INTO {CLICKHOUSE_DB}.{table} FORMAT JSONEachRow"
    payload = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
    resp    = requests.post(ch_url(query), data=payload, timeout=120)
    resp.raise_for_status()


def ch_count(table: str) -> int:
    resp = requests.get(
        ch_url(f"SELECT count(*) FROM {CLICKHOUSE_DB}.{table}"),
        timeout=30,
    )
    resp.raise_for_status()
    return int(resp.text.strip())


#Step functions
def step_fetch():
    log.info("=" * 50)
    log.info("STEP 1: EXTRACT")
    log.info("=" * 50)
    result = fetch_orders(output_path=RAW_PATH)
    log.info(f"  ✔ {result['order_count']} orders diambil")
    return result


def step_transform():
    log.info("=" * 50)
    log.info("STEP 2: TRANSFORM")
    log.info("=" * 50)
    result = flatten_orders(
        raw_path=RAW_PATH,
        orders_out=ORDERS_PATH,
        items_out=ITEMS_PATH,
    )
    log.info(f"  ✔ orders flat      : {result['order_count']} baris")
    log.info(f"  ✔ order_items flat : {result['order_item_count']} baris")
    return result


def step_load():
    log.info("=" * 50)
    log.info("STEP 3: LOAD → ClickHouse")
    log.info("=" * 50)

    with open(ORDERS_PATH) as f:
        orders = json.load(f)
    with open(ITEMS_PATH) as f:
        items = json.load(f)

    ch_insert("orders", orders)
    log.info(f"  ✔ {len(orders)} baris → ecommerce.orders")

    ch_insert("order_items", items)
    log.info(f"  ✔ {len(items)} baris → ecommerce.order_items")

    return {"loaded_orders": len(orders), "loaded_items": len(items)}


def step_validate():
    log.info("=" * 50)
    log.info("STEP 4: VALIDATE")
    log.info("=" * 50)

    orders_n = ch_count("orders")
    items_n  = ch_count("order_items")

    log.info(f"  ecommerce.orders      : {orders_n} baris")
    log.info(f"  ecommerce.order_items : {items_n} baris")

    if orders_n == 0 or items_n == 0:
        raise ValueError("Validasi GAGAL: tabel kosong!")

    log.info("  ✔ Validasi BERHASIL")
    return {"orders": orders_n, "order_items": items_n}


#Main
def run_all():
    start = datetime.utcnow()
    log.info("🚀 Pipeline dimulai")

    r1 = step_fetch()
    r2 = step_transform()
    r3 = step_load()
    r4 = step_validate()

    elapsed = (datetime.utcnow() - start).total_seconds()
    log.info(f"\n✅ Pipeline selesai dalam {elapsed:.1f}s")
    log.info(f"   orders      : {r4['orders']}")
    log.info(f"   order_items : {r4['order_items']}")


STEPS = {
    "fetch":     step_fetch,
    "transform": step_transform,
    "load":      step_load,
    "validate":  step_validate,
    "all":       run_all,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orders ETL Pipeline")
    parser.add_argument(
        "--step",
        choices=list(STEPS.keys()),
        default="all",
        help="Step yang dijalankan (default: all)",
    )
    args = parser.parse_args()
    STEPS[args.step]()
