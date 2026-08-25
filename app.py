from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS

import pandas as pd
import os
import json
import secrets
import re

from datetime import datetime, timedelta


# ============================================================
# CONFIGURACIÓN
# ============================================================

app = Flask(__name__)

app.secret_key = "sistema_tickets_clave_2026"

CORS(app)

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

    mapa = {}

    for clave in fila.keys():

        normalizada = normalizar_nombre_columna(clave)

        mapa[normalizada] = clave

    for posible in posibles:

        normalizada = normalizar_nombre_columna(posible)

        if normalizada in mapa:

            columna = mapa[normalizada]

            return limpiar_valor(
                fila.get(columna, "")
            )

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
            "DOCENTES PENDIENTES DE VISADO DE FINIQUITO",
            "DOCENTE",
            "NOMBRE",
            "NOMBRE COMPLETO",
            "NOMBRE_COMPLETO"
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
# PASO 4 - CONFIGURACIÓN DEL TICKET (CON NIT Y RAZON SOCIAL)
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

    hora_fin = (
        data.get("hora_fin")
        or "13:21:00"
    )

    # NIT Y RAZON SOCIAL - SE CAPTURAN DESDE EL FRONTEND
    razon_social = (
        data.get("razon_social")
        or data.get("empresa")
        or ""
    )

    nit = str(
        data.get("nit", "")
    ).strip()

    tipo_tramite = data.get(
        "tipo_tramite",
        datos.get("tipo_tramite", 174)
    )

    departamento = data.get(
        "departamento",
        datos.get("departamento", 32)
    )

    try:
        tipo_tramite = int(tipo_tramite)
    except Exception:
        tipo_tramite = 174

    try:
        departamento = int(departamento)
    except Exception:
        departamento = 32

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

    datos["codigo_ticket"] = str(codigo)
    datos["fecha"] = str(fecha)
    datos["hora_base"] = str(hora_inicio)
    datos["hora_fin"] = str(hora_fin)

    # GUARDAR NIT Y RAZON SOCIAL
    datos["empresa"] = razon_social
    datos["nit"] = nit

    datos["tipo_tramite"] = tipo_tramite
    datos["departamento"] = departamento

    datos["cantidad_procesar"] = (
        hasta - desde + 1
    )

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
# PASO 4 - GENERAR ID_TICKET (CON NIT Y RAZON SOCIAL)
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
    id_ticket = datos.get(
        "id_ticket"
    )

    enviado = data.get("id_ticket")

    if enviado not in [
        None,
        "",
        "null",
        "undefined"
    ]:

        try:
            id_ticket = int(enviado)
        except Exception:
            pass

    # Si no existe, EL SISTEMA LO GENERA
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

    hora_fin = (
        data.get("hora_fin")
        or datos.get("hora_fin")
        or "13:21:00"
    )

    departamento = (
        data.get("departamento")
        if data.get("departamento") not in [
            None, ""
        ]
        else datos.get("departamento", 32)
    )

    tipo_tramite = (
        data.get("tipo_tramite")
        if data.get("tipo_tramite") not in [
            None, ""
        ]
        else datos.get("tipo_tramite", 174)
    )

    # OBTENER NIT Y RAZON SOCIAL
    razon_social = datos.get("empresa", "")
    nit = datos.get("nit", "")

    try:
        departamento = int(departamento)
    except Exception:
        departamento = 32

    try:
        tipo_tramite = int(tipo_tramite)
    except Exception:
        tipo_tramite = 174

    if departamento not in DEPARTAMENTOS:
        departamento = 32

    if tipo_tramite not in TIPOS_TRAMITE:
        tipo_tramite = 174

    cantidad = data.get(
        "cantidad_procesar"
    )

    if cantidad in [
        None,
        "",
        "null",
        "undefined"
    ]:

        cantidad = data.get(
            "cantidad_trabajadores"
        )

    if cantidad in [
        None,
        "",
        "null",
        "undefined"
    ]:

        cantidad = datos.get(
            "cantidad_procesar",
            0
        )

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

    desde = int(
        datos.get(
            "desde_trabajador",
            1
        )
    )

    if desde < 1:
        desde = 1

    if desde > total:

        return jsonify({
            "success": False,
            "error":
                "El trabajador inicial está fuera del rango."
        }), 400

    hasta = min(
        desde + cantidad - 1,
        total
    )

    cantidad_real = (
        hasta - desde + 1
    )

    # ASIGNAR EL MISMO ID_TICKET A TODOS
    for trabajador in trabajadores:

        nro = int(
            trabajador.get(
                "nro",
                0
            )
        )

        if desde <= nro <= hasta:

            trabajador["id_ticket"] = id_ticket
            trabajador["procesar"] = True

            indice = nro - desde

            inicio = sumar_minutos(
                hora_inicio,
                indice * 4
            )

            fin = sumar_minutos(
                inicio,
                3
            )

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
        nit
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

        "trabajadores":
            trabajadores,

        "procesados":
            procesados,

        "script":
            script,

        "razon_social": razon_social,
        "nit": nit
    })


# ============================================================
# PASO 5 - REGISTRAR ID_PERSONA (CORRELATIVO)
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
    
    # PRIMER ID_PERSONA ingresado manualmente
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
            # ASIGNAR ID CORRELATIVO
            trabajador["id_persona"] = primer_id + idx
            registrados += 1
            idx += 1
    
    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)
    
    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]
    
    # Generar script completo acumulado
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
# PASO 6 - REGISTRAR COD_TRAM (CORRELATIVO)
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
    
    # PRIMER COD_TRAM ingresado manualmente
    primer_codigo = data.get("primer_cod_tram")
    
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))
    
    if primer_codigo is None or primer_codigo == "":
        return jsonify({
            "success": False,
            "error": "Debe ingresar el primer COD_TRAM."
        }), 400
    
    # Extraer el prefijo y el número del código
    codigo_str = str(primer_codigo).strip()
    
    # Buscar el número al final del código
    match = re.search(r'(\D*)(\d+)$', codigo_str)
    
    if match:
        prefijo = match.group(1)
        numero_inicial = int(match.group(2))
    else:
        # Si no tiene formato, usar el código como prefijo y empezar desde 1
        prefijo = codigo_str + "-"
        numero_inicial = 1
    
    registrados = 0
    idx = 0
    
    for trabajador in trabajadores:
        nro = int(trabajador.get("nro", 0))
        
        if desde <= nro <= hasta:
            # ASIGNAR COD_TRAM CORRELATIVO
            numero_actual = numero_inicial + idx
            # Formatear el número con ceros a la izquierda (3 dígitos)
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
    
    # Generar script completo acumulado
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
# PASO 7 - REGISTRAR ID_TRAMITE (CORRELATIVO)
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
    
    # PRIMER ID_TRAMITE ingresado manualmente
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
            # ASIGNAR ID_TRAMITE CORRELATIVO
            trabajador["id_tramite"] = primer_id + idx
            registrados += 1
            idx += 1
    
    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)
    
    procesados = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]
    
    # Generar script completo acumulado
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
# PREVISUALIZACIÓN COMPLETA (ACUMULADA)
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
    
    # Generar script completo acumulado
    script_completo = generar_script_completo(procesados)
    
    # Obtener estado de cada paso
    tiene_id_persona = any(t.get("id_persona") for t in procesados)
    tiene_cod_tram = any(t.get("codigo_tramite") for t in procesados)
    tiene_id_tramite = any(t.get("id_tramite") for t in procesados)
    
    return jsonify({
        "success": True,
        "procesados": procesados,
        "script_completo": script_completo,
        "estado": {
            "id_persona": tiene_id_persona,
            "cod_tram": tiene_cod_tram,
            "id_tramite": tiene_id_tramite
        },
        "total": len(procesados),
        "tiene_id_persona": tiene_id_persona,
        "tiene_cod_tram": tiene_cod_tram,
        "tiene_id_tramite": tiene_id_tramite,
        "razon_social": datos.get("empresa", ""),
        "nit": datos.get("nit", "")
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

        "departamento":
            datos.get("departamento"),

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

    trabajadores = datos.get(
        "trabajadores",
        []
    )

    total = len(trabajadores)

    hasta_actual = int(
        datos.get(
            "hasta_trabajador",
            0
        )
    )

    if hasta_actual >= total:

        return jsonify({

            "success": False,

            "terminado": True,

            "mensaje":
                "No quedan trabajadores pendientes."
        })

    nuevo_desde = hasta_actual + 1

    data = request.get_json(
        silent=True
    ) or {}

    cantidad = data.get(
        "cantidad_procesar",
        data.get("cantidad")
    )

    if cantidad is None:

        cantidad = (
            total
            - nuevo_desde
            + 1
        )

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

    nuevo_hasta = min(
        nuevo_desde + cantidad - 1,
        total
    )

    datos["desde_trabajador"] = nuevo_desde

    datos["cantidad_procesar"] = (
        nuevo_hasta
        - nuevo_desde
        + 1
    )

    datos["hasta_trabajador"] = nuevo_hasta

    # NUEVA OPERACIÓN - NO REUTILIZA EL ID_TICKET
    datos["id_ticket"] = None

    # Limpiar datos del nuevo bloque
    for trabajador in trabajadores:

        nro = int(
            trabajador.get(
                "nro",
                0
            )
        )

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

    total = len(
        datos.get(
            "trabajadores",
            []
        )
    )

    hasta = int(
        datos.get(
            "hasta_trabajador",
            0
        )
    )

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
# SCRIPT 1 - TICKET (CON NIT Y RAZON SOCIAL)
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
    nit=""
):

    cantidad = len(trabajadores)

    return f"""
-- ============================================================
-- 1. INSERTAR TICKET
-- ============================================================

-- ID_TICKET GENERADO POR EL SISTEMA: {id_ticket}
-- RAZON SOCIAL: {escapar_sql(razon_social)}
-- NIT: {escapar_sql(nit)}

INSERT INTO mteps_d_tickets.dtck_ticket
(
    codigo,
    id_departamento,
    id_tipo_tramite,
    nro_tramites,
    estado,
    transaccion,
    usuario_creacion,
    usuario_modificacion,
    fecha_creacion,
    fecha_modificacion,
    observacion,
    fecha_solicitud_ticket,
    fecha_atencion,
    hora_inicio,
    hora_fin,
    notificado,
    correo_notificado,
    razon_social,
    nit
)
VALUES
(
    '{escapar_sql(codigo)}',
    {departamento},
    {tipo_tramite},
    {cantidad},
    'SOLICITADO',
    'SOLICITAR_D_TICKET',
    1155,
    NULL,
    now(),
    NULL,
    NULL,
    now(),
    '{escapar_sql(fecha)}',
    '{escapar_sql(hora_inicio)}',
    '{escapar_sql(hora_fin)}',
    false,
    NULL,
    '{escapar_sql(razon_social)}',
    '{escapar_sql(nit)}'
);

"""


# ============================================================
# SCRIPT 2 - PERSONAS
# ============================================================

def generar_script_personas(trabajadores):

    if not trabajadores:
        return ""

    valores = []

    for t in trabajadores:

        id_persona = t.get(
            "id_persona"
        )

        if id_persona in [
            None,
            "",
            "None"
        ]:
            id_persona_sql = "NULL"
        else:
            id_persona_sql = str(
                id_persona
            )

        valor = f"""
(
    {t.get("id_ticket") or "NULL"},
    {id_persona_sql},
    '{escapar_sql(t.get("nombre"))}',
    '',
    '',
    203,
    '{escapar_sql(t.get("ci"))}',
    '',
    '{escapar_sql(t.get("expedicion"))}',
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    'ELABORADO',
    NULL,
    NULL,
    '{escapar_sql(t.get("relacion") or t.get("cargo"))}',
    NULL,
    '{escapar_sql(t.get("direccion"))}',
    '{escapar_sql(t.get("telefono"))}',
    NULL,
    1155,
    1155,
    now(),
    now(),
    'ADICIONAR',
    '',
    NULL
)
"""

        valores.append(valor)

    return f"""
-- ============================================================
-- 2. INSERTAR PERSONAS
-- ============================================================

INSERT INTO externos_mteps.ext_persona
(
    id_ticket,
    id_persona,
    nombre_completo,
    paterno,
    materno,
    tipo_documento,
    nro_documento,
    complemento,
    lugar_expedicion,
    nacionalidad,
    genero,
    fecha_nacimiento,
    estado_segip,
    fecha_verificacion,
    fecha_expiracion,
    estado,
    observacion_segip,
    lugar_nacimiento,
    relacion_entidad,
    ocupacion,
    domicilio,
    telefono,
    correo,
    usuario_creacion,
    usuario_modificacion,
    fecha_creacion,
    fecha_modificacion,
    transaccion,
    observacion,
    edad
)
VALUES
{",".join(valores)};

"""


# ============================================================
# SCRIPT 3 - COD_TRAM
# ============================================================

def generar_script_codigos(trabajadores):

    script = """
-- ============================================================
-- 3. COD_TRAM
-- ============================================================

"""

    for t in trabajadores:

        codigo = (
            t.get("codigo_tramite")
            or "PENDIENTE"
        )

        script += f"""
-- TRABAJADOR #{t.get("nro")}
-- ID_TICKET: {t.get("id_ticket")}
-- ID_PERSONA: {t.get("id_persona")}
-- COD_TRAM: {codigo}

"""

    return script


# ============================================================
# SCRIPT 4 - ID_TRAMITE
# ============================================================

def generar_script_idtramites(trabajadores):

    script = """
-- ============================================================
-- 4. ID_TRAMITE
-- ============================================================

"""

    for t in trabajadores:

        id_tramite = (
            t.get("id_tramite")
            or "PENDIENTE"
        )

        codigo = (
            t.get("codigo_tramite")
            or "PENDIENTE"
        )

        script += f"""
-- TRABAJADOR #{t.get("nro")}
-- ID_TICKET: {t.get("id_ticket")}
-- ID_PERSONA: {t.get("id_persona")}
-- COD_TRAM: {codigo}
-- ID_TRAMITE: {id_tramite}

"""

    return script


# ============================================================
# SCRIPT 5 - ATENCIÓN
# ============================================================

def generar_script_atencion(trabajadores):

    if not trabajadores:
        return ""

    valores = []

    for t in trabajadores:

        id_ticket = (
            t.get("id_ticket")
            or "NULL"
        )

        id_tramite = (
            t.get("id_tramite")
            or "NULL"
        )

        fecha = datos_fecha_actual()

        hora_inicio = (
            t.get("hora_inicio")
            or "00:00:00"
        )

        hora_fin = (
            t.get("hora_fin")
            or "00:00:00"
        )

        valores.append(
            f"""
(
    {id_ticket},
    {id_tramite},
    981,
    '{escapar_sql(fecha)}',
    '{escapar_sql(hora_inicio)}',
    '{escapar_sql(hora_fin)}',
    'INICIAL',
    'SOLICITAR_D_TICKET',
    981,
    NULL,
    now(),
    NULL,
    NULL
)
"""
        )

    return f"""
-- ============================================================
-- 5. INSERTAR ATENCIÓN
-- ============================================================

INSERT INTO mteps_d_tickets.dtck_ticket_atencion_tramite
(
    id_ticket,
    id_tramite,
    id_usuario_asignado,
    fecha_atencion,
    hora_inicio,
    hora_fin,
    estado,
    transaccion,
    usuario_creacion,
    usuario_modificacion,
    fecha_creacion,
    fecha_modificacion,
    observacion
)
VALUES
{",".join(valores)};

"""


# ============================================================
# FECHA
# ============================================================

def datos_fecha_actual():

    datos = cargar_planilla()

    if datos and datos.get("fecha"):
        return str(datos["fecha"])

    return datetime.now().strftime(
        "%Y-%m-%d"
    )


# ============================================================
# SCRIPT COMPLETO (CON NIT Y RAZON SOCIAL)
# ============================================================

def generar_script_completo(trabajadores):

    datos = cargar_planilla()

    if not datos:
        return ""

    id_ticket = datos.get(
        "id_ticket"
    )

    codigo = datos.get(
        "codigo_ticket",
        "RF-001"
    )

    fecha = datos.get(
        "fecha"
    ) or datetime.now().strftime(
        "%Y-%m-%d"
    )

    departamento = datos.get(
        "departamento",
        32
    )

    tipo_tramite = datos.get(
        "tipo_tramite",
        174
    )

    hora_inicio = datos.get(
        "hora_base",
        "08:30:00"
    )

    hora_fin = datos.get(
        "hora_fin",
        "13:21:00"
    )

    razon_social = datos.get("empresa", "")
    nit = datos.get("nit", "")

    script = f"""
-- ============================================================
-- SCRIPT COMPLETO
-- ============================================================
-- PLANILLA: {datos.get("planilla_id")}
-- ARCHIVO: {datos.get("archivo_nombre", "")}
-- ID_TICKET: {id_ticket}
-- RF: {codigo}
-- RAZON SOCIAL: {escapar_sql(razon_social)}
-- NIT: {escapar_sql(nit)}
-- TRABAJADORES: {len(trabajadores)}
-- FECHA: {fecha}
-- ============================================================

"""

    script += generar_script_ticket(
        trabajadores,
        id_ticket,
        codigo,
        fecha,
        departamento,
        tipo_tramite,
        hora_inicio,
        hora_fin,
        razon_social,
        nit
    )

    script += generar_script_personas(
        trabajadores
    )

    script += generar_script_codigos(
        trabajadores
    )

    script += generar_script_idtramites(
        trabajadores
    )

    script += generar_script_atencion(
        trabajadores
    )

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

    script = generar_script_completo(
        trabajadores
    )

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
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )