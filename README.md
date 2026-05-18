# Data Pipeline E-Commerce ETL
## Pipeline Orchestration & Data Visualization
### Integrasi Otomatis: Apache Airflow ──► ClickHouse ──► Metabase via Docker
 
> **Modul 2 & 3** | Dataset: `http://96.9.212.102:8000/orders`
 
---
 
## Deskripsi Proyek
 
Dokumen ini merupakan panduan komprehensif untuk infrastruktur, arsitektur, operasional, serta pemeliharaan sistem **data pipeline e-commerce otomatis** berbasis ekosistem Docker. Pipeline ini mengekstrak data pesanan dari API eksternal, mentransformasikannya, dan memuatnya ke ClickHouse sebagai data warehouse untuk divisualisasikan melalui Metabase.
 
---

## Struktur Project
 
```
orders-pipeline/
│
├── dags/
│   ├── scripts/
│   │   ├── fetch_orders.py         ← Script extract data dari API
│   │   └── process_orders.py       ← Script flatten nested JSON
│   ├── orders_pipeline_dag.py      ← Airflow DAG (ETL orchestration)
│   └── orders_pipeline.py          ← Pipeline runner (testing lokal)
│
├── clickhouse/
│   └── clickhouse_setup.sql        ← CREATE DATABASE, TABLE + query analitik
│
├── data_lake/                      ← Folder penyimpanan data raw (opsional)
│
├── Dockerfile                      ← Image Airflow + dependencies
├── docker-compose.yml              ← Stack: Airflow + ClickHouse + Metabase
├── requirements.txt                ← Python dependencies
├── sql-metabase.sql                ← 10+ SQL queries siap paste ke Metabase
├── .gitignore
└── README.md
```
 
## Arsitektur & Alur Pipeline (DAG)
 
Sistem beroperasi secara sekuensial dengan struktur dependensi tugas terarah berbasis **Directed Acyclic Graph (DAG)**:
 
```
  [API: /orders]
       │
       ▼
 extract_orders       ← fetch_orders.py      → /tmp/orders_raw.json
       │
       ▼
 transform_orders     ← process_orders.py    → /tmp/orders_flat.json
                                             → /tmp/order_items_flat.json
       │
       ▼
 load_to_clickhouse   ← HTTP JSONEachRow     → ecommerce.orders
                                             → ecommerce.order_items
       │
       ▼
 validate_load        ← SELECT count(*)
       │
       ▼
 cleanup_temp_files   ← rm /tmp/*.json
```

### Detail Siklus Pipeline

| # | Task | Deskripsi |
|---|------|-----------|
| 1 | **Extract** (`extract_orders`) | Request HTTP GET ke `http://96.9.212.102:8000/orders`. Mengekstrak 100 rekaman JSON bersarang dan menyimpannya di `/tmp/orders_raw.json`. |
| 2 | **Transform** (`transform_orders`) | Membedah JSON mentah: atribut makro disimpan ke `/tmp/orders_flat.json`, sub-produk didenormalisasi menjadi 912 item di `/tmp/order_items_flat.json`. Termasuk konversi indeks hari (0–6) ke nama hari (Sunday, Monday, dst.). |
| 3 | **Load** (`load_to_clickhouse`) | Via driver `clickhouse-connect`, data JSON di-*bulk insert* ke tabel target di database `ecommerce`. |
| 4 | **Cleanup** (`cleanup_temp_files`) | Menghapus seluruh file JSON temporer di `/tmp/` setelah pemuatan terverifikasi sukses. |

---

## Struktur File Konfigurasi Utama

### `orders_pipeline_dag.py` — DAG Orchestrator
- Dikonfigurasi dengan `catchup=False` untuk mencegah *backfilling* antrean historis.
- Dijadwalkan **harian** (`@daily`) untuk menjamin kebaruan data analitis.

### `clickhouse_setup.sql` — Data Warehouse Schema
Menginisialisasi dua tabel inti di database `ecommerce`:

- **`orders`** — Menyimpan transaksi makro: waktu checkout, ID pengguna, dan metrik waktu.
- **`order_items`** — Menyimpan data atomik produk, nama departemen, dan status reorder.

> Kedua tabel menggunakan engine **`MergeTree()`** dengan `ORDER BY` teroptimasi untuk kueri agregasi OLAP berskala besar.

### `docker-compose.yml` — Container Conductor
- Mengatur topologi jaringan internal terisolasi antar kontainer.
- Port HTTP ClickHouse (`8123`) diarahkan langsung ke jaringan Metabase.
- Kontainer Metabase mengenali host dengan nama servis `clickhouse` tanpa eksposur port eksternal.

---

## Panduan Pengoperasian

### Langkah 1 — Jalankan Semua Kontainer

```bash
docker-compose up -d --build
```

### Langkah 2 — Verifikasi Status Kontainer

Pastikan komponen berikut berstatus **Running**:
- `airflow-webserver`
- `clickhouse`
- `metabase`

### Langkah 3 — Aktifkan DAG di Airflow

Buka **http://localhost:8080**, aktifkan toggle DAG `orders_pipeline`, lalu klik **Trigger DAG**.

### Langkah 4 — Hubungkan Metabase ke ClickHouse

Buka **http://localhost:3000** dan konfigurasikan koneksi database:

| Parameter | Nilai |
|-----------|-------|
| Database Type | `ClickHouse` |
| Host | `clickhouse` *(nama servis internal Docker)* |
| Port | `8123` |
| Database Name | `ecommerce` |
| Username | `default` |
| Password | `admin` |

---

## Hasil Analisis Dashboard Metabase

Dashboard terpusat bertema gelap (**Unified Business Dashboard**) menampilkan ringkasan eksekutif:

### Metrik Utama

| Metrik | Nilai |
|--------|-------|
| Total Transaksi | **100** |
| Unit Produk Terjual | **912** |
| Avg Basket Size | **9.12 item/transaksi** |

> Rata-rata 9.12 item per transaksi mengindikasikan dominasi segmen pembelanja grosir/borongan.

### Analisis Perilaku Waktu

- **Hari tersibuk:** Sunday (Minggu) — volume belanja tertinggi.
- **Hari terendah:** Thursday (Kamis) — titik operasional terendah.
- **Peak hours:** 09:00–10:00 pagi (14–15 checkout/jam); turun drastis di bawah 1 order setelah pukul 17:00.

### Rekomendasi Bisnis

> Luncurkan **flash sale** atau **subsidi ongkos kirim** pada hari **Minggu pukul 09:00 pagi** untuk memaksimalkan conversion rate.

### Produk Terlaris (Top 3)

| Peringkat | Produk |
|-----------|--------|
| 1 | Organic Strawberries |
| 2 | Bag of Organic Bananas |
| 3 | Organic Baby Spinach |

> Dominasi penuh produk pangan organik segar pada 10 besar kategori terlaris.

---

## Troubleshooting & Pemeliharaan

### Skenario: `FileNotFoundError` pada `load_to_clickhouse`

**Penyebab:** Restart mesin host / Docker Desktop dimatikan → file `/tmp/` terhapus total.

**Prosedur Pemulihan via UI Airflow:**

1. Buka visualisasi DAG `orders_pipeline` di Airflow.
2. Klik kotak tugas **`extract_orders`** (paling kiri).
3. Pada panel detail, tekan tombol **Clear task**.
4. Pastikan opsi **Downstream** dalam status **aktif (tercentang)**.
5. Klik **Confirm**.

**Hasil:** Airflow akan mengulang siklus dari awal — meregenerasi file JSON di `/tmp/` dan mengalirkan ulang data ke ClickHouse hingga semua status kembali `SUCCESS`.

---

## Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| Orchestration | Apache Airflow |
| Data Warehouse | ClickHouse |
| Visualization | Metabase |
| Containerization | Docker / Docker Compose |
| Driver | `clickhouse-connect` (Python) |
| Data Format | JSON (nested → flat) |


## Kontribusi Tim

| Nama | Tanggung Jawab |
| :--- | :--- |
| **Mahendra Agung Darmawan** | Arsitektur pipeline ETL, implementasi DAG Airflow, konfigurasi ClickHouse (schema & optimasi query), Docker Compose setup, integrasi seluruh komponen, pengujian end-to-end, dan dokumentasi teknis. |
| **Pradipta Raja Mahendra** | Setup dan konfigurasi Metabase dashboard, pembuatan 10+ SQL queries analitik (`sql-metabase.sql`), desain layout visualisasi, serta analisis hasil dashboard. |


### Pembagian Kerja Detail
 
**Mahendra Agung Darmawan**
- Merancang dan mengimplementasikan seluruh alur ETL (Extract → Transform → Load → Cleanup)
- Menulis script `fetch_orders.py` dan `process_orders.py`
- Membuat dan mengkonfigurasi `orders_pipeline_dag.py` beserta scheduling harian
- Merancang skema tabel ClickHouse dengan engine MergeTree yang dioptimalkan
- Menyusun `docker-compose.yml` dan `Dockerfile` untuk orkestrasi kontainer
- Melakukan pengujian pipeline secara end-to-end dan penanganan error
- Menyusun dokumentasi teknis komprehensif
- Mengkonfigurasi koneksi Metabase ke ClickHouse

**Pradipta Raja**
- Mengkonfigurasi koneksi Metabase ke ClickHouse
- Menulis 10+ SQL queries analitik untuk KPI cards dan visualisasi (`sql-metabase.sql`)
- Membangun layout dashboard "Orders Analytics" (6 KPI + 12 visualisasi)
- Menyusun analisis dan laporan beserta README.MD berdasarkan temuan data (peak hours, produk terlaris, rekomendasi promosi)

