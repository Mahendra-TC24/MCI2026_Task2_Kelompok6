"""
fetch_orders.py
Script untuk mengambil data orders dari REST API
dan menyimpannya sebagai file JSON mentah.

"""

import requests
import json
import logging
import os
from datetime import datetime

#Konfigurasi
API_URL      = os.getenv("ORDERS_API_URL", "http://96.9.212.102:8000/orders")
OUTPUT_PATH  = os.getenv("RAW_OUTPUT_PATH", "/tmp/orders_raw.json")
TIMEOUT      = int(os.getenv("API_TIMEOUT", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def fetch_orders(api_url: str = API_URL, output_path: str = OUTPUT_PATH) -> dict:
    """
    Fetch orders dari API endpoint dan simpan ke file JSON.

    Returns:
        dict berisi metadata hasil fetch
    """
    logging.info(f"Fetching data dari: {api_url}")

    try:
        response = requests.get(api_url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request timeout setelah {TIMEOUT}s ke {api_url}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error: {e}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Tidak bisa konek ke {api_url}")

    payload = response.json()

    # Normalisasi: bisa berupa list langsung atau dict dengan key 'orders'
    if isinstance(payload, list):
        orders = payload
        total  = len(orders)
    else:
        orders = payload.get("orders", [])
        total  = payload.get("total_orders", len(orders))

    # Simpan raw payload (pertahankan struktur asli)
    os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logging.info(f"Berhasil fetch {len(orders)} orders (total API: {total})")
    logging.info(f"Raw data disimpan ke: {output_path}")

    return {
        "api_url":       api_url,
        "order_count":   len(orders),
        "total_orders":  total,
        "output_path":   output_path,
        "fetched_at":    datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    # Jalankan langsung untuk testing
    result = fetch_orders()
    print(json.dumps(result, indent=2))
