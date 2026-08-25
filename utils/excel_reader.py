"""
Utilidad para leer y procesar archivos Excel
"""

import pandas as pd
import os
from datetime import datetime

class ExcelReader:
    """Clase para leer y procesar archivos Excel de planillas"""
    
    def __init__(self, file_path):
        """
        Inicializar lector de Excel
        
        Args:
            file_path (str): Ruta del archivo Excel
        """
        self.file_path = file_path
        self.df = None
        self.trabajadores = []
        self.errores = []
        
    def leer_archivo(self):
        """
        Leer el archivo Excel
        
        Returns:
            bool: True si se leyó correctamente, False si hubo error
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(self.file_path):
                self.errores.append(f"El archivo {self.file_path} no existe")
                return False
            
            # Leer archivo Excel
            self.df = pd.read_excel(self.file_path)
            
            # Verificar que tiene datos
            if self.df.empty:
                self.errores.append("El archivo Excel está vacío")
                return False
            
            return True
            
        except Exception as e:
            self.errores.append(f"Error al leer el archivo: {str(e)}")
            return False
    
    def validar_columnas(self):
        """
        Validar que el Excel tenga las columnas necesarias
        
        Returns:
            bool: True si todas las columnas existen
        """
        columnas_requeridas = ['CI', 'NOMBRE', 'CARGO', 'DIRECCION', 'TELEFONO']
        columnas_faltantes = []
        
        for col in columnas_requeridas:
            if col not in self.df.columns:
                columnas_faltantes.append(col)
        
        if columnas_faltantes:
            self.errores.append(f"Faltan columnas: {', '.join(columnas_faltantes)}")
            return False
        
        return True
    
    def procesar_trabajadores(self):
        """
        Procesar los trabajadores del Excel
        
        Returns:
            list: Lista de diccionarios con los trabajadores
        """
        if self.df is None:
            self.errores.append("Primero debe leer el archivo")
            return []
        
        self.trabajadores = []
        
        for index, row in self.df.iterrows():
            trabajador = {
                'nro': index + 1,
                'ci': self._limpiar_texto(str(row.get('CI', ''))),
                'nombre': self._limpiar_texto(str(row.get('NOMBRE', ''))),
                'cargo': self._limpiar_texto(str(row.get('CARGO', 'DOCENTE'))),
                'direccion': self._limpiar_texto(str(row.get('DIRECCION', ''))),
                'telefono': self._limpiar_texto(str(row.get('TELEFONO', ''))),
                'paterno': '',
                'materno': '',
                'domicilio': self._limpiar_texto(str(row.get('DIRECCION', ''))),
                'email': '',
                'estado': 'ACTIVO'
            }
            self.trabajadores.append(trabajador)
        
        return self.trabajadores
    
    def _limpiar_texto(self, texto):
        """
        Limpiar texto eliminando caracteres especiales y espacios
        
        Args:
            texto (str): Texto a limpiar
            
        Returns:
            str: Texto limpio
        """
        if texto == 'nan' or texto == 'NaN' or texto == 'None':
            return ''
        texto = str(texto).strip()
        return texto
    
    def obtener_resumen(self):
        """
        Obtener resumen del archivo
        
        Returns:
            dict: Resumen con estadísticas
        """
        if self.df is None:
            return {'error': 'No se ha leído el archivo'}
        
        total = len(self.trabajadores) if self.trabajadores else len(self.df)
        
        return {
            'total': total,
            'columnas': list(self.df.columns),
            'validos': total - len(self.errores),
            'errores': self.errores
        }
    
    def obtener_vista_previa(self, cantidad=5):
        """
        Obtener vista previa de trabajadores
        
        Args:
            cantidad (int): Número de trabajadores a mostrar
            
        Returns:
            list: Lista de trabajadores para vista previa
        """
        if not self.trabajadores:
            self.procesar_trabajadores()
        
        return self.trabajadores[:cantidad]


def detectar_empresa(trabajadores):
    """
    Detectar datos de la empresa desde los trabajadores
    
    Args:
        trabajadores (list): Lista de trabajadores
        
    Returns:
        dict: Datos de la empresa
    """
    # En un sistema real, esto vendría de una tabla de empresas
    # Aquí usamos datos por defecto
    return {
        'razon_social': 'CORPORACION DE AQUINO BOLIVIA S.A.',
        'nit': '1020367024',
        'tipo_tramite': 'FINIQUITO',
        'departamento': 32
    }


def calcular_horas(hora_base, intervalo, nro_trabajador, desde=1):
    """
    Calcular horas para un trabajador
    
    Args:
        hora_base (str): Hora base (HH:MM:SS)
        intervalo (int): Intervalo en minutos
        nro_trabajador (int): Número del trabajador
        desde (int): Desde qué trabajador empieza
        
    Returns:
        tuple: (hora_inicio, hora_fin)
    """
    from datetime import datetime, timedelta
    
    try:
        hora_obj = datetime.strptime(hora_base, '%H:%M:%S')
    except ValueError:
        hora_obj = datetime.strptime('08:30:00', '%H:%M:%S')
    
    minutos_inicio = (nro_trabajador - desde) * (intervalo + 1)
    minutos_fin = minutos_inicio + intervalo
    
    hora_inicio = hora_obj + timedelta(minutes=minutos_inicio)
    hora_fin = hora_inicio + timedelta(minutes=intervalo)
    
    return hora_inicio.strftime('%H:%M:%S'), hora_fin.strftime('%H:%M:%S')