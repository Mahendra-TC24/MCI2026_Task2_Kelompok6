--  Kumpulan SQL Query siap pakai untuk Metabase
--  Database: ecommerce (ClickHouse)
--  Tabel   : orders, order_items

--  SECTION 1: KPI CARDS (Number visualization)
-- [KPI-1] Total Orders
SELECT count() AS "Total Orders"
FROM ecommerce.orders;

-- [KPI-2] Total Users Unik
SELECT count(DISTINCT user_id) AS "Total Users"
FROM ecommerce.orders;

-- [KPI-3] Total Produk Dipesan
SELECT count() AS "Total Items Ordered"
FROM ecommerce.order_items;

-- [KPI-4] Rata-rata Produk per Order
SELECT round(avg(total_items), 1) AS "Avg Items / Order"
FROM ecommerce.orders;

-- [KPI-5] Rata-rata Hari Antar Order
SELECT round(avg(days_since_prior_order), 1) AS "Avg Days Between Orders"
FROM ecommerce.orders
WHERE days_since_prior_order IS NOT NULL;

-- [KPI-6] Reorder Rate Keseluruhan (%)
SELECT round(avg(reordered) * 100, 1) AS "Overall Reorder Rate %"
FROM ecommerce.order_items;


--  SECTION 2: WAKTU & POLA BELANJA
-- [VIZ-1] Order per Hari dalam Seminggu
SELECT
    order_dow                   AS "DOW (0=Sun)",
    order_dow_name              AS "Day",
    count()                     AS "Total Orders"
FROM ecommerce.orders
GROUP BY order_dow, order_dow_name
ORDER BY order_dow;

-- [VIZ-2] Peak Hours — Order per Jam
-- Chart: Line Chart / Area Chart | X: Hour | Y: Total Orders
SELECT
    order_hour_of_day           AS "Hour (0-23)",
    count()                     AS "Total Orders"
FROM ecommerce.orders
GROUP BY order_hour_of_day
ORDER BY order_hour_of_day;

-- [VIZ-3] Heatmap: Jam vs Hari dalam Seminggu
-- Chart: Pivot Table | Row: Day | Col: Hour | Value: Orders
SELECT
    order_dow_name              AS "Day",
    order_dow,
    order_hour_of_day           AS "Hour",
    count()                     AS "Orders"
FROM ecommerce.orders
GROUP BY order_dow_name, order_dow, order_hour_of_day
ORDER BY order_dow, order_hour_of_day;

-- [VIZ-4] Distribusi: Berapa Hari Sejak Order Terakhir?
-- Chart: Bar Chart / Histogram
SELECT
    round(days_since_prior_order) AS "Days Since Prior Order",
    count()                       AS "Order Count"
FROM ecommerce.orders
WHERE days_since_prior_order IS NOT NULL
GROUP BY days_since_prior_order
ORDER BY days_since_prior_order;


--  SECTION 3: PRODUK
-- [VIZ-5] Top 10 Produk Paling Sering Dipesan
SELECT
    product_name                AS "Product",
    department                  AS "Department",
    aisle                       AS "Aisle",
    count()                     AS "Times Ordered",
    sum(reordered)              AS "Times Reordered",
    round(avg(reordered) * 100, 1) AS "Reorder Rate %"
FROM ecommerce.order_items
GROUP BY product_name, department, aisle
ORDER BY "Times Ordered" DESC
LIMIT 10;

-- [VIZ-6] Top 10 Produk dengan Reorder Rate Tertinggi
-- Chart: Bar Chart (Horizontal)
SELECT
    product_name                AS "Product",
    department                  AS "Department",
    count()                     AS "Times Ordered",
    round(avg(reordered) * 100, 1) AS "Reorder Rate %"
FROM ecommerce.order_items
GROUP BY product_name, department
HAVING count() >= 3            -- minimal 3x dipesan agar valid
ORDER BY "Reorder Rate %" DESC
LIMIT 10;

-- [VIZ-7] Distribusi Items per Order
-- Chart: Bar Chart
SELECT
    total_items                 AS "Items in Order",
    count()                     AS "Number of Orders"
FROM ecommerce.orders
GROUP BY total_items
ORDER BY total_items;


--  SECTION 4: DEPARTMENT & AISLE
-- [VIZ-8] Orders per Department
SELECT
    department                  AS "Department",
    count()                     AS "Items Ordered",
    count(DISTINCT product_id)  AS "Unique Products",
    sum(reordered)              AS "Reordered Count",
    round(avg(reordered) * 100, 1) AS "Reorder Rate %"
FROM ecommerce.order_items
GROUP BY department
ORDER BY "Items Ordered" DESC;

-- [VIZ-9] Top 10 Aisle Terpopuler
SELECT
    aisle                       AS "Aisle",
    department                  AS "Department",
    count()                     AS "Items Ordered",
    count(DISTINCT product_id)  AS "Unique Products"
FROM ecommerce.order_items
GROUP BY aisle, department
ORDER BY "Items Ordered" DESC
LIMIT 10;

-- [VIZ-10] Reorder Rate per Department
SELECT
    department                  AS "Department",
    count()                     AS "Total Items",
    sum(reordered)              AS "Reordered",
    round(avg(reordered) * 100, 1) AS "Reorder Rate %"
FROM ecommerce.order_items
GROUP BY department
ORDER BY "Reorder Rate %" DESC;


--  SECTION 5: USER BEHAVIOR
-- [VIZ-11] Top 10 User Paling Aktif
SELECT
    user_id                             AS "User ID",
    count()                             AS "Total Orders",
    sum(total_items)                    AS "Total Items Ordered",
    max(order_number)                   AS "Max Order Number",
    round(avg(days_since_prior_order), 1) AS "Avg Days Between Orders",
    round(avg(total_reordered * 100.0 / total_items), 1) AS "Avg Reorder Rate %"
FROM ecommerce.orders
GROUP BY user_id
ORDER BY "Total Orders" DESC
LIMIT 10;

-- [VIZ-12] Posisi dalam Keranjang vs Reorder Rate
SELECT
    add_to_cart_order           AS "Cart Position",
    count()                     AS "Times at This Position",
    round(avg(reordered) * 100, 1) AS "Reorder Rate %"
FROM ecommerce.order_items
WHERE add_to_cart_order <= 20
GROUP BY add_to_cart_order
ORDER BY add_to_cart_order;
