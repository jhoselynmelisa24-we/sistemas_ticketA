from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask import send_file          # ⬅️ AGREGAR
from io import BytesIO               # ⬅️ AGREGAR

import pandas as pd
import os
import json
import secrets
import re
import openpyxl                      # ⬅️ AGREGAR
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side   # ⬅️ AGREGAR
from openpyxl.utils import get_column_letter                             # ⬅️ AGREGAR

from datetime import datetime, timedelta
# ============================================================
# IMPORTS DE BASE DE DATOS
# ============================================================

try:
    from conexion_empresa import obtener_id_empresa_por_nit
    print("✅ conexion_empresa.py importado")
except ImportError as e:
    print(f"⚠️ No se pudo importar conexion_empresa: {e}")
    def obtener_id_empresa_por_nit(nit):
        return None

try:
    from conexion import buscar_empresas
    print("✅ conexion.py importado")
except ImportError as e:
    print(f"⚠️ No se pudo importar conexion: {e}")
    def buscar_empresas(termino, limite=10):
        return []


# ============================================================
# CONFIGURACIÓN
# ============================================================

app = Flask(__name__)

app.secret_key = "sistema_tickets_clave_2026"

CORS(app)
app.config["SESSION_PERMANENT"] = True
app.permanent_session_lifetime = timedelta(days=7)

UPLOAD_FOLDER = "static/uploads"
DATA_FOLDER = "data"
PLANILLAS_FOLDER = os.path.join(DATA_FOLDER, "planillas")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(PLANILLAS_FOLDER, exist_ok=True)


# ============================================================
# CATÁLOGOS
# ============================================================

TIPOS_TRAMITE = {
    173: "CONTRATOS",
    174: "FINIQUITO",
    175: "TRÁMITES"
}

DEPARTAMENTOS = {
    30: "LA PAZ",
    31: "COCHABAMBA",
    32: "SANTA CRUZ"
}
# ============================================================
# FUNCIONARIOS QUE ATIENDEN (Datos de referencia)
# ============================================================
# Se usa para mostrar el nombre de cada funcionario en el sistema.
# El ID_USUARIO se relaciona con dtck_configuracion_usuario.
# ============================================================
# FUNCIONARIOS QUE ATIENDEN
# ============================================================
# La columna final (3) es el ID interno de departamento en la BD.
# Se mapea así:
#   BD 3  →  Santa Cruz (32)
#   BD ?  →  La Paz (30)
#   BD ?  →  Cochabamba (31)

FUNCIONARIOS = {

    # ============================================================
    # LA PAZ (30)
    # ============================================================
    289:  {"ci": "5362946",  "nombre": "Cesar Dereck Vasquez Gutierrez",    "tipos_tramite": [174],     "departamento": 30, "estado": "ACTIVO"},

    # ============================================================
    # COCHABAMBA (31)
    # ============================================================
    1130: {"ci": "5291854",  "nombre": "Cristina Silvia Orellana Cardozo", "tipos_tramite": [173, 174], "departamento": 31, "estado": "ACTIVO"},
    1233: {"ci": "5725232",  "nombre": "Igor Nataniel Bernal Flores",      "tipos_tramite": [173, 174], "departamento": 31, "estado": "INACTIVO"},

    # ============================================================
    # SANTA CRUZ (32)
    # ============================================================
    270:  {"ci": "6318790",  "nombre": "Teufilo Avendaño Tejerina",        "tipos_tramite": [173],     "departamento": 32, "estado": "ACTIVO"},
    1133: {"ci": "5869915",  "nombre": "Katia Aguilar Orellana",           "tipos_tramite": [173],     "departamento": 32, "estado": "ACTIVO"},
    244:  {"ci": "8365847",  "nombre": "Charlie Giovani Huarca Huayhua",   "tipos_tramite": [173],     "departamento": 32, "estado": "ACTIVO"},
    253:  {"ci": "2398637",  "nombre": "Ruth Remy Quisbert Soria",         "tipos_tramite": [174],     "departamento": 32, "estado": "ACTIVO"},
    1102: {"ci": "14021936", "nombre": "Patricia Ivana Guachalla Morales", "tipos_tramite": [174],     "departamento": 32, "estado": "ACTIVO"},
}

# ============================================================
# CORRELATIVO INTERNO DE PLANILLA
# ============================================================

CORRELATIVO_FILE = os.path.join(
    DATA_FOLDER,
    "correlativo_planillas.json"
)


def obtener_siguiente_planilla_id():

    ultimo = 0

    if os.path.exists(CORRELATIVO_FILE):
        try:
            with open(
                CORRELATIVO_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                contenido = json.load(f)

            ultimo = int(contenido.get("ultimo", 0))

        except Exception:
            ultimo = 0

    siguiente = ultimo + 1

    with open(
        CORRELATIVO_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            {"ultimo": siguiente},
            f,
            ensure_ascii=False,
            indent=2
        )

    return f"PLAN-{siguiente:06d}"


# ============================================================
# GENERAR ID_TICKET
# ============================================================

def generar_id_ticket_sistema():

    usados = set()

    if not os.path.exists(PLANILLAS_FOLDER):
        return secrets.randbelow(900000000) + 100000000

    for archivo in os.listdir(PLANILLAS_FOLDER):

        if not archivo.endswith(".json"):
            continue

        ruta = os.path.join(
            PLANILLAS_FOLDER,
            archivo
        )

        try:
            with open(
                ruta,
                "r",
                encoding="utf-8"
            ) as f:
                datos = json.load(f)

            valor = datos.get("id_ticket")

            if valor not in [None, "", "null"]:
                try:
                    usados.add(int(valor))
                except Exception:
                    pass

        except Exception:
            continue

    while True:

        nuevo = secrets.randbelow(900000000) + 100000000

        if nuevo not in usados:
            return nuevo


# ============================================================
# ARCHIVOS DE PLANILLA
# ============================================================

def ruta_planilla(planilla_id):

    return os.path.join(
        PLANILLAS_FOLDER,
        f"{planilla_id}.json"
    )


def guardar_planilla(planilla_id, datos):

    with open(
        ruta_planilla(planilla_id),
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            datos,
            f,
            ensure_ascii=False,
            indent=2
        )


def cargar_planilla(planilla_id=None):

    if planilla_id is None:
        planilla_id = session.get("planilla_id")

    if not planilla_id:
        return None

    ruta = ruta_planilla(planilla_id)

    if not os.path.exists(ruta):
        return None

    try:
        with open(
            ruta,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return None


def actualizar_planilla(datos):

    planilla_id = datos.get("planilla_id")

    if not planilla_id:
        return

    guardar_planilla(
        planilla_id,
        datos
    )


# ============================================================
# UTILIDADES
# ============================================================

def limpiar_valor(valor):

    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor).strip()

    if texto.lower() in [
        "nan",
        "none",
        "nat",
        "n/a",
        "na"
    ]:
        return ""

    if texto.endswith(".0"):

        try:
            numero = float(texto)

            if numero.is_integer():
                texto = str(int(numero))

        except Exception:
            pass

    return texto


def escapar_sql(valor):

    return str(valor or "").replace("'", "''")


def normalizar_nombre_columna(nombre):

    texto = str(nombre or "").strip().upper()

    texto = texto.replace("\n", " ")
    texto = texto.replace("\r", " ")
    texto = texto.replace("\t", " ")

    texto = " ".join(texto.split())

    return texto


def generar_columnas_unicas(columnas):

    resultado = []
    contador = {}

    for columna in columnas:

        nombre = normalizar_nombre_columna(columna)

        if not nombre:
            nombre = "COLUMNA_SIN_NOMBRE"

        if nombre not in contador:

            contador[nombre] = 1
            resultado.append(nombre)

        else:

            contador[nombre] += 1

            resultado.append(
                f"{nombre}_{contador[nombre]}"
            )

    return resultado


# ============================================================
# DETECTAR ENCABEZADO
# ============================================================

def detectar_fila_encabezado(df):

    palabras = [
        "C.I",
        "CI",
        "CARNET",
        "DOCENTE",
        "NOMBRE",
        "APELLIDO",
        "TELEFONO",
        "TELÉFONO",
        "CELULAR",
        "RELACION",
        "RELACIÓN",
        "DIRECCION",
        "DIRECCIÓN",
        "CODIGO PERSONA",
        "CÓDIGO PERSONA",
        "ID_PERSONA",
        "COD_TRAM",
        "COD TRAM",
        "ID_TRAMITE",
        "ID TRAMITE",
        "HORA INICIO",
        "HORA FIN"
    ]

    mejor_fila = 0
    mejor_puntaje = -1

    max_filas = min(len(df), 30)

    for i in range(max_filas):

        valores = [
            normalizar_nombre_columna(v)
            for v in df.iloc[i].tolist()
            if limpiar_valor(v)
        ]

        puntaje = 0

        for valor in valores:

            for palabra in palabras:

                palabra = normalizar_nombre_columna(palabra)

                if (
                    palabra in valor
                    or valor in palabra
                ):
                    puntaje += 1
                    break

        if puntaje > mejor_puntaje:

            mejor_puntaje = puntaje
            mejor_fila = i

    return mejor_fila


# ============================================================
# BUSCAR COLUMNA
# ============================================================

def obtener_columna(fila, posibles):
    """
    1) Busca coincidencia EXACTA (normalizada).
    2) Si no encuentra, busca coincidencia PARCIAL (contains).
    """
    mapa = {}

    for clave in fila.keys():
        normalizada = normalizar_nombre_columna(clave)
        mapa[normalizada] = clave

    # 1 EXACTA
    for posible in posibles:
        normalizada = normalizar_nombre_columna(posible)
        if normalizada in mapa:
            columna = mapa[normalizada]
            valor = limpiar_valor(fila.get(columna, ""))
            if valor:
                return valor

    # 2 PARCIAL
    for posible in posibles:
        normalizada = normalizar_nombre_columna(posible)
        if not normalizada:
            continue
        for clave_norm, clave_orig in mapa.items():
            if normalizada in clave_norm:
                valor = limpiar_valor(fila.get(clave_orig, ""))
                if valor:
                    return valor

    return ""


# ============================================================
# CONSTRUIR TRABAJADOR
# ============================================================

def construir_trabajador(numero, fila_excel):

    trabajador = {
        "nro": numero,
        "excel": fila_excel,
        "id_ticket": None,
        "id_persona": None,
        "codigo_tramite": None,
        "id_tramite": None,
        "hora_inicio": None,
        "hora_fin": None,
        "procesar": False
    }

    # DATOS QUE SE LEEN AUTOMÁTICAMENTE DEL EXCEL
    trabajador["ci"] = obtener_columna(
        fila_excel,
        ["C.I.", "C.I", "CI", "CARNET", "CARNET DE IDENTIDAD"]
    )

    trabajador["expedicion"] = obtener_columna(
        fila_excel,
        ["EXP.", "EXP", "EXPEDICION", "EXPEDICIÓN"]
    )

    trabajador["codexp"] = obtener_columna(
        fila_excel,
        ["CODEXP", "COD EXP", "COD_EXP"]
    )

    trabajador["nombre"] = obtener_columna(
        fila_excel,
        [
            "NOMBRES Y APELLIDOS",
            "NOMBRE Y APELLIDOS",
            "APELLIDOS Y NOMBRES",
            "NOMBRE COMPLETO",
            "NOMBRE_COMPLETO",
            "NOMBRES",
            "NOMBRE"
        ]
    )

    trabajador["telefono"] = obtener_columna(
        fila_excel,
        ["TELEFONO", "TELÉFONO", "CELULAR"]
    )

    trabajador["direccion"] = obtener_columna(
        fila_excel,
        ["DIRECCIÓN", "DIRECCION", "DOMICILIO"]
    )

    trabajador["relacion"] = obtener_columna(
        fila_excel,
        ["RELACIÓN CON LA EMPRESA", "RELACION CON LA EMPRESA", "RELACION", "RELACIÓN"]
    )

    trabajador["cargo"] = trabajador["relacion"]

    return trabajador


# ============================================================
# HORARIOS
# ============================================================

def convertir_hora(hora_str):

    if not hora_str:
        return datetime.strptime(
            "08:30:00",
            "%H:%M:%S"
        )

    texto = str(hora_str).strip()

    for formato in [
        "%H:%M:%S",
        "%H:%M"
    ]:

        try:
            return datetime.strptime(
                texto,
                formato
            )
        except Exception:
            pass

    return datetime.strptime(
        "08:30:00",
        "%H:%M:%S"
    )


def sumar_minutos(hora_str, minutos):

    hora = convertir_hora(hora_str)

    nueva = hora + timedelta(
        minutes=int(minutos)
    )

    return nueva.strftime("%H:%M:%S")


# ============================================================
# TRABAJADORES DEL BLOQUE ACTUAL
# ============================================================

def trabajadores_actuales():

    datos = cargar_planilla()

    if not datos:
        return []

    trabajadores = datos.get(
        "trabajadores",
        []
    )

    desde = int(
        datos.get(
            "desde_trabajador",
            1
        )
    )

    hasta = int(
        datos.get(
            "hasta_trabajador",
            0
        )
    )

    return [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]


# ============================================================
# PANTALLAS
# ============================================================

@app.route("/")
def index():

    return render_template(
        "pantalla1_carga.html",
        step=1,
        tipos_tramite=TIPOS_TRAMITE,
        departamentos=DEPARTAMENTOS
    )


@app.route("/tipo")
def tipo():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=2
        )

    return render_template(
        "pantalla2_tipo.html",
        step=2
    )


@app.route("/continuar")
def continuar():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=3
        )

    return render_template(
        "pantalla3_continuar.html",
        step=3
    )


@app.route("/ticket")
def ticket():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=4
        )

    return render_template(
        "pantalla4_ticket.html",
        step=4,
        tipos_tramite=TIPOS_TRAMITE,
        departamentos=DEPARTAMENTOS
    )


@app.route("/persona")
def persona():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=5
        )

    return render_template(
        "pantalla5_persona.html",
        step=5
    )


@app.route("/codigo")
def codigo():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=6
        )

    return render_template(
        "pantalla6_codigo.html",
        step=6
    )


@app.route("/idtramite")
def idtramite():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=7
        )

    return render_template(
        "pantalla7_idtramite.html",
        step=7
    )


@app.route("/script")
def script():

    if not session.get("planilla_id"):

        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=8
        )

    return render_template(
        "pantalla8_script.html",
        step=8
    )


# ============================================================
# PASO 1 - CARGAR EXCEL
# ============================================================

@app.route(
    "/api/upload",
    methods=["POST"]
)
def upload_excel():

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "error": "No se seleccionó archivo."
        }), 400

    file = request.files["file"]

    if not file.filename:

        return jsonify({
            "success": False,
            "error": "El archivo no tiene nombre."
        }), 400

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    if extension not in [".xlsx", ".xls"]:

        return jsonify({
            "success": False,
            "error": "Use un archivo Excel .xlsx o .xls."
        }), 400

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    try:

        file.save(filepath)

        df_raw = pd.read_excel(
            filepath,
            header=None,
            dtype=str,
            keep_default_na=False
        )

        if df_raw.empty:

            return jsonify({
                "success": False,
                "error": "El Excel está vacío."
            }), 400

        fila_encabezado = detectar_fila_encabezado(
            df_raw
        )

        encabezados = [
            limpiar_valor(v)
            for v in df_raw.iloc[
                fila_encabezado
            ].tolist()
        ]

        encabezados = generar_columnas_unicas(
            encabezados
        )

        df = df_raw.iloc[
            fila_encabezado + 1:
        ].copy()

        df.columns = encabezados

        df = df.reset_index(drop=True)

        df = df[
            df.apply(
                lambda fila: any(
                    limpiar_valor(v) != ""
                    for v in fila
                ),
                axis=1
            )
        ]

        df = df.reset_index(drop=True)

        trabajadores = []
        filas_excel = []

        for indice, fila in df.iterrows():

            fila_excel = {}

            for columna in df.columns:

                fila_excel[columna] = limpiar_valor(
                    fila[columna]
                )

            trabajador = construir_trabajador(
                indice + 1,
                fila_excel
            )

            trabajadores.append(
                trabajador
            )

            filas_excel.append(
                fila_excel
            )

        if not trabajadores:

            return jsonify({
                "success": False,
                "error": "No se encontraron trabajadores."
            }), 400

        planilla_id = obtener_siguiente_planilla_id()

        datos = {

            "planilla_id": planilla_id,

            "archivo_nombre": file.filename,

            "fecha_carga":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "fila_encabezado":
                fila_encabezado + 1,

            "columnas_excel":
                list(df.columns),

            "filas_excel":
                filas_excel,

            "trabajadores":
                trabajadores,

            "total_trabajadores":
                len(trabajadores),

            # BLOQUE ACTUAL
            "cantidad_procesar": 0,
            "desde_trabajador": 1,
            "hasta_trabajador": 0,

            # TIPO
            "tipo_proceso": None,

            # EMPRESA
            "empresa": "",
            "nit": "",
            "id_empresa": None,
            "usuario_creacion": None,

            # TICKET
            "id_ticket": None,
            "codigo_ticket": None,
            "tipo_tramite": None,
            "departamento": None,
            "fecha": None,
            "hora_base": None,
            "hora_fin": None
        }

        guardar_planilla(
            planilla_id,
            datos
        )

        session.clear()
        session["planilla_id"] = planilla_id
        session.modified = True

        try:
            os.remove(filepath)
        except Exception:
            pass

        return jsonify({

            "success": True,

            "planilla_id":
                planilla_id,

            "archivo":
                file.filename,

            "total":
                len(trabajadores),

            "fila_encabezado":
                fila_encabezado + 1,

            "columnas":
                list(df.columns),

            "filas":
                filas_excel,

            "trabajadores":
                trabajadores,

            "empresa": "",
            "nit": ""
        })

    except Exception as e:

        import traceback
        traceback.print_exc()

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

        return jsonify({
            "success": False,
            "error": f"Error al leer Excel: {str(e)}"
        }), 500


# ============================================================
# PASO 2 - CANTIDAD
# ============================================================

@app.route(
    "/api/configurar_cantidad",
    methods=["POST"]
)
def configurar_cantidad():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(
        silent=True
    ) or {}

    valor = data.get(
        "cantidad_procesar",
        data.get("cantidad", 0)
    )

    try:
        cantidad = int(valor)
    except Exception:

        return jsonify({
            "success": False,
            "error": "La cantidad debe ser un número entero."
        }), 400

    total = len(
        datos.get("trabajadores", [])
    )

    if cantidad <= 0:

        return jsonify({
            "success": False,
            "error": "La cantidad debe ser mayor que cero."
        }), 400

    if cantidad > total:

        return jsonify({
            "success": False,
            "error":
                f"La planilla contiene {total} trabajadores."
        }), 400

    desde = int(
        datos.get(
            "desde_trabajador",
            1
        )
    )

    hasta = min(
        desde + cantidad - 1,
        total
    )

    datos["cantidad_procesar"] = (
        hasta - desde + 1
    )

    datos["hasta_trabajador"] = hasta

    actualizar_planilla(datos)

    return jsonify({

        "success": True,

        "planilla_id":
            datos["planilla_id"],

        "total":
            total,

        "cantidad_procesar":
            datos["cantidad_procesar"],

        "desde":
            desde,

        "hasta":
            hasta,

        "pendientes":
            total - hasta
    })


# ============================================================
# PASO 3 - TIPO DE PLANILLA
# ============================================================

@app.route(
    "/api/tipo",
    methods=["POST"]
)
def set_tipo():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(
        silent=True
    ) or {}

    tipo = str(
        data.get(
            "tipo",
            data.get("tipo_planilla", "")
        )
    ).strip().upper()

    equivalencias = {
        "CONTINUACIÓN": "CONTINUACION",
        "CONTINUACION": "CONTINUACION",
        "NUEVA": "NUEVA",
        "RECIENTE": "RECIENTE"
    }

    tipo = equivalencias.get(
        tipo,
        tipo
    )

    if tipo not in [
        "NUEVA",
        "RECIENTE",
        "CONTINUACION"
    ]:

        return jsonify({
            "success": False,
            "error": "Tipo de planilla inválido."
        }), 400

    datos["tipo_proceso"] = tipo

    actualizar_planilla(datos)

    return jsonify({

        "success": True,

        "tipo":
            tipo,

        "planilla_id":
            datos["planilla_id"]
    })


# ============================================================
# BUSCADOR DE EMPRESAS
# ============================================================

@app.route("/api/empresa/buscar", methods=["GET"])
def api_buscar_empresa():
    """
    Busca empresas por NIT o nombre.
    """
    termino = (request.args.get("termino") or "").strip()

    if len(termino) < 3:
        return jsonify({
            "success": False,
            "error": "Ingrese al menos 3 caracteres."
        }), 400

    empresas = []

    try:
        resultados = buscar_empresas(termino, limite=10) or []

        for emp in resultados:
            nit_empresa = str(emp.get("nit") or "").strip()

            id_empresa_real = None
            id_usuario = None

            if nit_empresa:
                try:
                    from conexion_empresa import obtener_id_empresa_por_nit
                    id_empresa_real = obtener_id_empresa_por_nit(nit_empresa)
                except Exception as e:
                    print(f"⚠️ Error id_empresa para NIT {nit_empresa}: {e}")

                try:
                    from conexion import buscar_usuario_por_login
                    usuario = buscar_usuario_por_login(nit_empresa)
                    if usuario:
                        id_usuario = usuario.get("id_usuario")
                except Exception as e:
                    print(f"⚠️ Error usuario para NIT {nit_empresa}: {e}")

            empresas.append({
                "id_empresa": id_empresa_real,
                "id_usuario": id_usuario,
                "nit": nit_empresa,
                "razon_social": str(emp.get("razon_social") or ""),
                "estado": str(emp.get("estado") or "V"),
            })

    except Exception as e:
        print(f"⚠️ Error buscar_empresas: {e}")

    return jsonify({
        "success": True,
        "total": len(empresas),
        "empresas": empresas,
        "resultados": empresas,
    })
@app.route("/api/guardar_id_empresa", methods=["POST"])
def api_guardar_id_empresa():
    """
    Guarda el id_empresa seleccionado en la planilla actual.
    """
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}

    id_empresa = data.get("id_empresa")
    nit = str(data.get("nit", "")).strip()
    razon_social = str(data.get("razon_social", "")).strip()
    id_usuario = data.get("id_usuario")

    if not id_empresa and nit:
        try:
            id_empresa = obtener_id_empresa_por_nit(nit)
        except Exception:
            pass

    if id_empresa is not None:
        datos["id_empresa"] = id_empresa
    if nit:
        datos["nit"] = nit
    if razon_social:
        datos["empresa"] = razon_social
        # ⚠️ NO sobrescribir usuario_creacion si ya hay funcionario guardado
    if id_usuario is not None and not datos.get("id_funcionario"):
        datos["usuario_creacion"] = id_usuario

    actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "id_empresa": datos.get("id_empresa"),
        "nit": datos.get("nit"),
        "razon_social": datos.get("empresa"),
        "empresa": datos.get("empresa"),
        "usuario_creacion": datos.get("usuario_creacion"),
        "id_funcionario": datos.get("id_funcionario"),
        "codigo_ticket": datos.get("codigo_ticket"),
    })
# ============================================================
# PASO 4 - CONFIGURACIÓN DEL TICKET
# ============================================================

@app.route(
    "/api/configurar_ticket",
    methods=["POST"]
)
def configurar_ticket():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(
        silent=True
    ) or {}

    codigo = (
        data.get("codigo")
        or data.get("codigo_ticket")
        or datos.get("codigo_ticket")
        or "RF-001"
    )

    fecha = (
        data.get("fecha")
        or datos.get("fecha")
        or datetime.now().strftime("%Y-%m-%d")
    )

    hora_inicio = (
        data.get("hora_inicio")
        or data.get("hora_base")
        or "08:30:00"
    )

    # La hora_fin se calculará más abajo según la cantidad
    hora_fin = data.get("hora_fin") or datos.get("hora_fin") or None

    razon_social = (
        data.get("razon_social")
        or data.get("empresa")
        or ""
    )

    nit = str(
        data.get("nit", "")
    ).strip()

    # TIPO TRÁMITE - Sin defaults
    tipo_tramite = data.get("tipo_tramite")
    if tipo_tramite is None:
        tipo_tramite = datos.get("tipo_tramite")
    
    if tipo_tramite is None:
        return jsonify({
            "success": False,
            "error": "Debe seleccionar un tipo de trámite."
        }), 400
    
    try:
        tipo_tramite = int(tipo_tramite)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Tipo de trámite inválido."
        }), 400
    
    if tipo_tramite not in TIPOS_TRAMITE:
        return jsonify({
            "success": False,
            "error": f"Tipo de trámite {tipo_tramite} no reconocido."
        }), 400
    
    # DEPARTAMENTO - Sin defaults
    departamento = data.get("departamento")
    if departamento is None:
        departamento = datos.get("departamento")
    
    if departamento is None:
        return jsonify({
            "success": False,
            "error": "Debe seleccionar un departamento."
        }), 400
    
    try:
        departamento = int(departamento)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Departamento inválido."
        }), 400
    
    if departamento not in DEPARTAMENTOS:
        return jsonify({
            "success": False,
            "error": f"Departamento {departamento} no reconocido."
        }), 400
    
    cantidad = data.get(
        "cantidad_trabajadores",
        data.get(
            "cantidad",
            datos.get(
                "cantidad_procesar",
                0
            )
        )
    )

    try:
        cantidad = int(cantidad)
    except Exception:
        cantidad = int(
            datos.get(
                "cantidad_procesar",
                0
            )
        )

    if cantidad <= 0:

        return jsonify({
            "success": False,
            "error":
                "Debe indicar una cantidad de trabajadores."
        }), 400

    total = len(
        datos.get("trabajadores", [])
    )

    desde = int(
        datos.get(
            "desde_trabajador",
            1
        )
    )

    hasta = min(
        desde + cantidad - 1,
        total
    )

    # ============================================================
    # CALCULAR HORA FIN SI NO VIENE
    # ============================================================
    cantidad_real = hasta - desde + 1
    if not hora_fin:
        minutos_totales = (cantidad_real -1)* 4 +3
        hora_fin = sumar_minutos(hora_inicio, minutos_totales)

    datos["codigo_ticket"] = str(codigo)
    datos["fecha"] = str(fecha)
    datos["hora_base"] = str(hora_inicio)
    datos["hora_fin"] = str(hora_fin)

    datos["empresa"] = razon_social
    datos["nit"] = nit

    datos["tipo_tramite"] = tipo_tramite
    datos["departamento"] = departamento

    datos["cantidad_procesar"] = cantidad_real

    datos["hasta_trabajador"] = hasta

    actualizar_planilla(datos)

    return jsonify({

        "success": True,

        "codigo":
            str(codigo),

        "fecha":
            str(fecha),

        "hora_inicio":
            str(hora_inicio),

        "hora_fin":
            str(hora_fin),

        "cantidad":
            datos["cantidad_procesar"],

        "empresa":
            razon_social,

        "razon_social":
            razon_social,

        "nit":
            nit,

        "tipo_tramite":
            tipo_tramite,

        "departamento":
            departamento
    })


# ============================================================
# PASO 4 - GENERAR ID_TICKET
# ============================================================

@app.route(
    "/api/generar_ticket",
    methods=["POST"]
)
def generar_ticket():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get(
        "trabajadores",
        []
    )

    if not trabajadores:

        return jsonify({
            "success": False,
            "error": "No existen trabajadores cargados."
        }), 400

    data = request.get_json(
        silent=True
    ) or {}

    # EL ID_TICKET LO GENERA EL SISTEMA
    id_ticket = datos.get("id_ticket")

    enviado = data.get("id_ticket")

    if enviado not in [None, "", "null", "undefined"]:
        try:
            id_ticket = int(enviado)
        except Exception:
            pass

    if id_ticket is None:
        id_ticket = generar_id_ticket_sistema()

    # DATOS
    codigo = (
        data.get("codigo")
        or data.get("codigo_ticket")
        or datos.get("codigo_ticket")
        or "RF-001"
    )

    fecha = (
        data.get("fecha")
        or datos.get("fecha")
        or datetime.now().strftime("%Y-%m-%d")
    )

    hora_inicio = (
        data.get("hora_inicio")
        or data.get("hora_base")
        or "08:30:00"
    )

    # La hora_fin se calcula más abajo según la cantidad
    hora_fin = data.get("hora_fin") or datos.get("hora_fin") or None

    # TIPO TRÁMITE - Sin defaults
    tipo_tramite = data.get("tipo_tramite")
    if tipo_tramite is None:
        tipo_tramite = datos.get("tipo_tramite")
    
    if tipo_tramite is None:
        return jsonify({
            "success": False,
            "error": "Debe seleccionar un tipo de trámite."
        }), 400
    
    try:
        tipo_tramite = int(tipo_tramite)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Tipo de trámite inválido."
        }), 400
    
    if tipo_tramite not in TIPOS_TRAMITE:
        return jsonify({
            "success": False,
            "error": f"Tipo de trámite {tipo_tramite} no reconocido."
        }), 400
    
    # DEPARTAMENTO - Sin defaults
    departamento = data.get("departamento")
    if departamento is None:
        departamento = datos.get("departamento")
    
    if departamento is None:
        return jsonify({
            "success": False,
            "error": "Debe seleccionar un departamento."
        }), 400
    
    try:
        departamento = int(departamento)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Departamento inválido."
        }), 400
    
    if departamento not in DEPARTAMENTOS:
        return jsonify({
            "success": False,
            "error": f"Departamento {departamento} no reconocido."
        }), 400

    razon_social = datos.get("empresa", "")
    nit = datos.get("nit", "")

    # USUARIO CREACIÓN - Sin defaults
    usuario_creacion = data.get("usuario_creacion")
    if usuario_creacion is None:
        usuario_creacion = datos.get("usuario_creacion")
    
    if usuario_creacion is None:
        return jsonify({
            "success": False,
            "error": "Debe indicar el usuario de creación."
        }), 400
    
    try:
        usuario_creacion = int(usuario_creacion)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Usuario de creación inválido."
        }), 400

    cantidad = data.get("cantidad_procesar")

    if cantidad in [None, "", "null", "undefined"]:
        cantidad = data.get("cantidad_trabajadores")

    if cantidad in [None, "", "null", "undefined"]:
        cantidad = datos.get("cantidad_procesar", 0)

    try:
        cantidad = int(cantidad)
    except Exception:

        return jsonify({
            "success": False,
            "error":
                "La cantidad de trabajadores no es válida."
        }), 400

    if cantidad <= 0:

        return jsonify({
            "success": False,
            "error":
                "Primero debe indicar la cantidad de trabajadores a procesar."
        }), 400

    total = len(trabajadores)

    desde = int(datos.get("desde_trabajador", 1))

    if desde < 1:
        desde = 1

    if desde > total:

        return jsonify({
            "success": False,
            "error":
                "El trabajador inicial está fuera del rango."
        }), 400

    hasta = min(desde + cantidad - 1, total)

    cantidad_real = hasta - desde + 1

    # ============================================================
    # CALCULAR HORA FIN SI NO VIENE
    # ============================================================
    if not hora_fin:
        minutos_totales = (cantidad_real - 1) * 4 + 3
        hora_fin = sumar_minutos(hora_inicio, minutos_totales)

    # ASIGNAR EL MISMO ID_TICKET A TODOS
    for trabajador in trabajadores:

        nro = int(trabajador.get("nro", 0))

        if desde <= nro <= hasta:

            trabajador["id_ticket"] = id_ticket
            trabajador["procesar"] = True

            indice = nro - desde

            inicio = sumar_minutos(hora_inicio, indice * 4)
            fin = sumar_minutos(inicio, 3)

            trabajador["hora_inicio"] = inicio
            trabajador["hora_fin"] = fin

    # GUARDAR
    datos["trabajadores"] = trabajadores
    datos["id_ticket"] = id_ticket
    datos["codigo_ticket"] = str(codigo)
    datos["fecha"] = str(fecha)
    datos["hora_base"] = str(hora_inicio)
    datos["hora_fin"] = str(hora_fin)
    datos["departamento"] = departamento
    datos["tipo_tramite"] = tipo_tramite
    datos["cantidad_procesar"] = cantidad_real
    datos["hasta_trabajador"] = hasta
    datos["usuario_creacion"] = usuario_creacion

    actualizar_planilla(datos)

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    script = generar_script_ticket(
        procesados,
        id_ticket,
        codigo,
        fecha,
        departamento,
        tipo_tramite,
        hora_inicio,
        hora_fin,
        razon_social,
        nit,
        usuario_creacion
    )

    return jsonify({

        "success": True,

        "planilla_id":
            datos["planilla_id"],

        "id_ticket":
            id_ticket,

        "codigo":
            codigo,

        "desde":
            desde,

        "hasta":
            hasta,

        "cantidad_procesar":
            len(procesados),

        "cantidad":
            len(procesados),

        "total":
            len(procesados),

        "trabajadores":
            trabajadores,

        "procesados":
            procesados,

        "script":
            script,

        "script_ticket":
            script,

        "script_completo":
            script,

        "razon_social": razon_social,

        "empresa": razon_social,

        "nit": nit,

        "mensaje": f"Ticket generado correctamente para {len(procesados)} trabajadores.",

        "hora_inicio": hora_inicio,

        "hora_fin": hora_fin
    })


# ============================================================
# PASO 5 - REGISTRAR ID_PERSONA
# ============================================================

@app.route(
    "/api/registrar_personas",
    methods=["POST"]
)
def registrar_personas():

    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])

    data = request.get_json(silent=True) or {}

    primer_id = data.get("primer_id_persona")

    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    if primer_id is None or primer_id == "":
        return jsonify({
            "success": False,
            "error": "Debe ingresar el primer ID_PERSONA."
        }), 400

    try:
        primer_id = int(primer_id)
    except Exception:
        return jsonify({
            "success": False,
            "error": "El ID_PERSONA debe ser un número válido."
        }), 400

    registrados = 0
    idx = 0

    for trabajador in trabajadores:
        nro = int(trabajador.get("nro", 0))

        if desde <= nro <= hasta:
            trabajador["id_persona"] = primer_id + idx
            registrados += 1
            idx += 1

    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    script_completo = generar_script_completo(procesados)

    return jsonify({
        "success": True,
        "registrados": registrados,
        "procesados": procesados,
        "trabajadores": trabajadores,
        "mensaje": f"Se registraron {registrados} ID_PERSONA correlativos (desde {primer_id} hasta {primer_id + registrados - 1}).",
        "script_completo": script_completo
    })

# ============================================================
# PASO 5 - GENERAR SCRIPT DE PERSONAS (endpoint del HTML)
# ============================================================
@app.route("/api/generar_personas", methods=["POST"])
def generar_personas_endpoint():
    """
    Endpoint que usa pantalla5_persona.html
    Devuelve el script de personas.
    """
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    if not procesados:
        return jsonify({
            "success": False,
            "error": "No hay trabajadores en el bloque actual."
        }), 400

    # ⚠️ SIN fallback 1155
    usuario_creacion = datos.get("usuario_creacion")

    if usuario_creacion is None:
        return jsonify({
            "success": False,
            "error": "Falta usuario_creacion. Seleccione empresa y funcionario primero."
        }), 400

    # Generar script de personas
    script = generar_script_personas(procesados, usuario_creacion)

    return jsonify({
        "success": True,
        "total": len(procesados),
        "script": script,
        "script_completo": script,
        "trabajadores": procesados,
        "id_ticket": datos.get("id_ticket"),
        "usuario_creacion": usuario_creacion,
        "id_funcionario": datos.get("id_funcionario")
    })
# ============================================================
# PASO 6 - REGISTRAR COD_TRAM
# ============================================================

@app.route(
    "/api/registrar_codigos",
    methods=["POST"]
)
def registrar_codigos():

    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])

    data = request.get_json(silent=True) or {}

    primer_codigo = data.get("primer_cod_tram")

    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    if primer_codigo is None or primer_codigo == "":
        return jsonify({
            "success": False,
            "error": "Debe ingresar el primer COD_TRAM."
        }), 400

    codigo_str = str(primer_codigo).strip()

    match = re.search(r'(\D*)(\d+)$', codigo_str)

    if match:
        prefijo = match.group(1)
        numero_inicial = int(match.group(2))
    else:
        prefijo = codigo_str + "-"
        numero_inicial = 1

    registrados = 0
    idx = 0

    for trabajador in trabajadores:
        nro = int(trabajador.get("nro", 0))

        if desde <= nro <= hasta:
            numero_actual = numero_inicial + idx
            numero_formateado = str(numero_actual).zfill(3)
            trabajador["codigo_tramite"] = f"{prefijo}{numero_formateado}"
            registrados += 1
            idx += 1

    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    script_completo = generar_script_completo(procesados)

    return jsonify({
        "success": True,
        "registrados": registrados,
        "procesados": procesados,
        "trabajadores": trabajadores,
        "mensaje": f"Se registraron {registrados} COD_TRAM correlativos (desde {primer_codigo} hasta {prefijo}{str(numero_inicial + registrados - 1).zfill(3)}).",
        "script_completo": script_completo
    })


# ============================================================
# PASO 7 - REGISTRAR ID_TRAMITE
# ============================================================

@app.route(
    "/api/registrar_idtramites",
    methods=["POST"]
)
def registrar_idtramites():

    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])

    data = request.get_json(silent=True) or {}

    primer_id = data.get("primer_id_tramite")

    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    if primer_id is None or primer_id == "":
        return jsonify({
            "success": False,
            "error": "Debe ingresar el primer ID_TRAMITE."
        }), 400

    try:
        primer_id = int(primer_id)
    except Exception:
        return jsonify({
            "success": False,
            "error": "El ID_TRAMITE debe ser un número válido."
        }), 400

    registrados = 0
    idx = 0

    for trabajador in trabajadores:
        nro = int(trabajador.get("nro", 0))

        if desde <= nro <= hasta:
            trabajador["id_tramite"] = primer_id + idx
            registrados += 1
            idx += 1

    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    script_completo = generar_script_completo(procesados)

    return jsonify({
        "success": True,
        "registrados": registrados,
        "procesados": procesados,
        "trabajadores": trabajadores,
        "mensaje": f"Se registraron {registrados} ID_TRAMITE correlativos (desde {primer_id} hasta {primer_id + registrados - 1}).",
        "script_completo": script_completo
    })


# ============================================================
# PREVISUALIZACIÓN COMPLETA
# ============================================================

@app.route(
    "/api/previsualizacion_completa",
    methods=["GET"]
)
def previsualizacion_completa():

    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])

    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    script_completo = generar_script_completo(procesados)

    tiene_id_persona = any(t.get("id_persona") for t in procesados)
    tiene_cod_tram = any(t.get("codigo_tramite") for t in procesados)
    tiene_id_tramite = any(t.get("id_tramite") for t in procesados)

    return jsonify({
        "success": True,
        "procesados": procesados,
        "script_completo": script_completo,
        "script": script_completo,
        "script_ticket": script_completo,
        "estado": {
            "id_persona": tiene_id_persona,
            "cod_tram": tiene_cod_tram,
            "id_tramite": tiene_id_tramite
        },
        "total": len(procesados),
        "cantidad": len(procesados),
        "cantidad_procesar": len(procesados),
        "tiene_id_persona": tiene_id_persona,
        "tiene_cod_tram": tiene_cod_tram,
        "tiene_id_tramite": tiene_id_tramite,
        "razon_social": datos.get("empresa", ""),
        "empresa": datos.get("empresa", ""),
        "nit": datos.get("nit", ""),
        "id_ticket": datos.get("id_ticket"),
        "hora_inicio": datos.get("hora_base", "08:30:00"),
        "hora_fin": datos.get("hora_fin")
    })


# ============================================================
# PREVISUALIZACIÓN
# ============================================================

@app.route(
    "/api/previsualizacion",
    methods=["GET"]
)
def previsualizacion():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])

    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    pendientes = [
        t for t in trabajadores
        if int(t.get("nro", 0)) > hasta
    ]

    return jsonify({

        "success": True,

        "planilla_id":
            datos.get("planilla_id"),

        "archivo":
            datos.get("archivo_nombre"),

        "columnas":
            datos.get("columnas_excel", []),

        "filas":
            datos.get("filas_excel", []),

        "todos":
            trabajadores,

        "procesados":
            procesados,

        "pendientes":
            pendientes,

        "total":
            len(trabajadores),

        "cantidad_procesada":
            len(procesados),

        "cantidad_pendiente":
            len(pendientes),

        "desde":
            desde,

        "hasta":
            hasta,

        "id_ticket":
            datos.get("id_ticket"),

        "razon_social": datos.get("empresa", ""),
        "nit": datos.get("nit", "")
    })


# ============================================================
# ESTADO
# ============================================================
@app.route(
    "/api/estado",
    methods=["GET"]
)
def estado():

    datos = cargar_planilla()

    # ⭐ Si no hay planilla en sesión, cargar la última creada
    if not datos:
        try:
            archivos = [
                f for f in os.listdir(PLANILLAS_FOLDER)
                if f.startswith("PLAN-") and f.endswith(".json")
            ]
            if archivos:
                # Ordenar por fecha de modificación (más reciente primero)
                archivos.sort(
                    key=lambda x: os.path.getmtime(
                        os.path.join(PLANILLAS_FOLDER, x)
                    ),
                    reverse=True
                )
                ultima_planilla = archivos[0].replace(".json", "")
                datos = cargar_planilla(ultima_planilla)

                if datos:
                    session["planilla_id"] = ultima_planilla
        except Exception as e:
            print(f"⚠️ Error cargando última planilla: {e}")

    if not datos:
        return jsonify({
            "success": True,
            "planilla_id": None,
            "total": 0,
            "cantidad_procesar": 0,
            "pendientes": 0,
            "id_ticket": None,
            "trabajadores": []
        })

    trabajadores = datos.get("trabajadores", [])
    ...

    trabajadores = datos.get("trabajadores", [])

    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    pendientes = [
        t for t in trabajadores
        if int(t.get("nro", 0)) > hasta
    ]

    return jsonify({

        "success": True,

        "planilla_id":
            datos.get("planilla_id"),

        "archivo":
            datos.get("archivo_nombre"),

        "total":
            len(trabajadores),

        "cantidad_procesar":
            len(procesados),

        "pendientes":
            len(pendientes),

        "desde":
            desde,

        "hasta":
            hasta,

        "id_ticket":
            datos.get("id_ticket"),

        "tipo":
            datos.get("tipo_proceso"),

        "empresa":
            datos.get("empresa"),

        "razon_social":
            datos.get("empresa"),

        "nit":
            datos.get("nit"),

        "id_empresa":
            datos.get("id_empresa"),

                "usuario_creacion":
            datos.get("usuario_creacion"),

        "id_funcionario":                  # ⬅️ AGREGA
            datos.get("id_funcionario"),   # ⬅️ AGREGA

        "codigo_ticket":
            datos.get("codigo_ticket"),

        "codigo_ticket":
            datos.get("codigo_ticket"),

        "fecha":
            datos.get("fecha"),

        "hora_inicio":
            datos.get("hora_base"),

        "hora_fin":
            datos.get("hora_fin"),

        "tipo_tramite":
            datos.get("tipo_tramite"),

        "tipo_tramite_nombre":
            TIPOS_TRAMITE.get(datos.get("tipo_tramite"), "Desconocido"),

        "departamento":
            datos.get("departamento"),

        "departamento_nombre":
            DEPARTAMENTOS.get(datos.get("departamento"), "Desconocido"),

        "columnas":
            datos.get("columnas_excel", []),

        "filas":
            datos.get("filas_excel", []),

        "trabajadores":
            trabajadores,

        "procesados":
            procesados,

        "pendientes_lista":
            pendientes
    })


# ============================================================
# CONTINUAR PROCESO
# ============================================================

@app.route(
    "/api/continuar_proceso",
    methods=["POST"]
)
def continuar_proceso():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])

    total = len(trabajadores)

    hasta_actual = int(datos.get("hasta_trabajador", 0))

    if hasta_actual >= total:

        return jsonify({

            "success": False,

            "terminado": True,

            "mensaje":
                "No quedan trabajadores pendientes."
        })

    nuevo_desde = hasta_actual + 1

    data = request.get_json(silent=True) or {}

    cantidad = data.get("cantidad_procesar", data.get("cantidad"))

    if cantidad is None:
        cantidad = total - nuevo_desde + 1

    try:
        cantidad = int(cantidad)
    except Exception:

        return jsonify({
            "success": False,
            "error": "Cantidad inválida."
        }), 400

    if cantidad <= 0:

        return jsonify({
            "success": False,
            "error":
                "La cantidad debe ser mayor que cero."
        }), 400

    nuevo_hasta = min(nuevo_desde + cantidad - 1, total)

    datos["desde_trabajador"] = nuevo_desde

    datos["cantidad_procesar"] = (
        nuevo_hasta
        - nuevo_desde
        + 1
    )

    datos["hasta_trabajador"] = nuevo_hasta

    datos["id_ticket"] = None

    for trabajador in trabajadores:

        nro = int(trabajador.get("nro", 0))

        if nuevo_desde <= nro <= nuevo_hasta:

            trabajador["id_ticket"] = None
            trabajador["id_persona"] = None
            trabajador["codigo_tramite"] = None
            trabajador["id_tramite"] = None
            trabajador["hora_inicio"] = None
            trabajador["hora_fin"] = None
            trabajador["procesar"] = False

    datos["trabajadores"] = trabajadores

    actualizar_planilla(datos)

    return jsonify({

        "success": True,

        "planilla_id":
            datos["planilla_id"],

        "desde":
            nuevo_desde,

        "hasta":
            nuevo_hasta,

        "cantidad_procesar":
            nuevo_hasta
            - nuevo_desde
            + 1,

        "pendientes":
            total
            - nuevo_hasta,

        "id_ticket":
            None,

        "trabajadores":
            trabajadores
    })


# ============================================================
# GUARDAR AVANCE
# ============================================================

@app.route(
    "/api/guardar_avance",
    methods=["POST"]
)
def guardar_avance():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    total = len(datos.get("trabajadores", []))

    hasta = int(datos.get("hasta_trabajador", 0))

    registro = {

        "planilla_id":
            datos.get("planilla_id"),

        "archivo":
            datos.get("archivo_nombre"),

        "fecha":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "total":
            total,

        "procesados":
            hasta,

        "pendientes":
            max(total - hasta, 0),

        "id_ticket":
            datos.get("id_ticket")
    }

    archivo = os.path.join(
        DATA_FOLDER,
        "session_data.json"
    )

    historial = []

    if os.path.exists(archivo):

        try:

            with open(
                archivo,
                "r",
                encoding="utf-8"
            ) as f:
                historial = json.load(f)

            if not isinstance(
                historial,
                list
            ):
                historial = [historial]

        except Exception:
            historial = []

    historial.append(registro)

    with open(
        archivo,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            historial,
            f,
            ensure_ascii=False,
            indent=2
        )

    return jsonify({

        "success": True,

        "registro":
            registro
    })


# ============================================================
# HISTORIAL
# ============================================================

@app.route(
    "/api/historial",
    methods=["GET"]
)
def historial():

    archivo = os.path.join(
        DATA_FOLDER,
        "session_data.json"
    )

    if not os.path.exists(archivo):

        return jsonify({

            "success": True,

            "historial": []
        })

    try:

        with open(
            archivo,
            "r",
            encoding="utf-8"
        ) as f:

            datos = json.load(f)

        if not isinstance(datos, list):
            datos = [datos]

        return jsonify({

            "success": True,

            "historial":
                datos
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)
        }), 500


# ============================================================
# USUARIOS FILTRADOS POR DEPARTAMENTO Y TIPO DE TRÁMITE
# ============================================================


@app.route("/api/usuarios_filtrados", methods=["GET"])
def api_usuarios_filtrados():
    """
    Devuelve funcionarios filtrados por departamento y tipo de trámite.
    Usa el diccionario FUNCIONARIOS para mostrar el nombre.
    """
    id_departamento = request.args.get("id_departamento")
    id_tipo_tramite = request.args.get("id_tipo_tramite")

    if not id_departamento or not id_tipo_tramite:
        return jsonify({
            "success": False,
            "error": "Faltan parámetros id_departamento o id_tipo_tramite."
        }), 400

    try:
        id_departamento = int(id_departamento)
        id_tipo_tramite = int(id_tipo_tramite)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Parámetros inválidos."
        }), 400

    usuarios = []

    # Recorrer el diccionario de funcionarios
    for id_usuario, datos_func in FUNCIONARIOS.items():

        # Filtrar por estado
        if datos_func.get("estado") != "ACTIVO":
            continue

        # Filtrar por departamento
        if datos_func.get("departamento") != id_departamento:
            continue

        # Filtrar por tipo de trámite
        tipos = datos_func.get("tipos_tramite", [])
        if id_tipo_tramite not in tipos:
            continue

        usuarios.append({
            "id": id_usuario,
            "nombre": datos_func.get("nombre", ""),
            "ci": datos_func.get("ci", ""),
            "login": str(id_usuario),
            "tipo_tramite": tipos,
            "estado": datos_func.get("estado", "ACTIVO"),
            "departamento": datos_func.get("departamento"),
            "puesto": "",
            "unidad_area": ""
        })

    # Ordenar por nombre
    usuarios.sort(key=lambda u: u["nombre"])

    return jsonify({
        "success": True,
        "total": len(usuarios),
        "usuarios": usuarios
    })

# ============================================================
# GUARDAR FUNCIONARIO EN LA PLANILLA
# ============================================================
# ============================================================
# GUARDAR FUNCIONARIO EN LA PLANILLA
# ============================================================

@app.route("/api/guardar_funcionario", methods=["POST"])
def api_guardar_funcionario():
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    id_funcionario = data.get("id_funcionario")

    if id_funcionario is not None:
        try:
            id_funcionario = int(id_funcionario)
        except Exception:
            return jsonify({
                "success": False,
                "error": "id_funcionario inválido."
            }), 400

        # ✅ GUARDAR AMBOS CAMPOS
        datos["id_funcionario"] = id_funcionario
        datos["usuario_creacion"] = id_funcionario    # ⚠️ ESTA ES LA CLAVE

        actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "id_funcionario": datos.get("id_funcionario"),
        "usuario_creacion": datos.get("usuario_creacion")
    })
# ============================================================
# ASIGNAR LISTA DE ID_PERSONA (endpoint que usa el frontend)
# ============================================================
# ============================================================
# ASIGNAR ID_PERSONA (uno por línea, array o primer correlativo)
# ============================================================

@app.route("/api/asignar_id_persona_lista", methods=["POST"])
def asignar_id_persona_lista():
    """
    Asigna ID_PERSONA a los trabajadores del bloque actual.

    Acepta 3 formatos:
      1) Texto multilínea (uno por línea):
         { "ids_texto": "1001\n1002\n1003" }
      2) Lista explícita:
         { "ids": [1001, 1002, 1003] }
      3) Primer ID correlativo:
         { "primer_id_persona": 1001 }
    """
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    if not procesados:
        return jsonify({
            "success": False,
            "error": "No hay trabajadores en el bloque actual."
        }), 400

    esperados = len(procesados)
    ids = []

    # ------------------------------------------------------------
    # FORMATO 1: texto multilínea (uno por línea)
    # ------------------------------------------------------------
    texto = data.get("ids_texto") or data.get("lista_ids") or data.get("texto")

    if texto:
        # Separar por saltos de línea, comas, punto y coma o espacios
        partes = re.split(r"[\s,;]+", str(texto).strip())

        for parte in partes:
            parte = parte.strip()
            if not parte:
                continue
            try:
                ids.append(int(parte))
            except Exception:
                return jsonify({
                    "success": False,
                    "error": f"Valor no numérico en la lista: '{parte}'"
                }), 400

    # ------------------------------------------------------------
    # FORMATO 2: array explícito
    # ------------------------------------------------------------
    elif data.get("ids") or data.get("id_personas"):
        ids_raw = data.get("ids") or data.get("id_personas")

        if not isinstance(ids_raw, list):
            return jsonify({
                "success": False,
                "error": "El campo 'ids' debe ser una lista."
            }), 400

        for valor in ids_raw:
            try:
                ids.append(int(valor))
            except Exception:
                return jsonify({
                    "success": False,
                    "error": f"ID inválido: {valor}"
                }), 400

    # ------------------------------------------------------------
    # FORMATO 3: primer ID correlativo
    # ------------------------------------------------------------
    else:
        primer_id = data.get("primer_id_persona") or data.get("id_persona_inicial")

        if primer_id in [None, "", "null", "undefined"]:
            return jsonify({
                "success": False,
                "error": "Debe enviar 'ids_texto', 'ids' o 'primer_id_persona'."
            }), 400

        try:
            primer_id = int(primer_id)
        except Exception:
            return jsonify({
                "success": False,
                "error": "El primer ID_PERSONA debe ser un número válido."
            }), 400

        ids = [primer_id + i for i in range(esperados)]

    # ------------------------------------------------------------
    # Validar cantidad
    # ------------------------------------------------------------
    if len(ids) != esperados:
        return jsonify({
            "success": False,
            "error": (
                f"Se esperaban {esperados} IDs (uno por trabajador del bloque), "
                f"pero se recibieron {len(ids)}."
            )
        }), 400

    # ------------------------------------------------------------
    # Validar duplicados
    # ------------------------------------------------------------
    if len(set(ids)) != len(ids):
        return jsonify({
            "success": False,
            "error": "Hay IDs duplicados en la lista."
        }), 400

    # ------------------------------------------------------------
    # Asignar
    # ------------------------------------------------------------
    for trabajador, nuevo_id in zip(procesados, ids):
        trabajador["id_persona"] = nuevo_id

    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)

    script_completo = generar_script_completo(procesados)

    return jsonify({
        "success": True,
        "asignados": len(procesados),
        "total": len(procesados),
        "ids": ids,
        "procesados": procesados,
        "trabajadores": trabajadores,
        "script_completo": script_completo,
        "script": script_completo,
        "mensaje": f"Se asignaron {len(procesados)} ID_PERSONA."
    })
# ============================================================
# GENERAR SOLO SCRIPT DE TRÁMITES (trm_tramite)
# ============================================================

@app.route("/api/generar_tramites", methods=["POST"])
def generar_tramites_endpoint():
    """
    Devuelve SOLO el script de trm_tramite (usando los id_persona ya asignados).
    """
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    if not procesados:
        return jsonify({
            "success": False,
            "error": "No hay trabajadores en el bloque actual."
        }), 400

    # Verificar que todos tengan id_persona
    sin_id = [t for t in procesados if not t.get("id_persona")]
    if sin_id:
        return jsonify({
            "success": False,
            "error": f"Hay {len(sin_id)} trabajadores sin ID_PERSONA asignado."
        }), 400

    # Generar SOLO el script de trámites
    script = generar_script_tramites(procesados, datos)

    return jsonify({
        "success": True,
        "total": len(procesados),
        "script": script,
        "script_completo": script,
        "script_tramites": script,
        "procesados": procesados,
        "id_ticket": datos.get("id_ticket"),
        "id_empresa": datos.get("id_empresa"),
        "id_funcionario": datos.get("id_funcionario")
    })



# ============================================================
# SCRIPT 1 - TICKET
# ============================================================

def generar_script_ticket(
    trabajadores,
    id_ticket,
    codigo,
    fecha,
    departamento,
    tipo_tramite,
    hora_inicio,
    hora_fin,
    razon_social="",
    nit="",
    usuario_creacion=None
):

    cantidad = len(trabajadores)

    return f"""INSERT INTO mteps_d_tickets.dtck_ticket
(codigo, id_departamento, id_tipo_tramite, nro_tramites, estado, transaccion, usuario_creacion, usuario_modificacion, 
fecha_creacion, fecha_modificacion, observacion, fecha_solicitud_ticket, fecha_atencion, hora_inicio, hora_fin, notificado, correo_notificado)
VALUES('{escapar_sql(codigo)}', {departamento}, {tipo_tramite}, {cantidad}, 'SOLICITADO', 'SOLICITAR_D_TICKET', {usuario_creacion}, NULL, now(), NULL, NULL, now(), '{escapar_sql(fecha)}', '{escapar_sql(hora_inicio)}', '{escapar_sql(hora_fin)}', false, NULL);
"""


# ============================================================
# SCRIPT 2 - PERSONAS
# ============================================================
# ============================================================
# SCRIPT 2 - PERSONAS
# ============================================================

def generar_script_personas(trabajadores, usuario_creacion=None):

    # Usuario de creación
    if usuario_creacion is None:
        datos_planilla = cargar_planilla()
        if datos_planilla:
            usuario_creacion = datos_planilla.get("usuario_creacion")

    if usuario_creacion is None:
        return "-- ⚠️ Falta usuario_creacion. Seleccione empresa primero.\n"

    if not trabajadores:
        return "-- ⚠️ No hay trabajadores en el bloque actual.\n"

    valores = []

    for t in trabajadores:

        # Datos del trabajador
        nombre    = escapar_sql(t.get("nombre") or "")
        ci        = escapar_sql(t.get("ci") or "")
        direccion = escapar_sql(t.get("direccion") or "")
        telefono  = escapar_sql(t.get("telefono") or "")
        relacion  = escapar_sql(t.get("relacion") or t.get("cargo") or "")

        # Validar CI
        if not ci:
            return f"-- ⚠️ El trabajador #{t.get('nro')} no tiene C.I.\n"

        # Construir el VALUES
        valor = (
            f"(externos_mteps.f_secuencial('ext_persona'),"
            f"'{nombre}','','',203,'{ci}','',NULL,'',NULL,NULL,NULL,NULL,NULL,"
            f"'ELABORADO', NULL, NULL, "
            f"'{relacion}', NULL,"
            f"'{direccion}','{telefono}',NULL, "
            f"{usuario_creacion},{usuario_creacion},"
            f"now(),now(),'ADICIONAR','',NULL)"
        )

        valores.append(valor)

    # Encabezado EXACTO como tu ejemplo
    script = """--------------------------INSERTA DETALLE DE TRABAJADORES
INSERT INTO externos_mteps.ext_persona
(id_persona, nombre_completo, paterno, materno, tipo_documento, nro_documento, complemento, lugar_expedicion, nacionalidad, genero, fecha_nacimiento, estado_segip, fecha_verificacion, fecha_expiracion, estado, observacion_segip, lugar_nacimiento, relacion_entidad, ocupacion, domicilio, telefono, correo, usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, transaccion, observacion, edad)
VALUES
"""

    script += ",\n".join(valores)
    script += ";"

    return script
# ============================================================
# SCRIPT 3 - COD_TRAM
# ============================================================

# ============================================================
# SCRIPT 3 - TRÁMITES (trm_tramite)
# ============================================================
def generar_script_tramites(trabajadores, datos):
    """
    Genera un INSERT de trm_tramite por cada trabajador.
    
    IMPORTANTE:
    - usuario_creacion y usuario_modificacion = ID del FUNCIONARIO que atiende (1102)
    - NO el usuario del sistema (1155)
    """

    if not trabajadores:
        return "-- ⚠️ No hay trabajadores.\n"

    # ============================================================
    # DATOS DE LA PLANILLA
    # ============================================================
    # ⚠️ CAMBIO CLAVE: usar id_funcionario (1102), NO usuario_creacion (1155)
    id_funcionario = datos.get("id_funcionario")     # ← ID del funcionario que atiende
    id_empresa     = datos.get("id_empresa")
    tipo_tramite   = datos.get("tipo_tramite")
    nit            = datos.get("nit") or ""
    razon_social   = datos.get("empresa") or ""

    # ============================================================
    # VALIDACIONES
    # ============================================================
    if id_funcionario is None:
        return "-- ⚠️ Falta id_funcionario. Seleccione funcionario en el Paso 4.\n"
    if id_empresa is None:
        return "-- ⚠️ Falta id_empresa.\n"
    if tipo_tramite is None:
        return "-- ⚠️ Falta tipo_tramite.\n"

    # ============================================================
    # PREFIJO DEL CÓDIGO DE TRÁMITE
    # ============================================================
    gestion = datetime.now().year   # 2026

    # Subquery para el correlativo
    subquery_codigo = (
        f"('TRM/{gestion}-'||((\n"
        f"        SELECT COALESCE(MAX(SUBSTRING(codigo_tramite FROM '[0-9]+$')::integer),0)\n"
        f"        FROM mteps_tramites.trm_tramite\n"
        f"        WHERE codigo_tramite LIKE 'TRM/{gestion}-%'\n"
        f"    ) + 1))"
    )

    valores = []

    for t in trabajadores:

        id_persona = t.get("id_persona")

        if id_persona in [None, "", "null", "undefined"]:
            return f"-- ⚠️ El trabajador #{t.get('nro')} no tiene ID_PERSONA asignado.\n"

        try:
            id_persona = int(id_persona)
        except Exception:
            return f"-- ⚠️ ID_PERSONA inválido: {id_persona}\n"

        nit_esc   = escapar_sql(nit)
        razon_esc = escapar_sql(razon_social)

        # ============================================================
        # VALUES — 53 columnas exactas
        # ============================================================
        valor = (
    f"(mteps_tramites.f_secuencial('trm_tramite'),"       # 1. id_tramite
    f"{subquery_codigo}, "                                 # 2. codigo_tramite
    f"{tipo_tramite}, "                                    # 3. id_clasificador_tramite
    f"NULL, "                                              # 4. monto_total_multa
    f"'ADICIONAR_TICKET', "                                # 5. transaccion
    f"'ELABORADO_TICKET', "                                # 6. estado
    f"{id_funcionario}, {id_funcionario}, "                # 7-8. usuario_creacion, usuario_modificacion
    f"now(), now(), "                                      # 9-10. fecha_creacion, fecha_modificacion
    f"{id_empresa}, "                                      # 11. id_empresa
    f"{id_persona}, "                                      # 12. id_persona
    f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "    # 13-20. 8 NULLs
    f"NULL, NULL, NULL, NULL, NULL, NULL, NULL, "          # 21-27. 7 NULLs
    f"'{nit_esc}', "                                       # 28. nit
    f"NULL, NULL, NULL, "                                  # 29-31. 3 NULLs ← ✅ CORREGIDO
    f"'{razon_esc}', "                                     # 32. razon_social
    f"false, "                                             # 33. persona_natural
    f"NULL, NULL, NULL, NULL, NULL, "                      # 34-38. 5 NULLs ← ✅ CORREGIDO
    f"NULL, NULL, NULL, NULL, NULL, NULL, "                # 39-44. 6 NULLs
    f"NULL, NULL, NULL, NULL, NULL, "                      # 45-49. 5 NULLs
    f"NULL, NULL, NULL, NULL)"                             # 50-53. 4 NULLs
)

        valores.append(valor)

    script = """--- INSERTA TRAMITE (un INSERT por trabajador)
INSERT INTO mteps_tramites.trm_tramite
(id_tramite, codigo_tramite, id_clasificador_tramite, monto_total_multa, transaccion, estado, usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, id_empresa, id_persona, periodo_planilla, gestion_planilla, minera, dias_retraso, monto_calculo, nro_trabajadores, fecha_pago_prima, id_detalle_finiquito, resolucion_administrativa, relacion_entidad, nro_fojas, observacion, json_requisitos, nhr_tramite_relacionado, nur_sigec, nit, matricula_comercio, codigo_multa, codigo_manual, razon_social, persona_natural, codigo_visado, declarado_fc, codigo_fc, id_ra, id_sucursal, nro_hojas_foleadas, descripcion_sucursal, nro_hojas_leg, documento_leg, nro_boleta_err, fecha_boleta_err, motivo_err, monto_err, c21_erroneos, c31_erroneos, devuelto_err, desc_result_err, id_imputacion, mnt_tipo_cambio, pais_visado)
VALUES
"""

    script += ",\n".join(valores)
    script += ";"

    return script

# ============================================================
# SCRIPT 4 - ID_TRAMITE
# ============================================================

def generar_script_idtramites(trabajadores):

    script = ""

    for t in trabajadores:

        id_tramite = t.get("id_tramite") or "PENDIENTE"
        codigo = t.get("codigo_tramite") or "PENDIENTE"

        script += f"""-- TRABAJADOR #{t.get("nro")}
-- ID_TICKET: {t.get("id_ticket")}
-- ID_PERSONA: {t.get("id_persona")}
-- COD_TRAM: {codigo}
-- ID_TRAMITE: {id_tramite}

"""

    return script


# ============================================================
# SCRIPT 5 - ATENCIÓN
# ============================================================
# ============================================================
# SCRIPT 5 - ATENCIÓN (dtck_ticket_atencion_tramite)
# ============================================================
# ============================================================
# SCRIPT 5 - ATENCIÓN (dtck_ticket_atencion_tramite)
# ============================================================
def generar_script_atencion(trabajadores, datos=None):

    if not trabajadores:
        return "-- ⚠️ No hay trabajadores.\n"

    # Obtener datos de la planilla
    if datos is None:
        datos = cargar_planilla()
        if not datos:
            return "-- ⚠️ No hay planilla cargada.\n"

    id_ticket        = datos.get("id_ticket")
    fecha            = datos.get("fecha") or datetime.now().strftime("%Y-%m-%d")

    # ⚠️ id_usuario_asignado = el funcionario que atiende (253)
    id_funcionario   = datos.get("id_funcionario")

    # Validaciones
    if id_ticket is None:
        return "-- ⚠️ Falta id_ticket. Genere el ticket primero.\n"
    if id_funcionario is None:
        return "-- ⚠️ Falta id_funcionario. Seleccione funcionario en el Paso 4.\n"

    valores = []

    for t in trabajadores:

        # ---------- ID_TRAMITE ----------
        id_tramite = t.get("id_tramite")

        if id_tramite in [None, "", "null", "undefined"]:
            return f"-- ⚠️ El trabajador #{t.get('nro')} no tiene ID_TRAMITE asignado.\n"

        try:
            id_tramite = int(id_tramite)
        except Exception:
            return f"-- ⚠️ ID_TRAMITE inválido: {id_tramite}\n"

        # ---------- HORARIOS ----------
        hora_inicio = t.get("hora_inicio") or "00:00:00"
        hora_fin    = t.get("hora_fin")    or "00:00:00"

        # ---------- VALUES ----------
        valor = (
            f"({id_ticket},"
            f"{id_tramite},"
            f"{id_funcionario},"        # id_usuario_asignado
            f"'{escapar_sql(fecha)}',"
            f"'{escapar_sql(hora_inicio)}',"
            f"'{escapar_sql(hora_fin)}',"
            f"'INICIAL',"
            f"'SOLICITAR_D_TICKET',"
            f"{id_funcionario},"        # ← ✅ CORREGIDO: usuario_creacion = FUNCIONARIO
            f"NULL,"
            f"now(),"
            f"NULL,"
            f"NULL)"
        )

        valores.append(valor)

    script = """INSERT INTO mteps_d_tickets.dtck_ticket_atencion_tramite
(id_ticket, id_tramite, id_usuario_asignado, fecha_atencion, hora_inicio, hora_fin, estado, transaccion, usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, observacion)
VALUES
"""

    script += ",\n".join(valores)
    script += ";"

    return script

# ============================================================
# ASIGNAR ID_TRAMITE (Códigos Trámite)
# ============================================================
# ============================================================
# GENERAR SCRIPT DE ATENCIÓN (Paso 8)
# ============================================================

@app.route("/api/generar_atencion", methods=["POST"])
def generar_atencion_endpoint():
    """
    Devuelve el script de dtck_ticket_atencion_tramite.
    """
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    if not procesados:
        return jsonify({
            "success": False,
            "error": "No hay trabajadores en el bloque actual."
        }), 400

    # Verificar que todos tengan id_tramite
    sin_id = [t for t in procesados if not t.get("id_tramite")]
    if sin_id:
        return jsonify({
            "success": False,
            "error": f"Hay {len(sin_id)} trabajadores sin ID_TRAMITE asignado."
        }), 400

    script = generar_script_atencion(procesados, datos)

    return jsonify({
        "success": True,
        "total": len(procesados),
        "script": script,
        "script_completo": script,
        "script_atencion": script,
        "id_ticket": datos.get("id_ticket"),
        "id_funcionario": datos.get("id_funcionario")
    })
# ============================================================
# ASIGNAR ID_TRAMITE + ID_TICKET (Paso 7)
# Genera el script de ATENCIÓN
# ============================================================

@app.route("/api/asignar_id_tramite_lista", methods=["POST"])
def asignar_id_tramite_lista():
    """
    Recibe:
      - id_ticket (del sistema externo)
      - lista_ids (id_tramite, uno por línea)

    Genera el script de dtck_ticket_atencion_tramite.
    """
    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    if not procesados:
        return jsonify({
            "success": False,
            "error": "No hay trabajadores en el bloque actual."
        }), 400

    # ------------------------------------------------------------
    # VALIDAR ID_TICKET
    # ------------------------------------------------------------
    id_ticket = data.get("id_ticket")

    if id_ticket in [None, "", "null", "undefined"]:
        return jsonify({
            "success": False,
            "error": "Debe ingresar el ID_TICKET."
        }), 400

    try:
        id_ticket = int(id_ticket)
    except Exception:
        return jsonify({
            "success": False,
            "error": "ID_TICKET inválido."
        }), 400

    # ------------------------------------------------------------
    # VALIDAR LISTA DE ID_TRAMITE
    # ------------------------------------------------------------
    esperados = len(procesados)
    ids = []

    texto = (
        data.get("lista_ids")
        or data.get("ids_texto")
        or data.get("texto")
    )

    if texto:
        partes = re.split(r"[\s,;]+", str(texto).strip())
        for parte in partes:
            parte = parte.strip()
            if not parte:
                continue
            try:
                ids.append(int(parte))
            except Exception:
                return jsonify({
                    "success": False,
                    "error": f"Valor no numérico: '{parte}'"
                }), 400

    elif data.get("ids"):
        ids_raw = data.get("ids")
        if not isinstance(ids_raw, list):
            return jsonify({
                "success": False,
                "error": "El campo 'ids' debe ser una lista."
            }), 400
        for valor in ids_raw:
            try:
                ids.append(int(valor))
            except Exception:
                return jsonify({
                    "success": False,
                    "error": f"ID inválido: {valor}"
                }), 400

    else:
        return jsonify({
            "success": False,
            "error": "Debe enviar 'lista_ids' o 'ids'."
        }), 400

    # ------------------------------------------------------------
    # Validar cantidad
    # ------------------------------------------------------------
    if len(ids) != esperados:
        return jsonify({
            "success": False,
            "error": (
                f"Se esperaban {esperados} IDs (uno por trabajador del bloque), "
                f"pero se recibieron {len(ids)}."
            )
        }), 400

    # ------------------------------------------------------------
    # Validar duplicados
    # ------------------------------------------------------------
    if len(set(ids)) != len(ids):
        return jsonify({
            "success": False,
            "error": "Hay IDs duplicados en la lista."
        }), 400

    # ------------------------------------------------------------
    # Asignar ID_TICKET e ID_TRAMITE a cada trabajador
    # ------------------------------------------------------------
    datos["id_ticket"] = id_ticket

    for trabajador, nuevo_id in zip(procesados, ids):
        trabajador["id_ticket"] = id_ticket
        trabajador["id_tramite"] = nuevo_id

    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)

    rango = f"{min(ids)} - {max(ids)}" if ids else "-"

    # ------------------------------------------------------------
    # GENERAR SCRIPT DE ATENCIÓN
    # ------------------------------------------------------------
    script = generar_script_atencion(procesados, datos)

    return jsonify({
        "success": True,
        "asignados": len(procesados),
        "total": len(procesados),
        "ids": ids,
        "rango": rango,
        "id_ticket": id_ticket,
        "procesados": procesados,
        "trabajadores": trabajadores,
        "script": script,
        "script_completo": script,
        "script_atencion": script,
        "mensaje": f"Se asignaron {len(procesados)} ID_TRAMITE al ticket {id_ticket}."
    })

# ============================================================
# FECHA
# ============================================================

def datos_fecha_actual():

    datos = cargar_planilla()

    if datos and datos.get("fecha"):
        return str(datos["fecha"])

    return datetime.now().strftime("%Y-%m-%d")


# ============================================================
# SCRIPT COMPLETO
# ============================================================
def generar_script_completo(trabajadores):
    datos = cargar_planilla()
    if not datos:
        return ""

    usuario_creacion = datos.get("usuario_creacion")
    id_ticket        = datos.get("id_ticket")
    codigo           = datos.get("codigo_ticket") or "RF-001"
    fecha            = datos.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    departamento     = datos.get("departamento")
    tipo_tramite     = datos.get("tipo_tramite")
    hora_inicio      = datos.get("hora_base") or "08:30:00"
    hora_fin         = datos.get("hora_fin") or hora_inicio
    razon_social     = datos.get("empresa", "")
    nit              = datos.get("nit", "")

    # Validaciones
    avisos = []
    if usuario_creacion is None:
        avisos.append("-- ⚠️ Falta usuario_creacion. Seleccione empresa primero.")
    if id_ticket is None:
        avisos.append("-- ⚠️ Falta id_ticket. Genere el ticket en el Paso 4.")
    if departamento is None:
        avisos.append("-- ⚠️ Falta departamento.")
    if tipo_tramite is None:
        avisos.append("-- ⚠️ Falta tipo_tramite.")
    if avisos:
        return "\n".join(avisos) + "\n"

    script = ""

    # 1) TICKET
    script += generar_script_ticket(
        trabajadores, id_ticket, codigo, fecha,
        departamento, tipo_tramite, hora_inicio, hora_fin,
        razon_social, nit, usuario_creacion
    )
    script += "\n\n"

    # 2) PERSONAS
    script += generar_script_personas(trabajadores, usuario_creacion)
    script += "\n\n"

    # 3) TRÁMITES (usa id_persona pegado por el usuario)
    script += generar_script_tramites(trabajadores, datos)

    return script

# ============================================================
# SCRIPT FINAL
# ============================================================

@app.route(
    "/api/generar_script_final",
    methods=["GET"]
)
def generar_script_final():

    datos = cargar_planilla()

    if not datos:

        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = trabajadores_actuales()

    script = generar_script_completo(trabajadores)

    return jsonify({

        "success": True,

        "script_completo":
            script,

        "trabajadores":
            trabajadores,

        "cantidad":
            len(trabajadores),

        "id_ticket":
            datos.get("id_ticket")
    })

# ============================================================
# DESCARGAR EXCEL CON LA PLANILLA LLENA
# ============================================================

@app.route("/api/descargar_excel", methods=["GET"])
def descargar_excel():
    """
    Genera un Excel con la planilla llena (IDs, horas, códigos).
    Incluye el nombre de la empresa en el encabezado.
    """

    datos = cargar_planilla()

    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]

    if not procesados:
        return jsonify({
            "success": False,
            "error": "No hay trabajadores en el bloque actual."
        }), 400

    # ============================================================
    # CREAR LIBRO DE EXCEL
    # ============================================================
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planilla Procesada"

    # ============================================================
    # ESTILOS
    # ============================================================
    fuente_titulo = Font(name="Calibri", size=14, bold=True, color="1A3C6E")
    fuente_subtitulo = Font(name="Calibri", size=11, bold=True, color="333333")
    fuente_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fuente_dato = Font(name="Calibri", size=10)

    relleno_header = PatternFill(
        start_color="1A3C6E",
        end_color="1A3C6E",
        fill_type="solid"
    )
    relleno_empresa = PatternFill(
        start_color="E7F3FF",
        end_color="E7F3FF",
        fill_type="solid"
    )

    alineacion_centro = Alignment(horizontal="center", vertical="center")
    alineacion_izq = Alignment(horizontal="left", vertical="center")

    borde = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC")
    )

    # ============================================================
    # DATOS DE LA EMPRESA
    # ============================================================
    empresa = datos.get("empresa") or "EMPRESA NO ESPECIFICADA"
    nit = datos.get("nit") or ""
    codigo_ticket = datos.get("codigo_ticket") or ""
    id_ticket = datos.get("id_ticket") or ""
    fecha = datos.get("fecha") or ""
    tipo_tramite = datos.get("tipo_tramite")
    departamento = datos.get("departamento")

    tipo_tramite_nombre = TIPOS_TRAMITE.get(tipo_tramite, "N/D")
    departamento_nombre = DEPARTAMENTOS.get(departamento, "N/D")

    # ============================================================
    # ENCABEZADO
    # ============================================================

    # Fila 1: Nombre de la empresa
    ws.merge_cells("A1:M1")
    celda_empresa = ws["A1"]
    celda_empresa.value = empresa
    celda_empresa.font = fuente_titulo
    celda_empresa.alignment = alineacion_centro
    celda_empresa.fill = relleno_empresa
    ws.row_dimensions[1].height = 28

    # Fila 2: NIT + Departamento + Tipo
    ws.merge_cells("A2:M2")
    celda_info = ws["A2"]
    celda_info.value = (
        f"NIT: {nit}  |  Departamento: {departamento_nombre}  |  "
        f"Tipo de Trámite: {tipo_tramite_nombre}"
    )
    celda_info.font = fuente_subtitulo
    celda_info.alignment = alineacion_centro
    ws.row_dimensions[2].height = 20

    # Fila 3: Ticket + Fecha
    ws.merge_cells("A3:M3")
    celda_ticket = ws["A3"]
    celda_ticket.value = (
        f"Ticket: {codigo_ticket}  |  ID_TICKET: {id_ticket}  |  Fecha: {fecha}"
    )
    celda_ticket.font = fuente_subtitulo
    celda_ticket.alignment = alineacion_centro
    ws.row_dimensions[3].height = 20

    # Fila 4: vacía
    ws.row_dimensions[4].height = 8

    # ============================================================
    # ENCABEZADOS DE LA TABLA
    # ============================================================
    encabezados = [
        "N°",
        "C.I.",
        "Expedición",
        "Nombre Completo",
        "Relación",
        "Teléfono",
        "Dirección",
        "ID_PERSONA",
        "COD_TRAM",
        "ID_TRAMITE",
        "Hora Inicio",
        "Hora Fin",
        "Estado"
    ]

    for col_idx, encabezado in enumerate(encabezados, start=1):
        celda = ws.cell(row=5, column=col_idx, value=encabezado)
        celda.font = fuente_header
        celda.fill = relleno_header
        celda.alignment = alineacion_centro
        celda.border = borde

    ws.row_dimensions[5].height = 22

    # ============================================================
    # DATOS DE TRABAJADORES
    # ============================================================
    for idx, t in enumerate(procesados, start=1):
        fila = idx + 5

        tiene_todo = (
            t.get("id_persona") and
            t.get("id_tramite") and
            t.get("hora_inicio")
        )
        estado = "COMPLETO" if tiene_todo else "PENDIENTE"

        valores = [
            t.get("nro", ""),
            t.get("ci", ""),
            t.get("expedicion", ""),
            t.get("nombre", ""),
            t.get("relacion", t.get("cargo", "")),
            t.get("telefono", ""),
            t.get("direccion", ""),
            t.get("id_persona", ""),
            t.get("codigo_tramite", ""),
            t.get("id_tramite", ""),
            t.get("hora_inicio", ""),
            t.get("hora_fin", ""),
            estado
        ]

        for col_idx, valor in enumerate(valores, start=1):
            celda = ws.cell(row=fila, column=col_idx, value=valor)
            celda.font = fuente_dato
            celda.border = borde
            celda.alignment = (
                alineacion_centro
                if col_idx in [1, 2, 3, 8, 9, 10, 11, 12, 13]
                else alineacion_izq
            )

        # Alternar color de filas
        if idx % 2 == 0:
            for col_idx in range(1, len(encabezados) + 1):
                celda = ws.cell(row=fila, column=col_idx)
                celda.fill = PatternFill(
                    start_color="F8F9FA",
                    end_color="F8F9FA",
                    fill_type="solid"
                )

    # ============================================================
    # AJUSTAR ANCHO DE COLUMNAS
    # ============================================================
    anchos = [6, 12, 10, 35, 18, 14, 35, 14, 14, 14, 12, 12, 14]

    for col_idx, ancho in enumerate(anchos, start=1):
        letra = get_column_letter(col_idx)
        ws.column_dimensions[letra].width = ancho

    # Congelar panel
    ws.freeze_panes = "A6"

    # ============================================================
    # GUARDAR Y ENVIAR
    # ============================================================
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    nombre_archivo = f"planilla_{codigo_ticket or 'sin_codigo'}_{fecha or 'sin_fecha'}.xlsx"
    nombre_archivo = nombre_archivo.replace("/", "-").replace("\\", "-")

    return send_file(
        output,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ============================================================
# ERROR 404
# ============================================================

@app.errorhandler(404)
def page_not_found(e):

    return render_template(
        "error.html",
        mensaje="Página no encontrada",
        step=0
    )


# ============================================================
# ERROR GENERAL
# ============================================================

@app.errorhandler(500)
def error_interno(e):

    return jsonify({
        "success": False,
        "error": "Error interno del servidor."
    }), 500

# ============================================================
# CERRAR SESIÓN / VOLVER AL PASO 1
# ============================================================

@app.route("/api/cerrar_sesion", methods=["POST"])
def cerrar_sesion():
    """Limpia la sesión actual y permite volver al Paso 1"""
    try:
        # Limpiar la sesión
        session.clear()
        
        return jsonify({
            "success": True,
            "mensaje": "Sesión cerrada correctamente. Redirigiendo al inicio..."
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )