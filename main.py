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
# MAPEO DE DEPARTAMENTOS PARA USUARIOS
# ============================================================

# Mapeo entre id_departamento (tablas) y departamento_usuario (catálogo)
MAPEO_DEPARTAMENTOS = {
    30: 3,  # LA PAZ → departamento_usuario = 3
    31: 2,  # COCHABAMBA → departamento_usuario = 2
    32: 1   # SANTA CRUZ → departamento_usuario = 1
}


# ============================================================
# CATÁLOGO DE USUARIOS POR DEPARTAMENTO Y TIPO DE TRÁMITE
# ============================================================
# ============================================================
# CATÁLOGO DE USUARIOS POR DEPARTAMENTO Y TIPO DE TRÁMITE
# ============================================================

USUARIOS = {
    # ============================================================
    # LA PAZ (departamento_usuario = 1 → id_departamento = 30)
    # ============================================================
    289: {
        "nombre": "Cesar Dereck Vasquez Gutierrez",
        "ci": "5362946",
        "tipo_tramite": [174],
        "departamento_usuario": 1  # ✅ LA PAZ
    },
    270: {
        "nombre": "Teufilo Avendaño Tejerina",
        "ci": "6318790",
        "tipo_tramite": [173],
        "departamento_usuario": 1  # ✅ LA PAZ
    },
    1133: {
        "nombre": "Katia Aguilar Orellana",
        "ci": "5869915",
        "tipo_tramite": [173],
        "departamento_usuario": 1  # ✅ LA PAZ
    },
    # ============================================================
    # COCHABAMBA (departamento_usuario = 2 → id_departamento = 31)
    # ============================================================
    1130: {
        "nombre": "Cristina Silvia Orellana Cardozo",
        "ci": "5291854",
        "tipo_tramite": [173, 174],
        "departamento_usuario": 2  # ✅ COCHABAMBA
    },
    1233: {
        "nombre": "Igor Nataniel Bernal Flores",
        "ci": "5725232",
        "tipo_tramite": [173, 174],
        "departamento_usuario": 2  # ✅ COCHABAMBA
    },
    # ============================================================
    # SANTA CRUZ (departamento_usuario = 3 → id_departamento = 32)
    # ============================================================
    1102: {
        "nombre": "Patricia Ivana Guachalla Morales",
        "ci": "14021936",
        "tipo_tramite": [174],
        "departamento_usuario": 3  # ✅ SANTA CRUZ
    },
    244: {
        "nombre": "Charlie Giovani Huarca Huayhua",
        "ci": "8365847",
        "tipo_tramite": [173],
        "departamento_usuario": 3  # ✅ SANTA CRUZ
    },
    253: {
        "nombre": "Ruth Remy Quisbert Soria",
        "ci": "2398637",
        "tipo_tramite": [174],
        "departamento_usuario": 3  # ✅ SANTA CRUZ
    }
}
def obtener_usuarios_filtrados(id_departamento, id_tipo_tramite):
    """Obtiene los usuarios que atienden en un departamento específico
    Y que pueden atender el tipo de trámite seleccionado"""
    departamento_usuario = MAPEO_DEPARTAMENTOS.get(id_departamento)
    if not departamento_usuario:
        return []
    usuarios = []
    for uid, datos in USUARIOS.items():
        if datos["departamento_usuario"] == departamento_usuario:
            if id_tipo_tramite in datos["tipo_tramite"]:
                usuarios.append({
                    "id": uid,
                    "nombre": datos["nombre"],
                    "ci": datos["ci"],
                    "tipo_tramite": datos["tipo_tramite"]
                })
    return usuarios


# ============================================================
# CORRELATIVO INTERNO DE PLANILLA
# ============================================================

CORRELATIVO_FILE = os.path.join(DATA_FOLDER, "correlativo_planillas.json")


def obtener_siguiente_planilla_id():
    ultimo = 0
    if os.path.exists(CORRELATIVO_FILE):
        try:
            with open(CORRELATIVO_FILE, "r", encoding="utf-8") as f:
                contenido = json.load(f)
            ultimo = int(contenido.get("ultimo", 0))
        except Exception:
            ultimo = 0
    siguiente = ultimo + 1
    with open(CORRELATIVO_FILE, "w", encoding="utf-8") as f:
        json.dump({"ultimo": siguiente}, f, ensure_ascii=False, indent=2)
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
        ruta = os.path.join(PLANILLAS_FOLDER, archivo)
        try:
            with open(ruta, "r", encoding="utf-8") as f:
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
    return os.path.join(PLANILLAS_FOLDER, f"{planilla_id}.json")


def guardar_planilla(planilla_id, datos):
    with open(ruta_planilla(planilla_id), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def cargar_planilla(planilla_id=None):
    if planilla_id is None:
        planilla_id = session.get("planilla_id")
    if not planilla_id:
        return None
    ruta = ruta_planilla(planilla_id)
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def actualizar_planilla(datos):
    planilla_id = datos.get("planilla_id")
    if not planilla_id:
        return
    guardar_planilla(planilla_id, datos)


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
    if texto.lower() in ["nan", "none", "nat", "n/a", "na"]:
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
            resultado.append(f"{nombre}_{contador[nombre]}")
    return resultado


# ============================================================
# DETECTAR ENCABEZADO
# ============================================================

def detectar_fila_encabezado(df):
    palabras = [
        "C.I", "CI", "CARNET", "DOCENTE", "NOMBRE", "APELLIDO",
        "TELEFONO", "TELÉFONO", "CELULAR", "RELACION", "RELACIÓN",
        "DIRECCION", "DIRECCIÓN", "CODIGO PERSONA", "CÓDIGO PERSONA",
        "ID_PERSONA", "COD_TRAM", "COD TRAM", "ID_TRAMITE", "ID TRAMITE",
        "HORA INICIO", "HORA FIN"
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
                if palabra in valor or valor in palabra:
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
            return limpiar_valor(fila.get(columna, ""))
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
            "DOCENTE", "NOMBRE", "NOMBRE COMPLETO", "NOMBRE_COMPLETO"
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
# TRABAJADORES DEL BLOQUE ACTUAL
# ============================================================

def trabajadores_actuales():
    datos = cargar_planilla()
    if not datos:
        return []
    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))
    return [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]


# ============================================================
# PANTALLAS (ROUTES HTML)
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
    return render_template("pantalla2_tipo.html", step=2)


@app.route("/continuar")
def continuar():
    if not session.get("planilla_id"):
        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=3
        )
    return render_template("pantalla3_continuar.html", step=3)


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
    return render_template("pantalla5_persona.html", step=5)


@app.route("/codigo")
def codigo():
    if not session.get("planilla_id"):
        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=6
        )
    return render_template("pantalla6_codigo.html", step=6)


@app.route("/idtramite")
def idtramite():
    if not session.get("planilla_id"):
        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=7
        )
    return render_template("pantalla7_idtramite.html", step=7)


@app.route("/script")
def script():
    if not session.get("planilla_id"):
        return render_template(
            "error.html",
            mensaje="Primero debe cargar un Excel",
            step=8
        )
    return render_template("pantalla8_script.html", step=8)


# ============================================================
# PASO 1 - CARGAR EXCEL
# ============================================================

@app.route("/api/upload", methods=["POST"])
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

    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in [".xlsx", ".xls"]:
        return jsonify({
            "success": False,
            "error": "Use un archivo Excel .xlsx o .xls."
        }), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)

    try:
        file.save(filepath)
        df_raw = pd.read_excel(filepath, header=None, dtype=str, keep_default_na=False)
        if df_raw.empty:
            return jsonify({
                "success": False,
                "error": "El Excel está vacío."
            }), 400

        fila_encabezado = detectar_fila_encabezado(df_raw)
        encabezados = [limpiar_valor(v) for v in df_raw.iloc[fila_encabezado].tolist()]
        encabezados = generar_columnas_unicas(encabezados)

        df = df_raw.iloc[fila_encabezado + 1:].copy()
        df.columns = encabezados
        df = df.reset_index(drop=True)
        df = df[df.apply(lambda fila: any(limpiar_valor(v) != "" for v in fila), axis=1)]
        df = df.reset_index(drop=True)

        trabajadores = []
        filas_excel = []

        for indice, fila in df.iterrows():
            fila_excel = {}
            for columna in df.columns:
                fila_excel[columna] = limpiar_valor(fila[columna])
            trabajador = construir_trabajador(indice + 1, fila_excel)
            trabajadores.append(trabajador)
            filas_excel.append(fila_excel)

        if not trabajadores:
            return jsonify({
                "success": False,
                "error": "No se encontraron trabajadores."
            }), 400

        planilla_id = obtener_siguiente_planilla_id()

        datos = {
            "planilla_id": planilla_id,
            "archivo_nombre": file.filename,
            "fecha_carga": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fila_encabezado": fila_encabezado + 1,
            "columnas_excel": list(df.columns),
            "filas_excel": filas_excel,
            "trabajadores": trabajadores,
            "total_trabajadores": len(trabajadores),
            "cantidad_procesar": 0,
            "desde_trabajador": 1,
            "hasta_trabajador": 0,
            "tipo_proceso": None,
            "empresa": "",
            "nit": "",
            "id_ticket": None,
            "codigo_ticket": None,
            "tipo_tramite": None,
            "departamento": None,
            "fecha": None,
            "hora_base": None,
            "hora_fin": None,
            "usuario_creacion": None,
            "id_funcionario": None,
            "id_empresa": None
        }

        guardar_planilla(planilla_id, datos)
        session.clear()
        session["planilla_id"] = planilla_id
        session.modified = True

        try:
            os.remove(filepath)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "planilla_id": planilla_id,
            "archivo": file.filename,
            "total": len(trabajadores),
            "fila_encabezado": fila_encabezado + 1,
            "columnas": list(df.columns),
            "filas": filas_excel,
            "trabajadores": trabajadores,
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

@app.route("/api/configurar_cantidad", methods=["POST"])
def configurar_cantidad():
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    valor = data.get("cantidad_procesar", data.get("cantidad", 0))
    try:
        cantidad = int(valor)
    except Exception:
        return jsonify({
            "success": False,
            "error": "La cantidad debe ser un número entero."
        }), 400

    total = len(datos.get("trabajadores", []))
    if cantidad <= 0:
        return jsonify({
            "success": False,
            "error": "La cantidad debe ser mayor que cero."
        }), 400
    if cantidad > total:
        return jsonify({
            "success": False,
            "error": f"La planilla contiene {total} trabajadores."
        }), 400

    desde = int(datos.get("desde_trabajador", 1))
    hasta = min(desde + cantidad - 1, total)

    datos["cantidad_procesar"] = hasta - desde + 1
    datos["hasta_trabajador"] = hasta

    actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "planilla_id": datos["planilla_id"],
        "total": total,
        "cantidad_procesar": datos["cantidad_procesar"],
        "desde": desde,
        "hasta": hasta,
        "pendientes": total - hasta
    })


# ============================================================
# PASO 3 - TIPO DE PLANILLA
# ============================================================

@app.route("/api/tipo", methods=["POST"])
def set_tipo():
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    tipo = str(data.get("tipo", data.get("tipo_planilla", ""))).strip().upper()

    equivalencias = {
        "CONTINUACIÓN": "CONTINUACION",
        "CONTINUACION": "CONTINUACION",
        "NUEVA": "NUEVA",
        "RECIENTE": "RECIENTE"
    }
    tipo = equivalencias.get(tipo, tipo)

    if tipo not in ["NUEVA", "RECIENTE", "CONTINUACION"]:
        return jsonify({
            "success": False,
            "error": "Tipo de planilla inválido."
        }), 400

    datos["tipo_proceso"] = tipo
    actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "tipo": tipo,
        "planilla_id": datos["planilla_id"]
    })


# ============================================================
# GUARDAR USUARIO CREACIÓN
# ============================================================

@app.route("/api/guardar_usuario_creacion", methods=["POST"])
def guardar_usuario_creacion():
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    usuario_creacion = data.get("usuario_creacion")

    if not usuario_creacion:
        return jsonify({
            "success": False,
            "error": "El usuario de creación es obligatorio."
        }), 400

    try:
        usuario_creacion = int(usuario_creacion)
        if usuario_creacion <= 0:
            return jsonify({
                "success": False,
                "error": "El usuario de creación debe ser un número positivo."
            }), 400
    except:
        return jsonify({
            "success": False,
            "error": "El usuario de creación debe ser un número entero."
        }), 400

    datos["usuario_creacion"] = usuario_creacion
    actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "usuario_creacion": usuario_creacion
    })


# ============================================================
# API: OBTENER USUARIOS FILTRADOS POR DEPARTAMENTO Y TIPO TRÁMITE
# ============================================================

@app.route("/api/usuarios_filtrados", methods=["GET"])
def usuarios_filtrados():
    """Retorna los usuarios disponibles según departamento y tipo de trámite"""
    
    id_departamento = request.args.get("id_departamento")
    id_tipo_tramite = request.args.get("id_tipo_tramite")
    
    if not id_departamento:
        return jsonify({
            "success": False,
            "error": "Debe especificar un departamento."
        }), 400
    
    if not id_tipo_tramite:
        return jsonify({
            "success": False,
            "error": "Debe especificar un tipo de trámite."
        }), 400
    
    try:
        id_departamento = int(id_departamento)
        id_tipo_tramite = int(id_tipo_tramite)
    except:
        return jsonify({
            "success": False,
            "error": "Los parámetros deben ser números."
        }), 400
    
    usuarios = obtener_usuarios_filtrados(id_departamento, id_tipo_tramite)
    
    depto_nombre = DEPARTAMENTOS.get(id_departamento, "Desconocido")
    tipo_nombre = TIPOS_TRAMITE.get(id_tipo_tramite, "Desconocido")
    
    return jsonify({
        "success": True,
        "usuarios": usuarios,
        "departamento": {
            "id": id_departamento,
            "nombre": depto_nombre
        },
        "tipo_tramite": {
            "id": id_tipo_tramite,
            "nombre": tipo_nombre
        }
    })


# ============================================================
# GUARDAR FUNCIONARIO (ID_USUARIO)
# ============================================================

@app.route("/api/guardar_funcionario", methods=["POST"])
def guardar_funcionario():
    """Guarda el ID del funcionario que atiende en la planilla"""
    
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    id_funcionario = data.get("id_funcionario")

    if not id_funcionario:
        return jsonify({
            "success": False,
            "error": "Debe seleccionar un funcionario."
        }), 400

    try:
        id_funcionario = int(id_funcionario)
        if id_funcionario <= 0:
            return jsonify({
                "success": False,
                "error": "El funcionario debe ser un número positivo."
            }), 400
    except:
        return jsonify({
            "success": False,
            "error": "El funcionario debe ser un número entero."
        }), 400

    datos["id_funcionario"] = id_funcionario
    actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "id_funcionario": id_funcionario
    })


# ============================================================
# GUARDAR ID_EMPRESA
# ============================================================

@app.route("/api/guardar_id_empresa", methods=["POST"])
def guardar_id_empresa():
    """Guarda el ID_EMPRESA en la planilla"""
    
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    id_empresa = data.get("id_empresa")

    if not id_empresa:
        return jsonify({
            "success": False,
            "error": "El ID_EMPRESA es obligatorio."
        }), 400

    try:
        id_empresa = int(id_empresa)
        if id_empresa <= 0:
            return jsonify({
                "success": False,
                "error": "El ID_EMPRESA debe ser un número positivo."
            }), 400
    except:
        return jsonify({
            "success": False,
            "error": "El ID_EMPRESA debe ser un número entero."
        }), 400

    datos["id_empresa"] = id_empresa
    actualizar_planilla(datos)

    return jsonify({
        "success": True,
        "id_empresa": id_empresa
    })


# ============================================================
# PASO 4 - GENERAR TICKET
# ============================================================

@app.route('/api/generar_ticket', methods=['POST'])
def generar_script_ticket():
    """Genera el script del ticket - SOLO HORA INICIO (el sistema calcula el resto)
    NO genera id_ticket automáticamente, se asignará en el Paso 7
    """
    
    try:
        data = request.get_json(silent=True) or {}
        
        # VALIDAR TODOS LOS CAMPOS OBLIGATORIOS
        codigo = data.get("codigo", "").strip()
        if not codigo:
            return jsonify({
                "success": False,
                "error": "El campo CÓDIGO es obligatorio. Ejemplo: RF-2026-001"
            }), 400
        
        fecha = data.get("fecha", "").strip()
        if not fecha:
            return jsonify({
                "success": False,
                "error": "El campo FECHA es obligatorio. Ejemplo: 2026-08-27"
            }), 400
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except:
            return jsonify({
                "success": False,
                "error": "Formato de fecha inválido. Use YYYY-MM-DD"
            }), 400
        
        hora_inicio = data.get("hora_inicio", "").strip()
        if not hora_inicio:
            return jsonify({
                "success": False,
                "error": "El campo HORA INICIO es obligatorio. Ejemplo: 09:30"
            }), 400
        
        # Validar y normalizar hora
        try:
            datetime.strptime(hora_inicio, "%H:%M:%S")
        except:
            try:
                datetime.strptime(hora_inicio, "%H:%M")
                hora_inicio = hora_inicio + ":00"
            except:
                return jsonify({
                    "success": False,
                    "error": "Formato de hora inválido. Use HH:MM o HH:MM:SS"
                }), 400
        
        razon_social = data.get("razon_social", "").strip()
        if not razon_social:
            return jsonify({
                "success": False,
                "error": "El campo RAZÓN SOCIAL es obligatorio."
            }), 400
        
        nit = data.get("nit", "").strip()
        if not nit:
            return jsonify({
                "success": False,
                "error": "El campo NIT es obligatorio."
            }), 400
        
        tipo_tramite = data.get("tipo_tramite")
        if not tipo_tramite:
            return jsonify({
                "success": False,
                "error": "Debe seleccionar un TIPO DE TRÁMITE."
            }), 400
        try:
            tipo_tramite = int(tipo_tramite)
            if tipo_tramite not in [173, 174, 175]:
                return jsonify({
                    "success": False,
                    "error": "Tipo de trámite inválido. Opciones: 173, 174, 175"
                }), 400
        except:
            return jsonify({
                "success": False,
                "error": "El TIPO DE TRÁMITE debe ser un número."
            }), 400
        
        departamento = data.get("departamento")
        if not departamento:
            return jsonify({
                "success": False,
                "error": "Debe seleccionar un DEPARTAMENTO."
            }), 400
        try:
            departamento = int(departamento)
            if departamento not in [30, 31, 32]:
                return jsonify({
                    "success": False,
                    "error": "Departamento inválido. Opciones: 30, 31, 32"
                }), 400
        except:
            return jsonify({
                "success": False,
                "error": "El DEPARTAMENTO debe ser un número."
            }), 400
        
        usuario_creacion = data.get("usuario_creacion")
        if not usuario_creacion:
            return jsonify({
                "success": False,
                "error": "El USUARIO CREACIÓN es obligatorio."
            }), 400
        try:
            usuario_creacion = int(usuario_creacion)
            if usuario_creacion <= 0:
                return jsonify({
                    "success": False,
                    "error": "El USUARIO CREACIÓN debe ser un número positivo."
                }), 400
        except:
            return jsonify({
                "success": False,
                "error": "El USUARIO CREACIÓN debe ser un número entero."
            }), 400
        
        cantidad = data.get("cantidad_trabajadores") or data.get("cantidad")
        if not cantidad:
            return jsonify({
                "success": False,
                "error": "Debe indicar la CANTIDAD de trabajadores."
            }), 400
        try:
            cantidad = int(cantidad)
            if cantidad <= 0:
                return jsonify({
                    "success": False,
                    "error": "La cantidad debe ser mayor que cero."
                }), 400
        except:
            return jsonify({
                "success": False,
                "error": "La CANTIDAD debe ser un número entero."
            }), 400
        
        # CARGAR PLANILLA
        datos_planilla = cargar_planilla()
        if not datos_planilla:
            return jsonify({
                "success": False,
                "error": "No existe una planilla cargada."
            }), 400
        
        trabajadores = datos_planilla.get("trabajadores", [])
        desde = int(datos_planilla.get("desde_trabajador", 1))
        hasta = int(datos_planilla.get("hasta_trabajador", 0))
        
        if not trabajadores:
            return jsonify({
                "success": False,
                "error": "No hay trabajadores en la planilla."
            }), 400
        
        total_disponibles = len([t for t in trabajadores if desde <= int(t.get("nro", 0)) <= hasta])
        if cantidad > total_disponibles:
            return jsonify({
                "success": False,
                "error": f"Solo hay {total_disponibles} trabajadores disponibles."
            }), 400
        
        trabajadores_bloque = [
            t for t in trabajadores 
            if desde <= int(t.get("nro", 0)) <= hasta
        ][:cantidad]
        
        if not trabajadores_bloque:
            return jsonify({
                "success": False,
                "error": "No hay trabajadores en el bloque actual."
            }), 400
        
        # ⭐⭐⭐ ELIMINADO: id_ticket = generar_id_ticket_sistema()
        # AHORA SE USA "PENDIENTE" COMO ID_TICKET TEMPORAL
        id_ticket = "PENDIENTE"  # Temporal, se reemplazará en el Paso 7
        
        hora_base_dt = datetime.strptime(hora_inicio, "%H:%M:%S")
        MINUTOS_POR_PERSONA = 4
        MINUTOS_ATENCION = 3
        ultima_hora_fin = None
        
        for idx, trabajador in enumerate(trabajadores_bloque):
            hora_actual = hora_base_dt + timedelta(minutes=(idx * MINUTOS_POR_PERSONA))
            hora_fin_trabajador = hora_actual + timedelta(minutes=MINUTOS_ATENCION)
            if idx == len(trabajadores_bloque) - 1:
                ultima_hora_fin = hora_fin_trabajador
            trabajador["id_ticket"] = id_ticket  # "PENDIENTE"
            trabajador["hora_inicio"] = hora_actual.strftime("%H:%M:%S")
            trabajador["hora_fin"] = hora_fin_trabajador.strftime("%H:%M:%S")
            trabajador["procesar"] = True
        
        hora_fin_script = ultima_hora_fin.strftime("%H:%M:%S") if ultima_hora_fin else "00:00:00"
        
        # GUARDAR EN LA PLANILLA
        for i, trabajador in enumerate(datos_planilla["trabajadores"]):
            nro = int(trabajador.get("nro", 0))
            if desde <= nro <= hasta:
                for t_actualizado in trabajadores_bloque:
                    if int(t_actualizado.get("nro", 0)) == nro:
                        datos_planilla["trabajadores"][i] = t_actualizado
                        break
        
        datos_planilla["id_ticket"] = id_ticket  # "PENDIENTE"
        datos_planilla["codigo_ticket"] = str(codigo)
        datos_planilla["fecha"] = str(fecha)
        datos_planilla["hora_base"] = str(hora_inicio)
        datos_planilla["hora_fin"] = str(hora_fin_script)
        datos_planilla["empresa"] = str(razon_social)
        datos_planilla["nit"] = str(nit)
        datos_planilla["tipo_tramite"] = tipo_tramite
        datos_planilla["departamento"] = departamento
        datos_planilla["usuario_creacion"] = usuario_creacion
        datos_planilla["cantidad_procesar"] = len(trabajadores_bloque)
        datos_planilla["hasta_trabajador"] = hasta
        
        actualizar_planilla(datos_planilla)
        
        # GENERAR SOLO SCRIPT DEL TICKET (con id_ticket = "PENDIENTE")
        script_ticket = generar_script_insert_ticket(
            trabajadores_bloque,
            id_ticket,  # "PENDIENTE"
            codigo,
            fecha,
            departamento,
            tipo_tramite,
            usuario_creacion,
            hora_inicio,
            hora_fin_script
        )
        
        return jsonify({
            "success": True,
            "mensaje": f"Ticket configurado para {len(trabajadores_bloque)} trabajadores. ID_TICKET: PENDIENTE (se asignará en el Paso 7)",
            "id_ticket": id_ticket,
            "id_ticket_pendiente": True,  # ⭐ Indicador de que falta el id_ticket real
            "codigo": str(codigo),
            "fecha": str(fecha),
            "hora_inicio": str(hora_inicio),
            "hora_fin": str(hora_fin_script),
            "tipo_tramite": tipo_tramite,
            "departamento": departamento,
            "usuario_creacion": usuario_creacion,
            "razon_social": str(razon_social),
            "nit": str(nit),
            "cantidad": len(trabajadores_bloque),
            "trabajadores": trabajadores_bloque,
            "script_ticket": script_ticket,
            "advertencia": "⚠️ ID_TICKET es 'PENDIENTE'. Debe ingresar el ID_TICKET real en el Paso 7."
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Error al generar ticket: {str(e)}"
        }), 500

# ============================================================
# FUNCIÓN: GENERAR SCRIPT INSERT TICKET
# ============================================================

def generar_script_insert_ticket(trabajadores, id_ticket, codigo, fecha, departamento, tipo_tramite, usuario_creacion, hora_inicio_total, hora_fin_total):
    if not trabajadores:
        return "-- No hay trabajadores para generar tickets"
    
    total_trabajadores = len(trabajadores)
    
    return f"""-- ============================================================
-- SCRIPT DE TICKET
-- ID_TICKET: {id_ticket}
-- CÓDIGO: {codigo}
-- FECHA: {fecha}
-- DEPARTAMENTO: {departamento}
-- TIPO TRÁMITE: {tipo_tramite}
-- USUARIO CREACIÓN: {usuario_creacion}
-- TOTAL TRABAJADORES: {total_trabajadores}
-- HORA INICIO (1er trabajador): {hora_inicio_total}
-- HORA FIN (último trabajador): {hora_fin_total}
-- ============================================================
INSERT INTO mteps_d_tickets.dtck_ticket
(codigo, id_departamento, id_tipo_tramite, nro_tramites, estado, transaccion, usuario_creacion, usuario_modificacion, 
fecha_creacion, fecha_modificacion, observacion, fecha_solicitud_ticket, fecha_atencion, hora_inicio, hora_fin, notificado, correo_notificado)

VALUES('{escapar_sql(codigo)}', {departamento}, {tipo_tramite}, {total_trabajadores}, 'SOLICITADO', 'SOLICITAR_D_TICKET', {usuario_creacion}, NULL, now(), NULL, NULL, now(), '{escapar_sql(fecha)}', '{escapar_sql(hora_inicio_total)}', '{escapar_sql(hora_fin_total)}', false, NULL);"""


# ============================================================
# FUNCIÓN: GENERAR SCRIPT PERSONAS (ext_persona)
# ============================================================

def generar_script_personas(trabajadores):
    """
    Genera el script SQL para insertar personas en externos_mteps.ext_persona
    - USA externos_mteps.f_secuencial('ext_persona') para el ID_PERSONA
    - CADA REGISTRO EN SU PROPIA LÍNEA
    """
    
    if not trabajadores:
        return "-- No hay trabajadores para generar personas"

    # Obtener usuario_creacion de la planilla
    datos_planilla = cargar_planilla()
    usuario = datos_planilla.get("usuario_creacion", 1155) if datos_planilla else 1155

    valores = []
    
    for t in trabajadores:
        nombre = escapar_sql(t.get("nombre", ""))
        ci = escapar_sql(t.get("ci", ""))
        relacion = escapar_sql(t.get("relacion") or t.get("cargo", ""))
        direccion = escapar_sql(t.get("direccion", ""))
        telefono = escapar_sql(t.get("telefono", ""))
        
        # ID_PERSONA automático con f_secuencial
        id_persona_sql = "externos_mteps.f_secuencial('ext_persona')"
        
        # CADA REGISTRO EN SU PROPIA LÍNEA - CON ESPACIADO
        valor = f"""({id_persona_sql}, '{nombre}', '', '', 203, '{ci}', '', NULL, '', NULL, NULL, NULL, NULL, NULL, 'ELABORADO', NULL, NULL, '{relacion}', NULL, '{direccion}', '{telefono}', NULL, {usuario}, {usuario}, now(), now(), 'ADICIONAR', '', NULL)"""
        
        valores.append(valor)

    # UNIR CADA REGISTRO CON ", \n" PARA QUE CADA UNO ESTÉ EN SU LÍNEA
    return f"""-- ============================================================
-- 2. INSERTAR PERSONAS (ID_PERSONA con f_secuencial)
-- ============================================================

INSERT INTO externos_mteps.ext_persona
(id_persona, nombre_completo, paterno, materno, tipo_documento, nro_documento, complemento, lugar_expedicion, nacionalidad, genero, fecha_nacimiento, estado_segip, fecha_verificacion, fecha_expiracion, estado, observacion_segip, lugar_nacimiento, relacion_entidad, ocupacion, domicilio, telefono, correo, usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, transaccion, observacion, edad)
VALUES
{",\n".join(valores)};
"""


# ============================================================
# PASO 5 - GENERAR SCRIPT DE PERSONAS (ext_persona) - RUTA
# ============================================================

@app.route("/api/generar_personas", methods=["POST"])
def generar_personas():
    try:
        datos = cargar_planilla()
        if not datos:
            return jsonify({
                "success": False,
                "error": "No existe una planilla cargada."
            }), 400

        id_ticket = datos.get("id_ticket")
        if not id_ticket:
            return jsonify({
                "success": False,
                "error": "Primero debe generar el ticket en el Paso 4."
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

        script = generar_script_personas(procesados)

        return jsonify({
            "success": True,
            "script": script,
            "total": len(procesados)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Error al generar personas: {str(e)}"
        }), 500


# ============================================================
# PASO 5 - REGISTRAR ID_PERSONA (MANUAL)
# ============================================================
@app.route("/api/registrar_personas", methods=["POST"])
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
    
    # ⭐ GENERAR SCRIPT COMPLETO (con manejo de errores)
    try:
        script_completo = generar_script_completo(procesados)
    except Exception as e:
        script_completo = f"-- Error al generar script completo: {str(e)}"
    
    return jsonify({
        "success": True,
        "registrados": registrados,
        "procesados": procesados,
        "trabajadores": trabajadores,
        "mensaje": f"Se registraron {registrados} ID_PERSONA correlativos (desde {primer_id} hasta {primer_id + registrados - 1}).",
        "script_completo": script_completo
    })


# ============================================================
# PASO 6 - GENERAR SCRIPT DE TRM_TRAMITE
# ============================================================
# ============================================================
# PASO 6 - ASIGNAR ID_PERSONA DESDE LISTA (COPY-PASTE)
# ============================================================

@app.route("/api/asignar_id_persona_lista", methods=["POST"])
def asignar_id_persona_lista():
    """Asigna ID_PERSONA a los trabajadores y genera SOLO el script de trm_tramite"""
    
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    lista_ids = data.get("lista_ids", "").strip()
    
    if not lista_ids:
        return jsonify({
            "success": False,
            "error": "Debe ingresar la lista de ID_PERSONA."
        }), 400
    
    # Procesar la lista
    ids = []
    for line in lista_ids.split('\n'):
        line = line.strip()
        if line:
            try:
                id_num = int(line)
                if id_num > 0:
                    ids.append(id_num)
            except ValueError:
                pass
    
    if not ids:
        return jsonify({
            "success": False,
            "error": "No se encontraron ID_PERSONA validos en la lista."
        }), 400
    
    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))
    
    bloque = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]
    
    if len(ids) != len(bloque):
        return jsonify({
            "success": False,
            "error": f"La lista tiene {len(ids)} ID_PERSONA, pero hay {len(bloque)} trabajadores."
        }), 400
    
    # Asignar IDs
    for idx, trabajador in enumerate(bloque):
        trabajador["id_persona"] = ids[idx]
    
    datos["trabajadores"] = trabajadores
    actualizar_planilla(datos)
    
    # Generar SOLO script de trm_tramite
    try:
        usuario_creacion = datos.get("usuario_creacion", 1155)
        razon_social = datos.get("empresa", "")
        nit = datos.get("nit", "")
        id_empresa = datos.get("id_empresa", 27424)
        id_ticket = datos.get("id_ticket")
        
        script = generar_script_trm_tramite(
            bloque,
            id_ticket,
            usuario_creacion,
            razon_social,
            nit,
            id_empresa
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        script = f"-- Error al generar script trm_tramite: {str(e)}"
    
    min_id = min(ids) if ids else 0
    max_id = max(ids) if ids else 0
    rango = f"{min_id} - {max_id}"
    
    return jsonify({
        "success": True,
        "asignados": len(ids),
        "total": len(bloque),
        "rango": rango,
        "ids": ids,
        "trabajadores": bloque,
        "script": script,
        "mensaje": f"Se asignaron {len(ids)} ID_PERSONA correctamente."
    })


# ============================================================
# PASO 7 - ASIGNAR ID_TRAMITE DESDE LISTA (COPY-PASTE)
# ============================================================

@app.route("/api/generar_trm_tramite", methods=["POST"])
def generar_trm_tramite():
    """Genera el script de trm_tramite usando los ID_PERSONA registrados"""
    
    try:
        datos = cargar_planilla()
        if not datos:
            return jsonify({
                "success": False,
                "error": "No existe una planilla cargada."
            }), 400

        # VALIDAR FUNCIONARIO
        id_funcionario = datos.get("id_funcionario")
        if not id_funcionario:
            return jsonify({
                "success": False,
                "error": "Primero debe seleccionar un funcionario en el Paso 6."
            }), 400

        id_ticket = datos.get("id_ticket")
        if not id_ticket:
            return jsonify({
                "success": False,
                "error": "Primero debe generar el ticket en el Paso 4."
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

        # Verificar que todos tengan ID_PERSONA
        sin_id = [t for t in procesados if not t.get("id_persona")]
        if sin_id:
            return jsonify({
                "success": False,
                "error": f"Hay {len(sin_id)} trabajadores sin Código Persona. Primero registre los Códigos Persona."
            }), 400

        # Obtener datos de la planilla
        usuario_creacion = datos.get("usuario_creacion", 1155)
        razon_social = datos.get("empresa", "")
        nit = datos.get("nit", "")
        id_empresa = datos.get("id_empresa", 27424)

        # Generar script de trm_tramite
        script = generar_script_trm_tramite(
            procesados,
            id_ticket,
            usuario_creacion,
            razon_social,
            nit,
            id_empresa
        )

        return jsonify({
            "success": True,
            "script": script,
            "total": len(procesados),
            "id_funcionario": id_funcionario
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Error al generar trm_tramite: {str(e)}"
        }), 500


def generar_script_trm_tramite(trabajadores, id_ticket, usuario_creacion, razon_social, nit, id_empresa=27424):
    """
    Genera el script SQL para insertar en mteps_tramites.trm_tramite
    - usuario_creacion y usuario_modificacion = ID_FUNCIONARIO seleccionado
    """
    
    if not trabajadores:
        return "-- No hay trabajadores para generar trm_tramite"

    # OBTENER EL ID_FUNCIONARIO DE LA PLANILLA
    datos_planilla = cargar_planilla()
    id_funcionario = datos_planilla.get("id_funcionario") if datos_planilla else None
    
    # Si no hay funcionario, usar el usuario_creacion como fallback
    if not id_funcionario:
        id_funcionario = usuario_creacion

    valores = []
    
    for t in trabajadores:
        id_persona = t.get("id_persona")
        id_persona_sql = str(id_persona) if id_persona else "NULL"
        
        valor = f"""(mteps_tramites.f_secuencial('trm_tramite'),'TRM/2026-'||((SELECT COALESCE(MAX(SUBSTRING(codigo_tramite FROM '[0-9]+$')::integer),0) FROM mteps_tramites.trm_tramite WHERE codigo_tramite LIKE 'TRM/2026-%') + 1), 174, NULL, 'ADICIONAR_TICKET', 'ELABORADO_TICKET', {id_funcionario}, {id_funcionario}, now(), now(), {id_empresa}, {id_persona_sql}, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '{escapar_sql(nit)}', NULL, NULL, NULL, '{escapar_sql(razon_social)}', false, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)"""
        
        valores.append(valor)

    return f"""-- ============================================================
-- INSERTA TRAMITE - LA SECUENCIA RETORNADA ANTERIORMENTE REEMPLAZAR EN ID_PERSONA
-- ============================================================
-- ID_TICKET: {id_ticket}
-- TOTAL TRABAJADORES: {len(trabajadores)}
-- USUARIO CREACIÓN/MODIFICACIÓN: {id_funcionario} (funcionario seleccionado)
-- ============================================================

INSERT INTO mteps_tramites.trm_tramite
(id_tramite, codigo_tramite, id_clasificador_tramite, monto_total_multa, transaccion, estado, usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, id_empresa, id_persona, periodo_planilla, gestion_planilla, minera, dias_retraso, monto_calculo, nro_trabajadores, fecha_pago_prima, id_detalle_finiquito, resolucion_administrativa, relacion_entidad, nro_fojas, observacion, json_requisitos, nhr_tramite_relacionado, nur_sigec, nit, matricula_comercio, codigo_multa, codigo_manual, razon_social, persona_natural, codigo_visado, declarado_fc, codigo_fc, id_ra, id_sucursal, nro_hojas_foleadas, descripcion_sucursal, nro_hojas_leg, documento_leg, nro_boleta_err, fecha_boleta_err, motivo_err, monto_err, c21_erroneos, c31_erroneos, devuelto_err, desc_result_err, id_imputacion, mnt_tipo_cambio, pais_visado)
VALUES
{",\n".join(valores)};
"""


# ============================================================
# PASO 6 - REGISTRAR COD_TRAM
# ============================================================

@app.route("/api/registrar_codigos", methods=["POST"])
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
# PASO 7 - ASIGNAR ID_TRAMITE DESDE LISTA (COPY-PASTE)
# ============================================================


# ============================================================
# PASO 7 - GENERAR SCRIPT DE ATENCIÓN
# ============================================================

@app.route("/api/generar_atencion", methods=["POST"])
def generar_atencion():
    """Genera el script de dtck_ticket_atencion_tramite"""
    
    try:
        datos = cargar_planilla()
        if not datos:
            return jsonify({
                "success": False,
                "error": "No existe una planilla cargada."
            }), 400

        id_ticket = datos.get("id_ticket")
        if not id_ticket:
            return jsonify({
                "success": False,
                "error": "Primero debe generar el ticket en el Paso 4."
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

        # Verificar que todos tengan ID_TRAMITE
        sin_id = [t for t in procesados if not t.get("id_tramite")]
        if sin_id:
            return jsonify({
                "success": False,
                "error": f"Hay {len(sin_id)} trabajadores sin ID_TRAMITE. Primero registre los ID_TRAMITE."
            }), 400

        # Generar script de atención
        script = generar_script_atencion(procesados)

        return jsonify({
            "success": True,
            "script": script,
            "total": len(procesados)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Error al generar atención: {str(e)}"
        }), 500
# ============================================================
# PASO 7 - REGISTRAR ID_TRAMITE
# ============================================================

@app.route("/api/registrar_idtramites", methods=["POST"])
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
# PASO 7 - ASIGNAR ID_TRAMITE DESDE LISTA (COPY-PASTE)
# ============================================================
# ============================================================
# PREVISUALIZACIÓN COMPLETA
# ============================================================

@app.route("/api/previsualizacion_completa", methods=["GET"])
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

@app.route("/api/previsualizacion", methods=["GET"])
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
        "planilla_id": datos.get("planilla_id"),
        "archivo": datos.get("archivo_nombre"),
        "columnas": datos.get("columnas_excel", []),
        "filas": datos.get("filas_excel", []),
        "todos": trabajadores,
        "procesados": procesados,
        "pendientes": pendientes,
        "total": len(trabajadores),
        "cantidad_procesada": len(procesados),
        "cantidad_pendiente": len(pendientes),
        "desde": desde,
        "hasta": hasta,
        "id_ticket": datos.get("id_ticket"),
        "razon_social": datos.get("empresa", ""),
        "nit": datos.get("nit", "")
    })


# ============================================================
# ESTADO
# ============================================================
@app.route("/api/estado", methods=["GET"])
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

    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))

    procesados = [t for t in trabajadores if desde <= int(t.get("nro", 0)) <= hasta]
    pendientes = [t for t in trabajadores if int(t.get("nro", 0)) > hasta]

    # Obtener nombres de departamento y tipo de trámite
    id_departamento = datos.get("departamento", 32)
    id_tipo_tramite = datos.get("tipo_tramite", 174)
    
    departamento_nombre = DEPARTAMENTOS.get(id_departamento, "Desconocido")
    tipo_tramite_nombre = TIPOS_TRAMITE.get(id_tipo_tramite, "Desconocido")

    return jsonify({
        "success": True,
        "planilla_id": datos.get("planilla_id"),
        "archivo": datos.get("archivo_nombre"),
        "total": len(trabajadores),
        "cantidad_procesar": len(procesados),
        "pendientes": len(pendientes),
        "desde": desde,
        "hasta": hasta,
        "id_ticket": datos.get("id_ticket"),
        "tipo": datos.get("tipo_proceso"),
        "empresa": datos.get("empresa", ""),
        "razon_social": datos.get("empresa", ""),
        "nit": datos.get("nit", ""),
        "codigo_ticket": datos.get("codigo_ticket", "RF-001"),
        "fecha": datos.get("fecha"),
        "hora_inicio": datos.get("hora_base", "08:30:00"),
        "hora_fin": datos.get("hora_fin", "13:21:00"),
        "tipo_tramite": id_tipo_tramite,
        "tipo_tramite_nombre": tipo_tramite_nombre,  # ⭐ NUEVO
        "departamento": id_departamento,
        "departamento_nombre": departamento_nombre,  # ⭐ NUEVO
        "usuario_creacion": datos.get("usuario_creacion", 1155),
        "id_funcionario": datos.get("id_funcionario"),
        "id_empresa": datos.get("id_empresa"),
        "columnas": datos.get("columnas_excel", []),
        "filas": datos.get("filas_excel", []),
        "trabajadores": trabajadores,
        "procesados": procesados,
        "pendientes_lista": pendientes
    })

# ============================================================
# CONTINUAR PROCESO
# ============================================================

@app.route("/api/continuar_proceso", methods=["POST"])
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
            "mensaje": "No quedan trabajadores pendientes."
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
            "error": "La cantidad debe ser mayor que cero."
        }), 400

    nuevo_hasta = min(nuevo_desde + cantidad - 1, total)

    datos["desde_trabajador"] = nuevo_desde
    datos["cantidad_procesar"] = nuevo_hasta - nuevo_desde + 1
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
        "planilla_id": datos["planilla_id"],
        "desde": nuevo_desde,
        "hasta": nuevo_hasta,
        "cantidad_procesar": nuevo_hasta - nuevo_desde + 1,
        "pendientes": total - nuevo_hasta,
        "id_ticket": None,
        "trabajadores": trabajadores
    })


# ============================================================
# GUARDAR AVANCE
# ============================================================

@app.route("/api/guardar_avance", methods=["POST"])
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
        "planilla_id": datos.get("planilla_id"),
        "archivo": datos.get("archivo_nombre"),
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "procesados": hasta,
        "pendientes": max(total - hasta, 0),
        "id_ticket": datos.get("id_ticket")
    }

    archivo = os.path.join(DATA_FOLDER, "session_data.json")
    historial = []

    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                historial = json.load(f)
            if not isinstance(historial, list):
                historial = [historial]
        except Exception:
            historial = []

    historial.append(registro)

    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

    return jsonify({
        "success": True,
        "registro": registro
    })


# ============================================================
# HISTORIAL
# ============================================================

@app.route("/api/historial", methods=["GET"])
def historial():
    archivo = os.path.join(DATA_FOLDER, "session_data.json")
    if not os.path.exists(archivo):
        return jsonify({
            "success": True,
            "historial": []
        })

    try:
        with open(archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, list):
            datos = [datos]
        return jsonify({
            "success": True,
            "historial": datos
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# FUNCIÓN: GENERAR SCRIPT COD_TRAM
# ============================================================

def generar_script_codigos(trabajadores):
    script = """
-- ============================================================
-- 3. COD_TRAM
-- ============================================================

"""
    for t in trabajadores:
        codigo = t.get("codigo_tramite") or "PENDIENTE"
        script += f"""
-- TRABAJADOR #{t.get("nro")}
-- ID_TICKET: {t.get("id_ticket")}
-- ID_PERSONA: {t.get("id_persona")}
-- COD_TRAM: {codigo}

"""
    return script


# ============================================================
# FUNCIÓN: GENERAR SCRIPT ID_TRAMITE
# ============================================================

def generar_script_idtramites(trabajadores):
    script = """
-- ============================================================
-- 4. ID_TRAMITE
-- ============================================================

"""
    for t in trabajadores:
        id_tramite = t.get("id_tramite") or "PENDIENTE"
        codigo = t.get("codigo_tramite") or "PENDIENTE"
        script += f"""
-- TRABAJADOR #{t.get("nro")}
-- ID_TICKET: {t.get("id_ticket")}
-- ID_PERSONA: {t.get("id_persona")}
-- COD_TRAM: {codigo}
-- ID_TRAMITE: {id_tramite}

"""
    return script


# ============================================================
# FUNCIÓN: GENERAR SCRIPT ATENCIÓN
# ============================================================
def generar_script_atencion(trabajadores):
    """
    Genera el script SQL para insertar en mteps_d_tickets.dtck_ticket_atencion_tramite
    - FORMATO EXACTO: UNA SOLA LÍNEA POR REGISTRO
    - id_ticket: El ID_TICKET que ingresó el usuario (Paso 8)
    - id_tramite: El ID_TRAMITE asignado a cada trabajador (Paso 7)
    - id_usuario_asignado: El funcionario seleccionado (Paso 6)
    - usuario_creacion: El funcionario seleccionado (Paso 6)
    - usuario_modificacion: NULL
    """
    
    if not trabajadores:
        return ""
    
    # Obtener datos de la planilla
    datos_planilla = cargar_planilla()
    if not datos_planilla:
        return "-- No hay planilla cargada"
    
    # ⭐ ID_TICKET INGRESADO POR EL USUARIO
    id_ticket = datos_planilla.get("id_ticket")
    if not id_ticket:
        return "-- No hay ID_TICKET generado (ingréselo en el Paso 8)"
    
    # Obtener el funcionario seleccionado (Paso 6)
    id_funcionario = datos_planilla.get("id_funcionario", 981)
    
    # Obtener la fecha
    fecha = datos_planilla.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    
    valores = []
    
    for t in trabajadores:
        # Obtener id_tramite del trabajador (Paso 7)
        id_tramite = t.get("id_tramite")
        if not id_tramite or id_tramite in [None, "", "null"]:
            id_tramite_sql = "NULL"
        else:
            id_tramite_sql = str(id_tramite)
        
        # Obtener horas del trabajador
        hora_inicio = t.get("hora_inicio", "00:00:00")
        hora_fin = t.get("hora_fin", "00:00:00")
        
        # ⭐ FORMATO EXACTO: UNA SOLA LÍNEA POR REGISTRO
        valor = f"""({id_ticket}, {id_tramite_sql}, {id_funcionario}, '{escapar_sql(fecha)}', '{escapar_sql(hora_inicio)}', '{escapar_sql(hora_fin)}', 'INICIAL', 'SOLICITAR_D_TICKET', {id_funcionario}, NULL, now(), NULL, NULL)"""
        
        valores.append(valor)

    return f"""-- ============================================================
-- INSERTA ATENCION DE TRAMITE CON SECUENCIA DEVUELTA ANTERIOR INSERT EN ID_TRAMITE, ID_TICKET ES CORRELATIVO DEL PRIMER INSERT
-- ============================================================
-- ID_TICKET: {id_ticket}
-- TOTAL TRABAJADORES: {len(trabajadores)}
-- FUNCIONARIO QUE ATIENDE: {id_funcionario}
-- FECHA: {fecha}
-- ============================================================

INSERT INTO mteps_d_tickets.dtck_ticket_atencion_tramite
(id_ticket, id_tramite, id_usuario_asignado, fecha_atencion, hora_inicio, hora_fin, estado, transaccion, usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, observacion)
VALUES
{",\n".join(valores)};
"""
# ============================================================
# PASO 7 - ASIGNAR ID_TRAMITE DESDE LISTA (COPY-PASTE)
# ============================================================

@app.route("/api/asignar_id_tramite_lista", methods=["POST"])
def asignar_id_tramite_lista():
    """
    Asigna ID_TRAMITE a los trabajadores y genera el script de atencion.
    USA el ID_TICKET que el usuario ingresó en la pantalla 7.
    """
    
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    lista_ids = data.get("lista_ids", "").strip()
    id_ticket_usuario = str(data.get("id_ticket", "")).strip()
    
    # ============================================================
    # VALIDAR ID_TICKET INGRESADO POR EL USUARIO
    # ============================================================
    if not id_ticket_usuario:
        return jsonify({
            "success": False,
            "error": "Debe ingresar el ID_TICKET que generó el sistema externo."
        }), 400
    
    try:
        id_ticket = int(id_ticket_usuario)
        if id_ticket <= 0:
            return jsonify({
                "success": False,
                "error": "El ID_TICKET debe ser un número mayor a 0."
            }), 400
    except:
        return jsonify({
            "success": False,
            "error": "El ID_TICKET debe ser un número válido."
        }), 400
    
    # ============================================================
    # VALIDAR LISTA DE ID_TRAMITE
    # ============================================================
    if not lista_ids:
        return jsonify({
            "success": False,
            "error": "Debe ingresar la lista de ID_TRAMITE."
        }), 400
    
    # Procesar la lista de ID_TRAMITE
    ids = []
    for line in lista_ids.split('\n'):
        line = line.strip()
        if line:
            try:
                id_num = int(line)
                if id_num > 0:
                    ids.append(id_num)
            except ValueError:
                pass
    
    if not ids:
        return jsonify({
            "success": False,
            "error": "No se encontraron ID_TRAMITE validos en la lista."
        }), 400
    
    # ============================================================
    # OBTENER TRABAJADORES DEL BLOQUE
    # ============================================================
    trabajadores = datos.get("trabajadores", [])
    desde = int(datos.get("desde_trabajador", 1))
    hasta = int(datos.get("hasta_trabajador", 0))
    
    bloque = [
        t for t in trabajadores
        if desde <= int(t.get("nro", 0)) <= hasta
    ]
    
    if len(ids) != len(bloque):
        return jsonify({
            "success": False,
            "error": f"La lista tiene {len(ids)} ID_TRAMITE, pero hay {len(bloque)} trabajadores."
        }), 400
    
    # ============================================================
    # ASIGNAR ID_TRAMITE A CADA TRABAJADOR
    # ============================================================
    for idx, trabajador in enumerate(bloque):
        trabajador["id_tramite"] = ids[idx]
    
    # ============================================================
    # GUARDAR EL ID_TICKET INGRESADO POR EL USUARIO
    # ============================================================
    datos["id_ticket"] = id_ticket
    datos["id_ticket_usuario"] = id_ticket
    datos["fecha_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    datos["trabajadores"] = trabajadores
    
    actualizar_planilla(datos)
    
    # ============================================================
    # GENERAR SCRIPT DE ATENCION CON EL ID_TICKET INGRESADO
    # ============================================================
    try:
        script = generar_script_atencion(bloque)
    except Exception as e:
        script = f"-- Error al generar script de atencion: {str(e)}"
    
    min_id = min(ids) if ids else 0
    max_id = max(ids) if ids else 0
    rango = f"{min_id} - {max_id}"
    
    return jsonify({
        "success": True,
        "asignados": len(ids),
        "total": len(bloque),
        "rango": rango,
        "ids": ids,
        "trabajadores": bloque,
        "script": script,
        "id_ticket": id_ticket,
        "mensaje": f"Se asignaron {len(ids)} ID_TRAMITE correctamente con ID_TICKET: {id_ticket}."
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

    id_ticket = datos.get("id_ticket")
    codigo = datos.get("codigo_ticket", "RF-001")
    fecha = datos.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    departamento = datos.get("departamento", 32)
    tipo_tramite = datos.get("tipo_tramite", 174)
    usuario_creacion = datos.get("usuario_creacion", 1155)
    razon_social = datos.get("empresa", "")
    nit = datos.get("nit", "")
    hora_inicio = datos.get("hora_base", "08:30:00")
    hora_fin = datos.get("hora_fin", "13:21:00")

   # ⭐ AGREGAR id_empresa
    id_empresa = datos.get("id_empresa", 27424)

    script = f"""
-- ============================================================
-- SCRIPT COMPLETO - PLANILLA FINAL
-- ============================================================
-- PLANILLA: {datos.get("planilla_id")}
-- ARCHIVO: {datos.get("archivo_nombre", "")}
-- ID_TICKET: {id_ticket}
-- RF: {codigo}
-- RAZON SOCIAL: {escapar_sql(razon_social)}
-- NIT: {escapar_sql(nit)}
-- USUARIO CREACIÓN: {usuario_creacion}
-- TRABAJADORES: {len(trabajadores)}
-- FECHA: {fecha}
-- ============================================================

"""
    script += generar_script_insert_ticket(
        trabajadores,
        id_ticket,
        codigo,
        fecha,
        departamento,
        tipo_tramite,
        usuario_creacion,
        hora_inicio,
        hora_fin
    )

    # ============================================================
    # 2. SCRIPT DE PERSONAS (ext_persona) - PASO 5
    # ============================================================
    script += generar_script_personas(trabajadores)
    

    script += generar_script_trm_tramite(
        trabajadores,
        id_ticket,
        usuario_creacion,
        razon_social,
        nit,
        id_empresa
    )

    # ============================================================
    # 4. SCRIPT DE ATENCIÓN (dtck_ticket_atencion_tramite) - PASO 7
    # ============================================================
    script += generar_script_atencion(trabajadores)

    # ============================================================
    # 5. INFORMACIÓN ADICIONAL (COD_TRAM e ID_TRAMITE)
    # ============================================================
    script += generar_script_codigos(trabajadores)
    script += generar_script_idtramites(trabajadores)

    return script


# ============================================================
# SCRIPT FINAL
# ============================================================
# ============================================================
# PASO 8 - GENERAR SCRIPT FINAL
# ============================================================
# ============================================================
# PASO 8 - GENERAR SCRIPT FINAL
# ============================================================

@app.route("/api/generar_script_final", methods=["POST"])
def generar_script_final():
    """Genera el script completo con todos los INSERTs"""
    
    datos = cargar_planilla()
    if not datos:
        return jsonify({
            "success": False,
            "error": "No existe una planilla cargada."
        }), 400

    data = request.get_json(silent=True) or {}
    
    # ⭐ CORREGIDO: Convertir a string antes de strip()
    id_ticket = str(data.get("id_ticket", "")).strip()
    
    if not id_ticket:
        return jsonify({
            "success": False,
            "error": "Debe ingresar el ID_TICKET que generó el sistema externo."
        }), 400
    
    try:
        id_ticket = int(id_ticket)
    except:
        return jsonify({
            "success": False,
            "error": "El ID_TICKET debe ser un número válido."
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

    # Verificar que todos tengan ID_TRAMITE
    sin_id = [t for t in procesados if not t.get("id_tramite")]
    if sin_id:
        return jsonify({
            "success": False,
            "error": f"Hay {len(sin_id)} trabajadores sin ID_TRAMITE. Primero registre los ID_TRAMITE en el Paso 7."
        }), 400

    # Verificar que todos tengan ID_PERSONA
    sin_persona = [t for t in procesados if not t.get("id_persona")]
    if sin_persona:
        return jsonify({
            "success": False,
            "error": f"Hay {len(sin_persona)} trabajadores sin ID_PERSONA. Primero registre los ID_PERSONA en el Paso 5."
        }), 400

    # ACTUALIZAR EL ID_TICKET EN LA PLANILLA
    datos["id_ticket"] = id_ticket
    actualizar_planilla(datos)

    # GENERAR SCRIPT COMPLETO
    script_completo = generar_script_completo(procesados)

    return jsonify({
        "success": True,
        "script_completo": script_completo,
        "trabajadores": procesados,
        "cantidad": len(procesados),
        "id_ticket": id_ticket
    })

# ============================================================
# ERRORES
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "error.html",
        mensaje="Página no encontrada",
        step=0
    )


@app.errorhandler(500)
def error_interno(e):
    return jsonify({
        "success": False,
        "error": "Error interno del servidor."
    }), 500

# ============================================================
# RUTAS PARA BASE DE DATOS
# ============================================================

@app.route("/api/db/test", methods=["GET"])
def api_test_db():
    """Prueba la conexión a la base de datos"""
    from conexion import get_db_info
    info = get_db_info()
    return jsonify({
        "success": info['conectado'],
        "mensaje": "Conexión exitosa" if info['conectado'] else "Error de conexión",
        "info": info
    })

@app.route("/api/db/esquemas", methods=["GET"])
def api_listar_esquemas():
    """Lista todos los esquemas de la base de datos"""
    from conexion import listar_esquemas
    try:
        esquemas = listar_esquemas()
        return jsonify({
            "success": True,
            "total": len(esquemas),
            "esquemas": esquemas
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/db/tablas", methods=["GET"])
def api_listar_tablas():
    """Lista todas las tablas con su esquema"""
    from conexion import listar_tablas
    try:
        tablas = listar_tablas()
        resultado = []
        for fila in tablas:
            resultado.append({
                "esquema": fila[0],
                "tabla": fila[1],
                "tipo": fila[2]
            })
        return jsonify({
            "success": True,
            "total": len(resultado),
            "tablas": resultado
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/db/buscar/<tabla>", methods=["GET"])
def api_buscar_tabla(tabla):
    """Busca una tabla en todos los esquemas"""
    from conexion import verificar_tabla_existe
    try:
        existe = verificar_tabla_existe(tabla)
        return jsonify({
            "success": True,
            "tabla": tabla,
            "existe": existe
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/db/consulta", methods=["POST"])
def api_ejecutar_consulta():
    """Ejecuta una consulta SQL en la base de datos"""
    from conexion import ejecutar_consulta
    try:
        data = request.get_json(silent=True) or {}
        consulta = data.get("consulta", "")
        parametros = data.get("parametros", None)
        
        if not consulta:
            return jsonify({
                "success": False,
                "error": "Debe proporcionar una consulta SQL"
            }), 400
        
        success, mensaje, resultado = ejecutar_consulta(consulta, parametros)
        
        return jsonify({
            "success": success,
            "mensaje": mensaje,
            "resultado": resultado
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
# ============================================================
# RUTAS PARA BUSCAR EMPRESAS (CORREGIDO)
# ============================================================

# ⭐ IMPORTAR AMBAS CONEXIONES
from conexion import buscar_empresas  # ← BD principal (dtck_empleador_nit)
from conexion_empresa import obtener_id_empresa_por_nit  # ← SOLO ID_EMPRESA

@app.route("/api/empresa/buscar", methods=["GET"])
def api_buscar_empresas():
    """
    Busca empresas combinando ambas bases de datos:
    1. Busca en dtck_empleador_nit (mteps_desa) → nit, razon_social (SOLO EMPRESAS)
    2. Obtiene SOLO id_empresa desde public.empresa (mintrabajo_ovt_desa) usando el NIT
    """
    
    termino = request.args.get("termino", "").strip()
    
    if not termino or len(termino) < 3:
        return jsonify({
            "success": False,
            "error": "Debe escribir al menos 3 caracteres para buscar"
        }), 400
    
    try:
        # 1. Buscar en la BD principal (dtck_empleador_nit) - SOLO EMPRESAS
        empresas_bd1 = buscar_empresas(termino, limite=10)
        
        # 2. Para cada empresa, obtener SOLO el id_empresa de la otra BD
        empresas_completas = []
        for emp in empresas_bd1:
            # Obtener id_empresa usando el NIT (de la otra BD)
            id_empresa = obtener_id_empresa_por_nit(emp['nit'])
            
            empresas_completas.append({
                'id_empresa': id_empresa if id_empresa else None,  # ← De mintrabajo_ovt_desa
                'nit': emp['nit'],                                   # ← De mteps_desa
                'razon_social': emp['razon_social']                  # ← De mteps_desa
            })
        
        # Filtrar empresas que tienen id_empresa
        empresas_completas = [e for e in empresas_completas if e['id_empresa'] is not None]
        
        return jsonify({
            "success": True,
            "total": len(empresas_completas),
            "empresas": empresas_completas
        })
    except Exception as e:
        print(f"❌ Error en búsqueda: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/empresa/<int:id_empresa>", methods=["GET"])
def api_obtener_empresa(id_empresa):
    """Obtiene los datos de una empresa por su ID desde mintrabajo_ovt_desa"""
    
    try:
        # ⭐ USAR LA CONEXIÓN QUE TIENE DATOS
        empresa = obtener_empresa_por_id_externo(id_empresa)
        
        if empresa:
            return jsonify({
                "success": True,
                "empresa": empresa
            })
        else:
            return jsonify({
                "success": False,
                "error": "Empresa no encontrada"
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ERRORES
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template(
        "error.html",
        mensaje="Página no encontrada",
        step=0
    )

@app.errorhandler(500)
def error_interno(e):
    return jsonify({
        "success": False,
        "error": "Error interno del servidor."
    }), 500


# ============================================================
# EJECUCIÓN
# ============================================================

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
if __name__ == "__main__":
    app.run(debug=True, port=5000)

# ============================================================
# EJECUCIÓN
# ============================================================
