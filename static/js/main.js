/* ============================================================
   SISTEMA DE PROCESAMIENTO DE PLANILLAS
   PASO 1 — CARGAR PLANILLA
   ============================================================ */


/* ============================================================
   ESTADO GLOBAL
   ============================================================ */

let archivoSeleccionado = null;

let trabajadoresData = [];

let totalTrabajadores = 0;

let cantidadProcesar = 0;


/*
 * CORRELATIVO DE PLANILLA
 *
 * Este identificador representa la planilla actual.
 *
 * Ejemplo:
 *
 * PLANILLA-0001
 * PLANILLA-0002
 * PLANILLA-0003
 *
 * NO es el número del trabajador.
 */

let correlativoPlanilla = null;


/*
 * Rango actual de trabajadores
 */

let desdeTrabajador = 1;

let hastaTrabajador = 0;


/* ============================================================
   INICIO
   ============================================================ */

document.addEventListener(
    'DOMContentLoaded',
    function () {

        inicializarCargaExcel();

        cargarEstadoPlanilla();

    }
);


/* ============================================================
   INICIALIZAR CARGA DE EXCEL
   ============================================================ */

function inicializarCargaExcel() {

    const uploadArea =
        document.getElementById('uploadArea');

    const fileInput =
        document.getElementById('fileInput');

    const cantidadInput =
        document.getElementById('cantidadProcesar');


    if (!uploadArea || !fileInput) {

        console.error(
            'No se encontró uploadArea o fileInput.'
        );

        return;
    }


    /* ========================================================
       CLICK
       ======================================================== */

    uploadArea.addEventListener(
        'click',
        function (e) {

            if (
                e.target.closest('button')
            ) {

                return;
            }

            fileInput.click();

        }
    );


    /* ========================================================
       DRAGOVER
       ======================================================== */

    uploadArea.addEventListener(
        'dragover',
        function (e) {

            e.preventDefault();

            uploadArea.classList.add(
                'border-primary'
            );

        }
    );


    /* ========================================================
       DRAGLEAVE
       ======================================================== */

    uploadArea.addEventListener(
        'dragleave',
        function () {

            uploadArea.classList.remove(
                'border-primary'
            );

        }
    );


    /* ========================================================
       DROP
       ======================================================== */

    uploadArea.addEventListener(
        'drop',
        function (e) {

            e.preventDefault();

            uploadArea.classList.remove(
                'border-primary'
            );


            if (
                e.dataTransfer &&
                e.dataTransfer.files &&
                e.dataTransfer.files.length > 0
            ) {

                handleFile(
                    e.dataTransfer.files[0]
                );

            }

        }
    );


    /* ========================================================
       INPUT FILE
       ======================================================== */

    fileInput.addEventListener(
        'change',
        function () {

            if (
                this.files &&
                this.files.length > 0
            ) {

                handleFile(
                    this.files[0]
                );

            }

        }
    );


    /* ========================================================
       CANTIDAD
       ======================================================== */

    if (cantidadInput) {

        cantidadInput.addEventListener(
            'input',
            actualizarCantidad
        );

    }

}


/* ============================================================
   CARGAR ESTADO DE LA PLANILLA
   ============================================================ */

function cargarEstadoPlanilla() {

    fetch('/api/estado')

        .then(async function (response) {

            const data =
                await response.json();

            if (!response.ok) {

                throw new Error(
                    data.error ||
                    'No se pudo obtener el estado.'
                );

            }

            return data;

        })

        .then(function (data) {

            if (!data.success) {

                return;
            }


            /*
             * Si ya existe una planilla en sesión,
             * recuperamos sus datos.
             */

            if (
                data.archivo &&
                data.total > 0
            ) {

                totalTrabajadores =
                    Number(data.total) || 0;

                cantidadProcesar =
                    Number(
                        data.cantidad_procesar
                    ) || 0;

                desdeTrabajador =
                    Number(
                        data.desde
                    ) || 1;

                hastaTrabajador =
                    Number(
                        data.hasta
                    ) || 0;


                mostrarEstadoActual(
                    data
                );

            }

        })

        .catch(function (error) {

            console.log(
                'No existe una sesión de planilla activa.'
            );

        });

}


/* ============================================================
   MOSTRAR ESTADO ACTUAL
   ============================================================ */

function mostrarEstadoActual(data) {

    const totalElement =
        document.getElementById(
            'totalTrabajadores'
        );


    if (totalElement) {

        totalElement.textContent =
            data.total || 0;

    }


    const totalPreview =
        document.getElementById(
            'totalPreview'
        );


    if (totalPreview) {

        totalPreview.textContent =
            `${data.total || 0} trabajadores`;

    }


    /*
     * Mostrar bloque actual
     */

    const resumen =
        document.getElementById(
            'resumenProcesamiento'
        );


    if (
        resumen &&
        data.cantidad_procesar > 0
    ) {

        const pendientes =
            data.pendientes || 0;


        resumen.className =
            'alert alert-success mb-0';


        resumen.innerHTML = `

            <strong>
                ${data.cantidad_procesar}
            </strong>
            trabajadores en el bloque actual.

            <br>

            Desde trabajador:
            <strong>
                ${data.desde}
            </strong>

            hasta:

            <strong>
                ${data.hasta}
            </strong>

            <br>

            <strong>
                ${pendientes}
            </strong>
            trabajadores pendientes.

        `;

    }

}


/* ============================================================
   ARCHIVO SELECCIONADO
   ============================================================ */

function handleFile(file) {

    if (!file) {

        return;
    }


    const extension =
        file.name
            .split('.')
            .pop()
            .toLowerCase();


    if (
        !['xlsx', 'xls'].includes(
            extension
        )
    ) {

        mostrarNotificacion(
            '❌ Solo se permiten archivos .xlsx o .xls.',
            'danger'
        );

        return;
    }


    archivoSeleccionado =
        file;


    /* ========================================================
       ELEMENTOS
       ======================================================== */

    const fileName =
        document.getElementById(
            'fileName'
        );

    const fileInfo =
        document.getElementById(
            'fileInfo'
        );

    const fileEmpty =
        document.getElementById(
            'fileEmpty'
        );

    const fileStatus =
        document.getElementById(
            'fileStatus'
        );

    const btnAnalizar =
        document.getElementById(
            'btnAnalizar'
        );


    if (fileName) {

        fileName.textContent =
            file.name;

    }


    if (fileInfo) {

        fileInfo.classList.remove(
            'd-none'
        );

    }


    if (fileEmpty) {

        fileEmpty.classList.add(
            'd-none'
        );

    }


    if (fileStatus) {

        fileStatus.textContent =
            '📄 Archivo seleccionado';

        fileStatus.className =
            'badge bg-info';

    }


    if (btnAnalizar) {

        btnAnalizar.disabled =
            false;

        btnAnalizar.innerHTML =
            '<i class="fas fa-search me-2"></i> ANALIZAR EXCEL';

    }


    /* ========================================================
       LIMPIAR ESTADO ANTERIOR
       ======================================================== */

    trabajadoresData = [];

    totalTrabajadores = 0;

    cantidadProcesar = 0;

    desdeTrabajador = 1;

    hastaTrabajador = 0;


    /*
     * Importante:
     *
     * Al seleccionar una NUEVA planilla,
     * no reutilizamos el rango anterior.
     */


    const previewSection =
        document.getElementById(
            'previewSection'
        );


    if (previewSection) {

        previewSection.classList.add(
            'd-none'
        );

    }


    const btnContinuar =
        document.getElementById(
            'btnContinuar'
        );


    if (btnContinuar) {

        btnContinuar.disabled =
            true;

    }

}


/* ============================================================
   ANALIZAR EXCEL
   ============================================================ */
function analizarExcel() {

    if (!archivoSeleccionado) {
        mostrarNotificacion('⚠️ Primero seleccione una planilla Excel.', 'warning');
        return;
    }

    mostrarLoading('Analizando planilla...', 'Extrayendo los datos de todos los trabajadores.');

    const btnAnalizar = document.getElementById('btnAnalizar');
    if (btnAnalizar) {
        btnAnalizar.disabled = true;
        btnAnalizar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> ANALIZANDO...';
    }

    const formData = new FormData();
    formData.append('file', archivoSeleccionado);

    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })

    .then(async function (response) {
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Error al procesar la planilla.');
        }
        return data;
    })

    .then(function (data) {
        ocultarLoading();

        if (!data.success) {
            throw new Error(data.error || 'No se pudo analizar la planilla.');
        }

        /* ====================================================
           GUARDAR TRABAJADORES
           ==================================================== */

        trabajadoresData = data.trabajadores || [];
        totalTrabajadores = Number(data.total) || trabajadoresData.length;
        desdeTrabajador = 1;
        hastaTrabajador = 0;
        cantidadProcesar = 0;

        /* ====================================================
           CORRELATIVO
           ==================================================== */

        correlativoPlanilla = data.correlativo_planilla || data.planilla_id || null;

        /* ====================================================
           TOTAL
           ==================================================== */

        const totalElement = document.getElementById('totalTrabajadores');
        if (totalElement) {
            totalElement.textContent = totalTrabajadores;
        }

        /* ====================================================
           EMPRESA
           ==================================================== */

        const empresaElement = document.getElementById('empresaNombre');
        if (empresaElement) {
            empresaElement.textContent = data.empresa || 'No detectada';
        }

        /* ====================================================
           NIT
           ==================================================== */

        const nitElement = document.getElementById('nitEmpresa');
        if (nitElement) {
            nitElement.textContent = data.nit || 'No detectado';
        }

        /* ====================================================
           MOSTRAR CORRELATIVO
           ==================================================== */

        mostrarCorrelativoPlanilla();

        // ⭐⭐⭐ GUARDAR NIT Y RAZÓN SOCIAL DEL EXCEL ⭐⭐⭐
        const datosEmpresa = guardarDatosEmpresaDesdeExcel(data);
        if (datosEmpresa.nit || datosEmpresa.razonSocial) {
            console.log('📌 Datos de empresa extraídos del Excel:', datosEmpresa);
        }

        /* ====================================================
           PREVISUALIZACIÓN
           ==================================================== */

        mostrarVistaPrevia(trabajadoresData);

        const previewSection = document.getElementById('previewSection');
        if (previewSection) {
            previewSection.classList.remove('d-none');
        }

        const totalPreview = document.getElementById('totalPreview');
        if (totalPreview) {
            totalPreview.textContent = `${totalTrabajadores} trabajadores`;
        }

        const fileStatus = document.getElementById('fileStatus');
        if (fileStatus) {
            fileStatus.textContent = '✅ Planilla analizada correctamente';
            fileStatus.className = 'badge bg-success';
        }

        if (btnAnalizar) {
            btnAnalizar.disabled = false;
            btnAnalizar.innerHTML = '<i class="fas fa-check me-2"></i> EXCEL ANALIZADO';
        }

        mostrarNotificacion(
            `✅ Se extrajeron ${totalTrabajadores} trabajadores de la planilla.`,
            'success'
        );

    })

    .catch(function (error) {
        ocultarLoading();
        console.error('Error:', error);
        mostrarNotificacion('❌ ' + error.message, 'danger');
        restaurarBotonAnalizar();
    });

}

/* ============================================================
   MOSTRAR CORRELATIVO DE PLANILLA
   ============================================================ */

function mostrarCorrelativoPlanilla() {

    /*
     * Busca diferentes IDs para que puedas utilizar
     * cualquiera de ellos en tu HTML.
     */

    const elementos = [

        document.getElementById(
            'correlativoPlanilla'
        ),

        document.getElementById(
            'planillaId'
        ),

        document.getElementById(
            'numeroPlanilla'
        )

    ];


    const elemento =
        elementos.find(
            function (e) {
                return e !== null;
            }
        );


    if (!elemento) {

        return;
    }


    if (correlativoPlanilla) {

        elemento.textContent =
            correlativoPlanilla;

        return;
    }


    /*
     * Mientras el backend todavía no entregue
     * el correlativo, mostramos que está pendiente.
     */

    elemento.textContent =
        'Pendiente de asignación';

}

/* ============================================================
   GUARDAR NIT Y RAZÓN SOCIAL DEL EXCEL
   ============================================================ */

function guardarDatosEmpresaDesdeExcel(data) {
    /*
     * Esta función extrae el NIT y Razón Social del Excel
     * y los guarda en la planilla para usarlos en el Paso 4
     */
    
    let nit = '';
    let razonSocial = '';
    
    // Buscar en los trabajadores el primer NIT y Razón Social
    if (data.trabajadores && data.trabajadores.length > 0) {
        for (let i = 0; i < data.trabajadores.length; i++) {
            const t = data.trabajadores[i];
            // Buscar campos que puedan contener NIT
            if (t.nit && t.nit !== '' && t.nit !== null) {
                nit = t.nit;
            }
            // Buscar campos que puedan contener Razón Social
            if (t.razon_social && t.razon_social !== '' && t.razon_social !== null) {
                razonSocial = t.razon_social;
            }
            // Si encontramos ambos, salimos
            if (nit && razonSocial) break;
        }
    }
    
    // Si no encontramos, buscar en filas_excel
    if ((!nit || !razonSocial) && data.filas_excel && data.filas_excel.length > 0) {
        for (let i = 0; i < data.filas_excel.length; i++) {
            const fila = data.filas_excel[i];
            // Buscar NIT en diferentes nombres de columna
            for (const [key, value] of Object.entries(fila)) {
                const keyUpper = key.toUpperCase();
                if (keyUpper.includes('NIT') && value && value !== '') {
                    nit = value;
                }
                if ((keyUpper.includes('RAZON SOCIAL') || keyUpper.includes('RAZÓN SOCIAL') || keyUpper.includes('EMPRESA')) && value && value !== '') {
                    razonSocial = value;
                }
            }
            if (nit && razonSocial) break;
        }
    }
    
    // Guardar en la planilla (enviar al backend)
    if (nit || razonSocial) {
        fetch('/api/guardar_datos_empresa', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nit: nit,
                razon_social: razonSocial
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                console.log('✅ Datos de empresa guardados:', { nit, razonSocial });
            } else {
                console.warn('⚠️ No se pudieron guardar los datos de empresa');
            }
        })
        .catch(error => {
            console.warn('⚠️ Error al guardar datos de empresa:', error);
        });
    }
    
    return { nit, razonSocial };
}


/* ============================================================
   PREVISUALIZACIÓN
   ============================================================ */

function mostrarVistaPrevia(
    trabajadores
) {

    const tbody =
        document.getElementById(
            'previewBody'
        );


    if (!tbody) {

        console.error(
            'No existe #previewBody'
        );

        return;
    }


    tbody.innerHTML = '';


    if (
        !trabajadores ||
        trabajadores.length === 0
    ) {

        tbody.innerHTML = `

            <tr>

                <td
                    colspan="13"
                    class="text-center text-muted py-4">

                    No se encontraron trabajadores.

                </td>

            </tr>

        `;

        return;
    }


    /*
     * MOSTRAR TODOS LOS TRABAJADORES
     *
     * La previsualización no se limita
     * a la cantidad que se procesará.
     */


    trabajadores.forEach(
        function (t, index) {

            const tr =
                document.createElement(
                    'tr'
                );


            /*
             * Marcar si pertenece al bloque
             * actual.
             */

            const nro =
                Number(
                    t.nro ??
                    index + 1
                );


            if (
                hastaTrabajador > 0 &&
                nro >= desdeTrabajador &&
                nro <= hastaTrabajador
            ) {

                tr.classList.add(
                    'table-success'
                );

            }


            tr.innerHTML = `

                <td>
                    ${escapeHTML(
                        t.nro ??
                        index + 1
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.ci
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.expedicion
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.codexp
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.id_persona_excel
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.cod_tram
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.id_tramite_excel
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.hora_inicio_excel
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.hora_fin_excel
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.nombre
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.telefono
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.cargo
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        t.direccion
                    )}
                </td>

            `;


            tbody.appendChild(
                tr
            );

        }
    );

}


/* ============================================================
   CANTIDAD A PROCESAR
   ============================================================ */

function actualizarCantidad() {

    const input =
        document.getElementById(
            'cantidadProcesar'
        );

    const resumen =
        document.getElementById(
            'resumenProcesamiento'
        );

    const btnContinuar =
        document.getElementById(
            'btnContinuar'
        );


    if (!input) {

        return;
    }


    cantidadProcesar =
        parseInt(
            input.value,
            10
        );


    /* ========================================================
       SIN CANTIDAD
       ======================================================== */

    if (
        !cantidadProcesar ||
        cantidadProcesar <= 0
    ) {

        if (resumen) {

            resumen.className =
                'alert alert-info mb-0';

            resumen.innerHTML =
                'Indique la cantidad que desea procesar.';

        }


        if (btnContinuar) {

            btnContinuar.disabled =
                true;

        }

        return;
    }


    /* ========================================================
       MAYOR AL TOTAL
       ======================================================== */

    if (
        cantidadProcesar >
        totalTrabajadores
    ) {

        if (resumen) {

            resumen.className =
                'alert alert-danger mb-0';

            resumen.innerHTML =
                `❌ No puede procesar más de ${totalTrabajadores} trabajadores.`;

        }


        if (btnContinuar) {

            btnContinuar.disabled =
                true;

        }

        return;
    }


    /* ========================================================
       CALCULAR RANGO
       ======================================================== */

    desdeTrabajador =
        1;


    hastaTrabajador =
        cantidadProcesar;


    const pendientes =
        totalTrabajadores -
        cantidadProcesar;


    /* ========================================================
       RESUMEN
       ======================================================== */

    if (resumen) {

        resumen.className =
            'alert alert-success mb-0';


        resumen.innerHTML = `

            <strong>
                ${cantidadProcesar}
            </strong>
            trabajadores serán procesados.

            <br>

            Trabajador inicial:
            <strong>
                ${desdeTrabajador}
            </strong>

            <br>

            Trabajador final:
            <strong>
                ${hastaTrabajador}
            </strong>

            <br>

            <strong>
                ${pendientes}
            </strong>
            quedarán pendientes.

        `;

    }


    /* ========================================================
       BOTÓN
       ======================================================== */

    if (btnContinuar) {

        btnContinuar.disabled =
            false;


        btnContinuar.innerHTML = `

            <i class="fas fa-arrow-right me-2"></i>

            CONTINUAR AL PASO 2

            (${cantidadProcesar})

        `;

    }


    /*
     * Actualizamos visualmente la planilla.
     */

    mostrarVistaPrevia(
        trabajadoresData
    );

}


/* ============================================================
   CONTINUAR PASO 1
   ============================================================ */

function continuarPaso1() {

    const input =
        document.getElementById(
            'cantidadProcesar'
        );


    cantidadProcesar =
        parseInt(
            input?.value,
            10
        );


    /* ========================================================
       VALIDACIÓN
       ======================================================== */

    if (
        !cantidadProcesar ||
        cantidadProcesar <= 0
    ) {

        mostrarNotificacion(
            '⚠️ Debe indicar cuántos trabajadores desea procesar.',
            'warning'
        );

        return;
    }


    if (
        cantidadProcesar >
        totalTrabajadores
    ) {

        mostrarNotificacion(
            '❌ La cantidad supera el total de trabajadores.',
            'danger'
        );

        return;
    }


    /*
     * Calcular rango actual.
     */

    desdeTrabajador =
        1;


    hastaTrabajador =
        cantidadProcesar;


    mostrarLoading(
        'Guardando configuración...',
        'Registrando la cantidad de trabajadores a procesar.'
    );


    /* ========================================================
       GUARDAR EN FLASK
       ======================================================== */

    fetch(
        '/api/configurar_cantidad',
        {
            method: 'POST',

            headers: {
                'Content-Type':
                    'application/json'
            },

            body: JSON.stringify({

                cantidad_procesar:
                    cantidadProcesar

            })

        }
    )

    .then(async function (response) {

        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                'No se pudo guardar la cantidad.'
            );

        }


        return data;

    })


        /*
         * IMPORTANTE:
         *
         * Flask devuelve el rango real.
         */

        desdeTrabajador =
            Number(
                data.desde
            ) || 1;


        hastaTrabajador =
            Number(
                data.hasta
            ) || cantidadProcesar;


        cantidadProcesar =
            Number(
                data.cantidad_procesar
            ) || cantidadProcesar;


        /*
         * Guardar correlativo si el backend
         * lo devuelve.
         */

        if (
            data.correlativo_planilla
        ) {

            correlativoPlanilla =
                data.correlativo_planilla;

        }


        /*
         * Ahora sí pasamos al Paso 2.
         */

        window.location.href =
            '/tipo';

    })

    .catch(function (error) {

        ocultarLoading();


        console.error(
            error
        );


        mostrarNotificacion(
            '❌ ' + error.message,
            'danger'
        );

    });

}


/* ============================================================
   CONTINUAR CON OTRA PARTE DE LA PLANILLA
   ============================================================ */

function continuarProceso(
    cantidad = null
) {

    const datos = {};


    if (cantidad !== null) {

        datos.cantidad_procesar =
            cantidad;

    }


    mostrarLoading(
        'Preparando siguiente bloque...',
        'Calculando los trabajadores pendientes.'
    );


    fetch(
        '/api/continuar_proceso',
        {
            method: 'POST',

            headers: {
                'Content-Type':
                    'application/json'
            },

            body: JSON.stringify(
                datos
            )

        }
    )

    .then(async function (response) {

        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                'No se pudo continuar el proceso.'
            );

        }


        return data;

    })

    .then(function (data) {

        ocultarLoading();


        if (
            data.terminado
        ) {

            mostrarNotificacion(
                '✅ No quedan trabajadores pendientes.',
                'success'
            );

            return;
        }


        if (!data.success) {

            throw new Error(
                data.error ||
                'No se pudo continuar.'
            );

        }


        /*
         * Actualizar rango.
         */

        desdeTrabajador =
            Number(
                data.desde
            );


        hastaTrabajador =
            Number(
                data.hasta
            );


        cantidadProcesar =
            Number(
                data.cantidad_procesar
            );


        trabajadoresData =
            data.trabajadores ||
            trabajadoresData;


        /*
         * Mostrar información.
         */

        mostrarResumenBloque(
            data
        );


        mostrarVistaPrevia(
            trabajadoresData
        );


        mostrarNotificacion(

            `✅ Siguiente bloque preparado: ` +
            `trabajadores ${data.desde} al ${data.hasta}.`,

            'success'

        );

    })

    .catch(function (error) {

        ocultarLoading();


        console.error(
            error
        );


        mostrarNotificacion(
            '❌ ' + error.message,
            'danger'
        );

    });

}


/* ============================================================
   RESUMEN DEL BLOQUE
   ============================================================ */

function mostrarResumenBloque(data) {

    const resumen =
        document.getElementById(
            'resumenProcesamiento'
        );


    if (!resumen) {

        return;
    }


    resumen.className =
        'alert alert-success mb-0';


    resumen.innerHTML = `

        <strong>
            BLOQUE ACTUAL
        </strong>

        <br>

        Trabajadores:

        <strong>
            ${data.desde}
        </strong>

        -

        <strong>
            ${data.hasta}
        </strong>

        <br>

        Cantidad:

        <strong>
            ${data.cantidad_procesar}
        </strong>

        <br>

        Pendientes:

        <strong>
            ${data.pendientes}
        </strong>

    `;

}


/* ============================================================
   OBTENER PREVISUALIZACIÓN DESDE FLASK
   ============================================================ */

function cargarPrevisualizacion() {

    fetch(
        '/api/previsualizacion'
    )

    .then(async function (response) {

        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                'No se pudo obtener la previsualización.'
            );

        }


        return data;

    })

    .then(function (data) {

        if (!data.success) {

            return;
        }


        trabajadoresData =
            data.todos || [];


        totalTrabajadores =
            Number(
                data.total
            ) || 0;


        cantidadProcesar =
            Number(
                data.cantidad_procesada
            ) || 0;


        desdeTrabajador =
            Number(
                data.desde
            ) || 1;


        hastaTrabajador =
            Number(
                data.hasta
            ) || 0;


        mostrarVistaPrevia(
            trabajadoresData
        );


        mostrarResumenBloque(
            {

                desde:
                    desdeTrabajador,

                hasta:
                    hastaTrabajador,

                cantidad_procesar:
                    cantidadProcesar,

                pendientes:
                    data.cantidad_pendiente

            }
        );

    })

    .catch(function (error) {

        console.error(
            error
        );

    });

}


/* ============================================================
   ESCAPAR HTML
   ============================================================ */

function escapeHTML(valor) {

    if (
        valor === null ||
        valor === undefined ||
        valor === ''
    ) {

        return '-';

    }


    const div =
        document.createElement(
            'div'
        );


    div.textContent =
        String(valor);


    return div.innerHTML;

}


/* ============================================================
   BOTÓN ANALIZAR
   ============================================================ */

function restaurarBotonAnalizar() {

    const btn =
        document.getElementById(
            'btnAnalizar'
        );


    if (!btn) {

        return;
    }


    btn.disabled =
        false;


    btn.innerHTML =
        '<i class="fas fa-search me-2"></i> ANALIZAR EXCEL';

}


/* ============================================================
   LOADING
   ============================================================ */

function mostrarLoading(
    titulo,
    mensaje
) {

    const overlay =
        document.getElementById(
            'loadingOverlay'
        );

    const title =
        document.getElementById(
            'loadingTitle'
        );

    const message =
        document.getElementById(
            'loadingMessage'
        );


    if (title) {

        title.textContent =
            titulo;

    }


    if (message) {

        message.textContent =
            mensaje;

    }


    if (overlay) {

        overlay.classList.remove(
            'd-none'
        );

    }

}


function ocultarLoading() {

    const overlay =
        document.getElementById(
            'loadingOverlay'
        );


    if (overlay) {

        overlay.classList.add(
            'd-none'
        );

    }

}


/* ============================================================
   NOTIFICACIONES
   ============================================================ */

function mostrarNotificacion(
    mensaje,
    tipo = 'info'
) {

    const container =
        document.getElementById(
            'notificationContainer'
        );


    if (!container) {

        alert(mensaje);

        return;

    }


    const alertDiv =
        document.createElement(
            'div'
        );


    alertDiv.className =
        'alert alert-' +
        tipo +
        ' alert-dismissible fade show shadow';


    alertDiv.innerHTML = `

        ${escapeHTML(mensaje)}

        <button
            type="button"
            class="btn-close"
            data-bs-dismiss="alert">
        </button>

    `;


    container.appendChild(
        alertDiv
    );


    setTimeout(
        function () {

            if (
                alertDiv &&
                alertDiv.parentNode
            ) {

                alertDiv.remove();

            }

        },
        5000
    );

}


/* ============================================================
   FUNCIONES GLOBALES
   ============================================================ */

window.analizarExcel =
    analizarExcel;

window.continuarPaso1 =
    continuarPaso1;

window.actualizarCantidad =
    actualizarCantidad;

window.handleFile =
    handleFile;

window.continuarProceso =
    continuarProceso;

window.cargarPrevisualizacion =
    cargarPrevisualizacion;

window.mostrarNotificacion =
    mostrarNotificacion;