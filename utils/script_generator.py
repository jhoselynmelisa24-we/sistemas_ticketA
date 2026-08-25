"""
Generador de scripts SQL para el sistema de planillas
"""

from datetime import datetime

class ScriptGenerator:
    """Clase para generar scripts SQL"""
    
    def __init__(self):
        self.script = ""
    
    def generar_ticket(self, datos):
        """
        Generar script para ID_TICKET
        
        Args:
            datos (dict): Datos del ticket
            
        Returns:
            str: Script SQL
        """
        script = """
-- =============================================
-- PASO 1: ID_TICKET
-- =============================================
INSERT INTO mteps_d_tickets.dtck_ticket
(codigo, id_departamento, id_tipo_tramite, nro_tramites, estado, transaccion, 
 usuario_creacion, usuario_modificacion, fecha_creacion, fecha_modificacion, 
 observacion, fecha_solicitud_ticket, fecha_atencion, hora_inicio, hora_fin, 
 notificado, correo_notificado)
VALUES(
    '{codigo}',
    {departamento},
    {tipo_tramite},
    {nro_tramites},
    'SOLICITADO',
    'SOLICITAR_D_TICKET',
    1155, NULL, now(), NULL, NULL, now(),
    '{fecha}',
    '{hora_inicio}',
    '{hora_fin}',
    false, NULL
);
""".format(
    codigo=datos.get('codigo', 'RF-001'),
    departamento=datos.get('departamento', 32),
    tipo_tramite=datos.get('tipo_tramite', 174),
    nro_tramites=datos.get('nro_tramites', 1),
    fecha=datos.get('fecha', '2026-08-05'),
    hora_inicio=datos.get('hora_inicio', '08:30:00'),
    hora_fin=datos.get('hora_fin', '13:21:00')
)
        
        return script
    
    def generar_persona(self, trabajadores, desde=1):
        """
        Generar script para ID_PERSONA
        
        Args:
            trabajadores (list): Lista de trabajadores
            desde (int): Desde qué trabajador empezar
            
        Returns:
            str: Script SQL
        """
        if not trabajadores:
            return "-- No hay trabajadores para procesar"
        
        script = """
-- =============================================
-- PASO 2: ID_PERSONA
-- =============================================
INSERT INTO externos_mteps.ext_persona
(id_persona, nombre_completo, paterno, materno, tipo_documento, nro_documento, 
 complemento, lugar_expedicion, nacionalidad, genero, fecha_nacimiento, 
 estado_segip, fecha_verificacion, fecha_expiracion, estado, 
 observacion_segip, lugar_nacimiento, relacion_entidad, ocupacion, 
 domicilio, telefono, correo, usuario_creacion, usuario_modificacion, 
 fecha_creacion, fecha_modificacion, transaccion, observacion, edad)
VALUES
"""
        
        valores = []
        for t in trabajadores:
            if t.get('nro', 0) >= desde:
                valor = """
(
    externos_mteps.f_secuencial('ext_persona'),
    '{nombre}',
    '{paterno}',
    '{materno}',
    203,
    '{ci}',
    '', NULL, '', NULL, NULL, NULL, NULL, NULL, 'ELABORADO',
    NULL, NULL, 'DOCENTE', NULL,
    '{domicilio}',
    '{telefono}',
    NULL, 1155, 1155, now(), now(), 'ADICIONAR', '', NULL
)""".format(
    nombre=t.get('nombre', '').replace("'", "''"),
    paterno=t.get('paterno', '').replace("'", "''"),
    materno=t.get('materno', '').replace("'", "''"),
    ci=t.get('ci', ''),
    domicilio=t.get('domicilio', '').replace("'", "''"),
    telefono=t.get('telefono', '')
)
                valores.append(valor)
        
        if valores:
            script += ",\n".join(valores) + ";"
        else:
            script = "-- No hay trabajadores para procesar desde #{desde}".format(desde=desde)
        
        return script
    
    def generar_codigo_tramite(self, trabajadores, desde=1, prefijo='TRM', anio=2026):
        """
        Generar script para CÓDIGO_TRAMITE
        
        Args:
            trabajadores (list): Lista de trabajadores
            desde (int): Desde qué trabajador empezar
            prefijo (str): Prefijo del código
            anio (int): Año del código
            
        Returns:
            str: Script SQL
        """
        script = """
-- =============================================
-- PASO 3: CÓDIGO_TRAMITE
-- =============================================
"""
        
        for t in trabajadores:
            if t.get('nro', 0) >= desde:
                codigo = "{prefijo}/{anio}-{nro}".format(
                    prefijo=prefijo,
                    anio=anio,
                    nro=t.get('nro')
                )
                script += "-- {codigo} -> ID_PERSONA: {id_persona}\n".format(
                    codigo=codigo,
                    id_persona=t.get('id_persona', 'N/A')
                )
        
        return script
    
    def generar_id_tramite(self, trabajadores, desde=1):
        """
        Generar script para ID_TRAMITE
        
        Args:
            trabajadores (list): Lista de trabajadores
            desde (int): Desde qué trabajador empezar
            
        Returns:
            str: Script SQL
        """
        if not trabajadores:
            return "-- No hay trabajadores para procesar"
        
        script = """
-- =============================================
-- PASO 4: ID_TRAMITE
-- =============================================
INSERT INTO mteps_tramites.trm_tramite
(id_tramite, codigo_tramite, id_clasificador_tramite, monto_total_multa, 
 transaccion, estado, usuario_creacion, usuario_modificacion, 
 fecha_creacion, fecha_modificacion, id_empresa, id_persona, 
 periodo_planilla, gestion_planilla, minera, dias_retraso, 
 monto_calculo, nro_trabajadores, fecha_pago_prima, id_detalle_finiquito, 
 resolucion_administrativa, relacion_entidad, nro_fojas, observacion, 
 json_requisitos, nhr_tramite_relacionado, nur_sigec, nit, 
 matricula_comercio, codigo_multa, codigo_manual, razon_social, 
 persona_natural, codigo_visado, declarado_fc, codigo_fc, 
 id_ra, id_sucursal, nro_hojas_foleadas, descripcion_sucursal, 
 nro_hojas_leg, documento_leg, nro_boleta_err, fecha_boleta_err, 
 motivo_err, monto_err, c21_erroneos, c31_erroneos, devuelto_err, 
 desc_result_err, id_imputacion, mnt_tipo_cambio, pais_visado)
VALUES
"""
        
        valores = []
        for t in trabajadores:
            if t.get('nro', 0) >= desde:
                valor = """
(
    mteps_tramites.f_secuencial('trm_tramite'),
    '{codigo_tramite}',
    174, NULL, 'ADICIONAR_TICKET', 'ELABORADO_TICKET',
    981, 981, now(), now(), 27424, {id_persona},
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, '1020367024',
    NULL, NULL, NULL, 'CORPORACION DE AQUINO BOLIVIA S.A.',
    false, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL
)""".format(
    codigo_tramite=t.get('codigo_tramite', ''),
    id_persona=t.get('id_persona', 'NULL')
)
                valores.append(valor)
        
        if valores:
            script += ",\n".join(valores) + ";"
        else:
            script = "-- No hay trabajadores para procesar desde #{desde}".format(desde=desde)
        
        return script
    
    def generar_atencion(self, id_ticket, trabajadores, desde=1, fecha='2026-08-05'):
        """
        Generar script para ATENCIÓN (horas)
        
        Args:
            id_ticket (int): ID del ticket
            trabajadores (list): Lista de trabajadores
            desde (int): Desde qué trabajador empezar
            fecha (str): Fecha de atención
            
        Returns:
            str: Script SQL
        """
        if not trabajadores:
            return "-- No hay trabajadores para procesar"
        
        script = """
-- =============================================
-- PASO 5: ATENCIÓN (HORAS)
-- =============================================
INSERT INTO mteps_d_tickets.dtck_ticket_atencion_tramite
(id_ticket, id_tramite, id_usuario_asignado, fecha_atencion, hora_inicio, hora_fin, 
 estado, transaccion, usuario_creacion, usuario_modificacion, 
 fecha_creacion, fecha_modificacion, observacion)
VALUES
"""
        
        valores = []
        for t in trabajadores:
            if t.get('nro', 0) >= desde:
                valor = """
(
    {id_ticket}, {id_tramite}, 981, '{fecha}', '{hora_inicio}', '{hora_fin}',
    'INICIAL', 'SOLICITAR_D_TICKET', 981, NULL, now(), NULL, NULL
)""".format(
    id_ticket=id_ticket,
    id_tramite=t.get('id_tramite', 'NULL'),
    fecha=fecha,
    hora_inicio=t.get('hora_inicio', '00:00:00'),
    hora_fin=t.get('hora_fin', '00:00:00')
)
                valores.append(valor)
        
        if valores:
            script += ",\n".join(valores) + ";"
        else:
            script = "-- No hay trabajadores para procesar desde #{desde}".format(desde=desde)
        
        return script
    
    def generar_script_completo(self, id_ticket, trabajadores, desde=1, 
                                hora_base='08:30:00', fecha='2026-08-05'):
        """
        Generar script completo
        
        Args:
            id_ticket (int): ID del ticket
            trabajadores (list): Lista de trabajadores
            desde (int): Desde qué trabajador empezar
            hora_base (str): Hora base
            fecha (str): Fecha
            
        Returns:
            str: Script SQL completo
        """
        script = """
-- =============================================
-- SCRIPT COMPLETO GENERADO AUTOMÁTICAMENTE
-- =============================================
-- ID_TICKET: {id_ticket}
-- FECHA GENERACIÓN: {fecha_generacion}
-- DESDE TRABAJADOR: #{desde}
-- TOTAL: {total}
-- =============================================

""".format(
    id_ticket=id_ticket,
    fecha_generacion=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    desde=desde,
    total=len([t for t in trabajadores if t.get('nro', 0) >= desde])
)
        
        # Ticket
        script += self.generar_ticket({
            'codigo': 'RF-001',
            'departamento': 32,
            'tipo_tramite': 174,
            'nro_tramites': len([t for t in trabajadores if t.get('nro', 0) >= desde]),
            'fecha': fecha,
            'hora_inicio': hora_base,
            'hora_fin': '13:21:00'
        })
        
        # Persona
        script += "\n" + self.generar_persona(trabajadores, desde)
        
        # Código
        script += "\n" + self.generar_codigo_tramite(trabajadores, desde)
        
        # ID Tramite
        script += "\n" + self.generar_id_tramite(trabajadores, desde)
        
        # Atención
        script += "\n" + self.generar_atencion(id_ticket, trabajadores, desde, fecha)
        
        return script