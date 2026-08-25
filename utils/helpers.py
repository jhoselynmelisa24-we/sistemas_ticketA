"""
Funciones auxiliares para el sistema de planillas
"""

from datetime import datetime, timedelta
import json
import os

def sumar_minutos(hora_str, minutos):
    """
    Sumar minutos a una hora
    
    Args:
        hora_str (str): Hora en formato HH:MM:SS
        minutos (int): Minutos a sumar
        
    Returns:
        str: Nueva hora en formato HH:MM:SS
    """
    try:
        hora = datetime.strptime(hora_str, '%H:%M:%S')
    except ValueError:
        hora = datetime.strptime('08:30:00', '%H:%M:%S')
    
    nueva_hora = hora + timedelta(minutes=minutos)
    return nueva_hora.strftime('%H:%M:%S')


def calcular_total_horas(hora_inicio, hora_fin):
    """
    Calcular total de horas entre dos horas
    
    Args:
        hora_inicio (str): Hora inicio
        hora_fin (str): Hora fin
        
    Returns:
        str: Total de horas en formato HH:MM
    """
    try:
        inicio = datetime.strptime(hora_inicio, '%H:%M:%S')
        fin = datetime.strptime(hora_fin, '%H:%M:%S')
        diferencia = fin - inicio
        horas = diferencia.seconds // 3600
        minutos = (diferencia.seconds % 3600) // 60
        return f"{horas:02d}:{minutos:02d}"
    except:
        return "00:00"


def guardar_sesion(data, archivo='data/session_data.json'):
    """
    Guardar datos de sesión en archivo
    
    Args:
        data (dict): Datos a guardar
        archivo (str): Ruta del archivo
    """
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    with open(archivo, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cargar_sesion(archivo='data/session_data.json'):
    """
    Cargar datos de sesión desde archivo
    
    Args:
        archivo (str): Ruta del archivo
        
    Returns:
        dict: Datos de sesión
    """
    if os.path.exists(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def formatear_codigo_tramite(prefijo, anio, numero):
    """
    Formatear código de trámite
    
    Args:
        prefijo (str): Prefijo (ej: TRM)
        anio (int): Año
        numero (int): Número
        
    Returns:
        str: Código formateado
    """
    return f"{prefijo}/{anio}-{numero}"


def limpiar_texto(texto):
    """
    Limpiar texto para uso en SQL
    
    Args:
        texto (str): Texto a limpiar
        
    Returns:
        str: Texto limpio
    """
    if not texto or texto == 'nan' or texto == 'NaN' or texto == 'None':
        return ''
    texto = str(texto).strip()
    texto = texto.replace("'", "''")  # Escapar comillas simples
    return texto