# ============================================================
# CONEXION.PY - MÓDULO DE CONEXIÓN A BASE DE DATOS
# ============================================================

import os
import psycopg2
from psycopg2 import sql, extras
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

# ============================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ============================================================

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'mteps_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'schema': os.getenv('DB_SCHEMA', 'public')  # ← Solo para referencia, no se usa
}

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# FUNCIONES DE CONEXIÓN
# ============================================================

def get_db_connection():
    """
    Obtiene una conexión a la base de datos
    Retorna: conexión o None si falla
    """
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        # ⭐ NO ESTABLECER ESQUEMA FIJO
        # Así puedes acceder a TODOS los esquemas:
        #   - externos_mteps
        #   - mteps_d_tickets
        #   - mteps_tramites
        #   - etc.
        logger.info("Conexión a la base de datos establecida")
        return conn
    except Exception as e:
        logger.error(f"Error de conexión a la base de datos: {e}")
        return None


def test_db_connection():
    """
    Prueba la conexión a la base de datos
    Retorna: True si es exitosa, False si falla
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                logger.info("Prueba de conexión exitosa")
                return True
        except Exception as e:
            logger.error(f" Error al probar conexión: {e}")
            return False
        finally:
            conn.close()
    return False


# ============================================================
# FUNCIONES PARA BUSCAR EMPRESAS
# ============================================================
# ============================================================
# FUNCIONES PARA BUSCAR EMPRESAS
# ============================================================
# ============================================================
# FUNCIONES PARA BUSCAR EMPRESAS
# ============================================================

# ============================================================
# FUNCIONES PARA BUSCAR EMPRESAS
# ============================================================

def buscar_empresas(termino, limite=10):
    """
    Busca empresas en la base de datos por nombre o NIT
    Usa la tabla dtck_empleador_nit en mteps_d_tickets
    """
    consulta = """
        SELECT 
            id,
            nit,
            razon_social,
            estado
        FROM mteps_d_tickets.dtck_empleador_nit
        WHERE UPPER(razon_social) LIKE UPPER(%s)
        OR UPPER(nit) LIKE UPPER(%s)
        ORDER BY razon_social
        LIMIT %s;
    """
    termino_busqueda = f"%{termino}%"
    success, mensaje, resultado = ejecutar_consulta(
        consulta, 
        (termino_busqueda, termino_busqueda, limite)
    )
    
    empresas = []
    if success and resultado:
        for fila in resultado['filas']:
            empresas.append({
                'id_empresa': fila[0],      # id
                'nit': fila[1],              # nit
                'razon_social': fila[2],     # razon_social
                'estado': fila[3]            # estado
            })
    return empresas


def obtener_empresa_por_id(id_empresa):
    """
    Obtiene los datos de una empresa por su ID
    """
    consulta = """
        SELECT 
            id,
            nit,
            razon_social,
            estado
        FROM mteps_d_tickets.dtck_empleador_nit
        WHERE id = %s;
    """
    success, mensaje, resultado = ejecutar_consulta(consulta, (id_empresa,))
    
    if success and resultado and resultado['filas']:
        fila = resultado['filas'][0]
        return {
            'id_empresa': fila[0],
            'nit': fila[1],
            'razon_social': fila[2],
            'estado': fila[3]
        }
    return None

def cerrar_conexion(conn):
    """Cierra la conexión a la base de datos"""
    if conn:
        try:
            conn.close()
            logger.info("Conexión cerrada")
        except Exception as e:
            logger.error(f"Error al cerrar conexión: {e}")


# ============================================================
# FUNCIONES PARA EJECUTAR SCRIPTS
# ============================================================

def ejecutar_script_sql(script, descripcion="Script SQL"):
    """
    Ejecuta un script SQL en la base de datos
    Retorna: (success, mensaje, resultados)
    """
    conn = get_db_connection()
    if not conn:
        return False, "No se pudo conectar a la base de datos", None
    
    try:
        with conn.cursor() as cur:
            cur.execute(script)
            
            try:
                resultados = cur.fetchall()
            except Exception:
                resultados = []
            
            conn.commit()
            logger.info(f"{descripcion} ejecutado correctamente")
            return True, f"{descripcion} ejecutado correctamente", resultados
            
    except psycopg2.Error as e:
        conn.rollback()
        error_msg = f"Error de PostgreSQL: {e.pgerror}"
        logger.error(f"{error_msg}")
        return False, error_msg, None
    except Exception as e:
        conn.rollback()
        error_msg = f"Error: {str(e)}"
        logger.error(f"{error_msg}")
        return False, error_msg, None
    finally:
        conn.close()


def ejecutar_script_en_bloques(script, descripcion="Script SQL", bloque_size=500):
    """
    Ejecuta un script SQL dividido en bloques (para inserciones masivas)
    """
    conn = get_db_connection()
    if not conn:
        return False, "No se pudo conectar a la base de datos", None
    
    try:
        with conn.cursor() as cur:
            lineas = script.split(';')
            bloques = []
            bloque_actual = []
            
            for linea in lineas:
                linea = linea.strip()
                if not linea:
                    continue
                bloque_actual.append(linea)
                if len(bloque_actual) >= bloque_size:
                    bloques.append('; '.join(bloque_actual))
                    bloque_actual = []
            
            if bloque_actual:
                bloques.append('; '.join(bloque_actual))
            
            total_bloques = len(bloques)
            exitosos = 0
            
            for i, bloque in enumerate(bloques):
                if bloque:
                    try:
                        cur.execute(bloque + ';')
                        conn.commit()
                        exitosos += 1
                        logger.info(f"Bloque {i+1}/{total_bloques} ejecutado")
                    except Exception as e:
                        conn.rollback()
                        logger.warning(f"Error en bloque {i+1}: {e}")
            
            mensaje = f"{descripcion}: {exitosos}/{total_bloques} bloques exitosos"
            return True, mensaje, None
            
    except Exception as e:
        conn.rollback()
        error_msg = f"Error: {str(e)}"
        logger.error(f"{error_msg}")
        return False, error_msg, None
    finally:
        conn.close()


# ============================================================
# FUNCIONES PARA CONSULTAS
# ============================================================

def ejecutar_consulta(consulta, parametros=None, descripcion="Consulta"):
    """
    Ejecuta una consulta SQL y retorna los resultados
    """
    conn = get_db_connection()
    if not conn:
        return False, "No se pudo conectar a la base de datos", None
    
    try:
        with conn.cursor() as cur:
            if parametros:
                cur.execute(consulta, parametros)
            else:
                cur.execute(consulta)
            
            try:
                resultados = cur.fetchall()
                columnas = [desc[0] for desc in cur.description] if cur.description else []
            except Exception:
                resultados = []
                columnas = []
            
            conn.commit()
            logger.info(f"{descripcion} ejecutada correctamente")
            return True, f"{descripcion} ejecutada correctamente", {
                'columnas': columnas,
                'filas': resultados,
                'total': len(resultados)
            }
            
    except Exception as e:
        conn.rollback()
        error_msg = f"Error: {str(e)}"
        logger.error(f"{error_msg}")
        return False, error_msg, None
    finally:
        conn.close()


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def listar_esquemas():
    """
    Lista todos los esquemas de la base de datos
    """
    consulta = """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT LIKE 'pg_%'
        AND schema_name != 'information_schema'
        ORDER BY schema_name;
    """
    success, mensaje, resultado = ejecutar_consulta(consulta)
    
    if success and resultado:
        return [fila[0] for fila in resultado['filas']]
    return []


def listar_tablas():
    """
    Lista todas las tablas con su esquema
    """
    consulta = """
        SELECT 
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema NOT LIKE 'pg_%'
        AND table_schema != 'information_schema'
        ORDER BY table_schema, table_name;
    """
    success, mensaje, resultado = ejecutar_consulta(consulta)
    
    if success and resultado:
        return resultado['filas']
    return []


def verificar_tabla_existe(tabla, esquema=None):
    """
    Verifica si una tabla existe en la base de datos
    """
    if esquema:
        consulta = """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s
            );
        """
        success, mensaje, resultado = ejecutar_consulta(consulta, (esquema, tabla))
    else:
        # Buscar en todos los esquemas
        consulta = """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = %s
            );
        """
        success, mensaje, resultado = ejecutar_consulta(consulta, (tabla,))
    
    if success and resultado and resultado['filas']:
        return resultado['filas'][0][0]
    return False


def get_db_info():
    """
    Retorna información de la configuración de la base de datos
    """
    return {
        'host': DB_CONFIG['host'],
        'port': DB_CONFIG['port'],
        'database': DB_CONFIG['database'],
        'user': DB_CONFIG['user'],
        'conectado': test_db_connection()
    }


# ============================================================
# PROBAR CONEXIÓN AL IMPORTAR EL MÓDULO
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PYPLAN - CONEXIÓN A BASE DE DATOS")
    print("=" * 60)
    
    if test_db_connection():
        print(" Conexión establecida correctamente")
        info = get_db_info()
        print(f" Host: {info['host']}")
        print(f" Base de datos: {info['database']}")
        print(f" Usuario: {info['user']}")
        
        # Mostrar esquemas disponibles
        esquemas = listar_esquemas()
        print(f"Esquemas disponibles: {len(esquemas)}")
        for i, esquema in enumerate(esquemas[:5]):
            print(f"      {i+1}. {esquema}")
        if len(esquemas) > 5:
            print(f"      ... y {len(esquemas) - 5} más")
    else:
        print("Error de conexión a la base de datos")
        print("   Verifica tus credenciales en el archivo .env")