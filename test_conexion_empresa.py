# ============================================================
# TEST_CONEXION_EMPRESA.PY - PROBAR CONEXIÓN A BD DE EMPRESAS
# ============================================================

import sys
import os

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from conexion_empresa import (
    test_empresa_connection,
    buscar_empresas_externo,
    obtener_empresa_por_id_externo,
    obtener_id_empresa_por_nit,
    get_empresa_db_info,
    close_empresa_connections
)

def test_conexion():
    """Prueba completa de la conexión a la BD de empresas"""
    
    print("=" * 70)
    print("🔍 PRUEBA DE CONEXIÓN A BASE DE DATOS DE EMPRESAS")
    print("=" * 70)
    
    # 1. Probar conexión
    print("\n📡 1. Probando conexión...")
    if test_empresa_connection():
        print("   ✅ Conexión exitosa")
    else:
        print("   ❌ Error de conexión")
        print("   Verifica las variables en el archivo .env:")
        print("   - DB_EMPRESA_HOST")
        print("   - DB_EMPRESA_PORT")
        print("   - DB_EMPRESA_NAME")
        print("   - DB_EMPRESA_USER")
        print("   - DB_EMPRESA_PASSWORD")
        return False
    
    # 2. Mostrar información de la conexión
    print("\n📋 2. Información de la conexión:")
    info = get_empresa_db_info()
    print(f"   Host: {info['host']}")
    print(f"   Puerto: {info['port']}")
    print(f"   Base de datos: {info['database']}")
    print(f"   Usuario: {info['user']}")
    print(f"   Estado: {'✅ Conectado' if info['conectado'] else '❌ Desconectado'}")
    
    # 3. Probar búsqueda por término
    print("\n🔎 3. Probando búsqueda de empresas...")
    
    terminos = ["AQUINO", "MINERA", "1020"]
    for termino in terminos:
        print(f"\n   Buscando '{termino}':")
        empresas = buscar_empresas_externo(termino, limite=3)
        if empresas:
            print(f"   ✅ Encontradas {len(empresas)} empresas:")
            for emp in empresas:
                print(f"      📌 ID: {emp['id_empresa']} | NIT: {emp['nit']} | {emp['razon_social']}")
        else:
            print(f"   ⚠️ No se encontraron empresas con '{termino}'")
    
    # 4. Probar búsqueda por NIT exacto
    print("\n🔎 4. Probando búsqueda por NIT...")
    nit_test = "486067020"  # De la tabla dtck_empleador_nit
    print(f"   Buscando NIT: {nit_test}")
    id_emp = obtener_id_empresa_por_nit(nit_test)
    if id_emp:
        print(f"   ✅ ID_EMPRESA encontrado: {id_emp}")
        
        # Obtener empresa completa por ID
        empresa = obtener_empresa_por_id_externo(id_emp)
        if empresa:
            print(f"   📌 Datos completos:")
            print(f"      ID_EMPRESA: {empresa['id_empresa']}")
            print(f"      NIT: {empresa['nit']}")
            print(f"      Razón Social: {empresa['razon_social']}")
    else:
        print(f"   ⚠️ No se encontró ID_EMPRESA para NIT: {nit_test}")
    
    # 5. Cerrar conexiones
    print("\n🔒 5. Cerrando conexiones...")
    close_empresa_connections()
    print("   ✅ Conexiones cerradas")
    
    print("\n" + "=" * 70)
    print("✅ PRUEBA COMPLETADA")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    test_conexion()