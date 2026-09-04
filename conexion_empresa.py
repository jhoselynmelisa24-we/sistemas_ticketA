# ============================================================
# CONEXION_EMPRESA.PY - SOLO PARA OBTENER ID_EMPRESA
# ============================================================

import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
import logging

load_dotenv()

# ============================================================
# CONFIGURACIÓN - SOLO PARA ID_EMPRESA
# ============================================================

DB_EMPRESA_CONFIG = {
    'host': os.getenv('DB_EMPRESA_HOST', '192.168.241.12'),
    'port': os.getenv('DB_EMPRESA_PORT', '5432'),
    'database': os.getenv('DB_EMPRESA_NAME', 'mintrabajo_ovt_desa'),  # ← SOLO ESTA BD
    'user': os.getenv('DB_EMPRESA_USER', 'mintrabajo'),
    'password': os.getenv('DB_EMPRESA_PASSWORD', 'mintrabajo'),
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# POOL DE CONEXIONES
# ============================================================

_empresa_pool = None
_MAX_CONNECTIONS = 5
_MIN_CONNECTIONS = 1


def init_empresa_pool():
    global _empresa_pool
    if _empresa_pool is None:
        try:
            _empresa_pool = psycopg2.pool.SimpleConnectionPool(
                _MIN_CONNECTIONS,
                _MAX_CONNECTIONS,
                host=DB_EMPRESA_CONFIG['host'],
                port=DB_EMPRESA_CONFIG['port'],
                database=DB_EMPRESA_CONFIG['database'],
                user=DB_EMPRESA_CONFIG['user'],
                password=DB_EMPRESA_CONFIG['password']
            )
            logger.info("✅ Pool de conexiones para ID_EMPRESA inicializado")
            logger.info(f"   Host: {DB_EMPRESA_CONFIG['host']}")
            logger.info(f"   Base de datos: {DB_EMPRESA_CONFIG['database']}")
        except Exception as e:
            logger.error(f"❌ Error al inicializar pool: {e}")
            raise
    return _empresa_pool


def get_empresa_connection():
    try:
        pool_instance = init_empresa_pool()
        if pool_instance:
            return pool_instance.getconn()
    except Exception as e:
        logger.error(f"Error al obtener conexión: {e}")
        return None


def return_empresa_connection(conn):
    global _empresa_pool
    if conn and _empresa_pool:
        try:
            _empresa_pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error al devolver conexión: {e}")
            try:
                conn.close()
            except:
                pass


def close_empresa_connections():
    global _empresa_pool
    if _empresa_pool:
        try:
            _empresa_pool.closeall()
            logger.info("✅ Conexiones cerradas")
        except Exception as e:
            logger.error(f"Error al cerrar conexiones: {e}")
        finally:
            _empresa_pool = None


# ============================================================
# FUNCIÓN PRINCIPAL: OBTENER SOLO ID_EMPRESA POR NIT
# ============================================================

def obtener_id_empresa_por_nit(nit):
    """
    ⭐ SOLO ESTA FUNCIÓN EXTRAE DATOS DE mintrabajo_ovt_desa
    Busca SOLO el id_empresa en public.empresa usando el NIT
    
    Args:
        nit (str): NIT de la empresa
    
    Returns:
        int: id_empresa o None si no existe
    """
    conn = None
    try:
        conn = get_empresa_connection()
        if not conn:
            logger.error("No se pudo conectar a la BD de empresas")
            return None
        
        # ⭐ CONSULTA SOLO PARA ID_EMPRESA
        consulta = """
            SELECT id_empresa
            FROM public.empresa
            WHERE nit = %s
            LIMIT 1;
        """
        
        with conn.cursor() as cur:
            cur.execute(consulta, (nit,))
            fila = cur.fetchone()
            
            if fila:
                logger.info(f"✅ ID_EMPRESA encontrado: {fila[0]} para NIT: {nit}")
                return fila[0]
            else:
                logger.warning(f"⚠️ No se encontró ID_EMPRESA para NIT: {nit}")
                return None
            
    except Exception as e:
        logger.error(f"❌ Error al obtener id_empresa: {e}")
        return None
    finally:
        if conn:
            return_empresa_connection(conn)


def obtener_empresa_por_id_externo(id_empresa):
    """
    ⭐ Obtiene datos de la empresa por ID (solo para referencia)
    """
    conn = None
    try:
        conn = get_empresa_connection()
        if not conn:
            return None
        
        consulta = """
            SELECT 
                id_empresa,
                nit,
                razon_social
            FROM public.empresa
            WHERE id_empresa = %s;
        """
        
        with conn.cursor() as cur:
            cur.execute(consulta, (id_empresa,))
            fila = cur.fetchone()
            
            if fila:
                return {
                    'id_empresa': fila[0],
                    'nit': fila[1],
                    'razon_social': fila[2]
                }
            return None
            
    except Exception as e:
        logger.error(f"❌ Error al obtener empresa por ID: {e}")
        return None
    finally:
        if conn:
            return_empresa_connection(conn)


# ============================================================
# FUNCIÓN: PROBAR CONEXIÓN
# ============================================================

def test_empresa_connection():
    conn = None
    try:
        conn = get_empresa_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                logger.info("✅ Conexión a BD de empresas exitosa")
                return True
    except Exception as e:
        logger.error(f"❌ Error en conexión: {e}")
        return False
    finally:
        if conn:
            return_empresa_connection(conn)


# ============================================================
# PROBAR CONEXIÓN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CONEXIÓN PARA ID_EMPRESA (mintrabajo_ovt_desa)")
    print("=" * 60)
    
    if test_empresa_connection():
        print("✅ Conexión establecida")
        print(f"   Host: {DB_EMPRESA_CONFIG['host']}")
        print(f"   Base de datos: {DB_EMPRESA_CONFIG['database']}")
        
        # Probar búsqueda de ID_EMPRESA
        nit_test = "1020367024"
        print(f"\n🔍 Buscando ID_EMPRESA para NIT: {nit_test}")
        id_emp = obtener_id_empresa_por_nit(nit_test)
        if id_emp:
            print(f"   ✅ ID_EMPRESA: {id_emp}")
        else:
            print("   ⚠️ No se encontró ID_EMPRESA")
    else:
        print("❌ Error de conexión")