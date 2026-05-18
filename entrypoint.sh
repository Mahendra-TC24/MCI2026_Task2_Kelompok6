#!/bin/bash
set -e

echo "Menjalankan Migrasi Database Airflow"
airflow db migrate

echo "Membuat User Admin"
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com || true

echo "Menyalakan Scheduler & Webserver"
airflow scheduler &
exec airflow webserver --port 8080