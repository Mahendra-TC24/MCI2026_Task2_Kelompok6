
--1. Buat Database 
CREATE DATABASE IF NOT EXISTS ecommerce;


--2. Tabel: orders
-- Satu baris per order. Kolom order_dow_name dan agregasi

CREATE TABLE IF NOT EXISTS ecommerce.orders
(
    order_id                UInt32,
    user_id                 UInt32,
    order_number            UInt32,         -- Urutan order ke-berapa untuk user ini
    order_dow               UInt8,          -- 0=Sunday … 6=Saturday
    order_dow_name          String,         -- "Sunday", "Monday", …
    order_hour_of_day       UInt8,          -- 0–23
    days_since_prior_order  Nullable(Float32), -- NULL jika order pertama user
    eval_set                String,         -- "prior", "train", atau "test"
    total_items             UInt16,         -- jumlah produk dalam order
    total_reordered         UInt16          -- jumlah produk yang merupakan reorder
)
ENGINE = MergeTree()
ORDER BY (user_id, order_id)
SETTINGS index_granularity = 8192;


-- 3. Tabel: order_items
-- Satu baris per produk per order (hasil flatten dari array products).

CREATE TABLE IF NOT EXISTS ecommerce.order_items
(
    order_id            UInt32,
    user_id             UInt32,
    product_id          UInt32,
    product_name        String,
    aisle_id            UInt16,
    aisle               String,
    department_id       UInt8,
    department          String,
    add_to_cart_order   UInt8,      -- urutan produk ditambahkan ke keranjang
    reordered           UInt8       -- 1 = pernah dibeli sebelumnya, 0 = baru
)
ENGINE = MergeTree()
ORDER BY (order_id, product_id)
SETTINGS index_granularity = 8192;

 
--  QUERY ANALITIK (untuk Metabase / Dashboard)
--  Q1: Overview — Total orders & rata-rata items per order
SELECT
    count()                                     AS total_orders,
    count(DISTINCT user_id)                     AS total_users,
    sum(total_items)                            AS total_items_ordered,
    round(avg(total_items), 2)                  AS avg_items_per_order,
    round(avg(days_since_prior_order), 1)       AS avg_days_between_orders
FROM ecommerce.orders;


-- Q2: Order per Hari dalam Seminggu (Bar Chart)
SELECT
    order_dow_name                  AS day_of_week,
    order_dow,
    count()                         AS total_orders
FROM ecommerce.orders
GROUP BY order_dow_name, order_dow
ORDER BY order_dow;


-- Q3: Order per Jam (Heatmap / Line Chart)
SELECT
    order_hour_of_day               AS hour,
    count()                         AS total_orders
FROM ecommerce.orders
GROUP BY hour
ORDER BY hour;


-- Q4: Distribusi Jumlah Items per Order (Bar Chart)
SELECT
    total_items                     AS items_in_order,
    count()                         AS order_count
FROM ecommerce.orders
GROUP BY total_items
ORDER BY total_items;


-- Q5: Top 10 Produk Paling Sering Dipesan
SELECT
    product_name,
    department,
    aisle,
    count()                         AS times_ordered,
    sum(reordered)                  AS times_reordered,
    round(sum(reordered) * 100.0 / count(), 1) AS reorder_rate_pct
FROM ecommerce.order_items
GROUP BY product_name, department, aisle
ORDER BY times_ordered DESC
LIMIT 10;


-- Q6: Top 10 Department (by volume)
SELECT
    department,
    count()                         AS items_ordered,
    count(DISTINCT product_id)      AS unique_products,
    sum(reordered)                  AS reordered_count,
    round(sum(reordered) * 100.0 / count(), 1) AS reorder_rate_pct
FROM ecommerce.order_items
GROUP BY department
ORDER BY items_ordered DESC
LIMIT 10;

-- Q7: Top 10 Aisle (lorong) Paling Populer
SELECT
    aisle,
    department,
    count()                         AS items_ordered,
    count(DISTINCT product_id)      AS unique_products
FROM ecommerce.order_items
GROUP BY aisle, department
ORDER BY items_ordered DESC
LIMIT 10;


-- Q8: Tingkat Reorder per Department
SELECT
    department,
    count()                         AS total_items,
    sum(reordered)                  AS reordered,
    round(sum(reordered) * 100.0 / count(), 1) AS reorder_rate_pct
FROM ecommerce.order_items
GROUP BY department
ORDER BY reorder_rate_pct DESC;


-- Q9: User Paling Aktif (Top 10 by order count)
SELECT
    user_id,
    count()                         AS total_orders,
    sum(total_items)                AS total_items_ordered,
    max(order_number)               AS max_order_number,
    round(avg(days_since_prior_order), 1) AS avg_days_between_orders
FROM ecommerce.orders
GROUP BY user_id
ORDER BY total_orders DESC
LIMIT 10;


-- Q10: Posisi Item dalam Keranjang (add_to_cart_order)
SELECT
    add_to_cart_order               AS cart_position,
    count()                         AS times_ordered,
    round(avg(reordered) * 100, 1)  AS reorder_rate_pct
FROM ecommerce.order_items
WHERE add_to_cart_order <= 20   -- Fokus 20 posisi pertama
GROUP BY cart_position
ORDER BY cart_position;


-- Q11: Heatmap — Order Hour vs Day of Week
SELECT
    o.order_dow_name                AS day_of_week,
    o.order_dow,
    o.order_hour_of_day             AS hour,
    count()                         AS total_orders
FROM ecommerce.orders o
GROUP BY day_of_week, order_dow, hour
ORDER BY order_dow, hour;


-- Q12: Eval Set Distribution
SELECT
    eval_set,
    count()                         AS total_orders,
    count(DISTINCT user_id)         AS total_users
FROM ecommerce.orders
GROUP BY eval_set;


-- ── Verifikasi ────────────────────────────────────────────
SELECT 'orders'      AS tabel, count() AS total FROM ecommerce.orders
UNION ALL
SELECT 'order_items' AS tabel, count() AS total FROM ecommerce.order_items;

-- Sample data
SELECT * FROM ecommerce.orders      LIMIT 5;
SELECT * FROM ecommerce.order_items LIMIT 5;
