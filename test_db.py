# test_db.py - Prueba de conexión a base de datos
from conexion import test_db_connection, get_db_info, listar_esquemas

print("=" * 50)
print("🔌 PRUEBA DE CONEXIÓN")
print("=" * 50)

if test_db_connection():
    print("✅ Conexión exitosa")
    info = get_db_info()
    print(f"Host: {info['host']}")
    print(f"BD: {info['database']}")
    print(f"Usuario: {info['user']}")
    print(f"Conectado: {info['conectado']}")
    
    # Listar esquemas
    esquemas = listar_esquemas()
    print(f"Esquemas disponibles: {len(esquemas)}")
    for e in esquemas[:5]:
        print(f"  - {e}")
else:
    print("❌ Error de conexión")
    print("Revisa tu archivo .env")