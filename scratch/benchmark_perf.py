import os
import sys
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from models import db, User

app = create_app()

query_count = 0

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    global query_count
    query_count += 1

def benchmark_endpoint(client, url, name):
    global query_count
    query_count = 0
    t0 = time.perf_counter()
    resp = client.get(url)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"[{name}]")
    print(f"  Status: {resp.status_code}")
    print(f"  Queries SQL: {query_count}")
    print(f"  Tiempo: {elapsed_ms:.2f} ms")
    assert resp.status_code in (200, 302), f"Error in {url}"
    return query_count, elapsed_ms

def run_benchmarks():
    with app.app_context():
        # Verificar indices en la base de datos
        with db.engine.connect() as conn:
            idx_list = conn.execute(db.text("SELECT name, tbl_name FROM sqlite_master WHERE type = 'index';")).fetchall()
            print("=== INDICES EN BASE DE DATOS ===")
            for name, tbl in idx_list:
                if name and not name.startswith("sqlite_autoindex"):
                    print(f"  • {name} ON {tbl}")

        client = app.test_client()

        # Login como admin
        client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)

        print("\n=== RENDIMIENTO DE ENDPOINTS ===")
        benchmark_endpoint(client, "/", "Dashboard Principal (con KPIs y tabla)")
        benchmark_endpoint(client, "/mis-casos-front", "Bandeja Front (badges y casos)")
        benchmark_endpoint(client, "/calidad", "Módulo Calidad TYQ (métricas y desglose)")
        benchmark_endpoint(client, "/admin/estadisticas", "Estadísticas Admin (agrupaciones)")
        benchmark_endpoint(client, "/buscar?q=BGH", "Búsqueda Global Universal")
        benchmark_endpoint(client, "/reportes", "Informes y Reportes")

        print("\n=== BENCHMARK COMPLETADO CON ÉXITO ===")

if __name__ == "__main__":
    run_benchmarks()
