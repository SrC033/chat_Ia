/* ============================================================
   MyndTeks · Modulación de Programación de Equipo de Trabajo
   Lógica del cliente
   ============================================================ */

/* ============================================================
   ESTADO GLOBAL
   ============================================================ */
let isProcessing = false;
let archivosAbiertos = {};
let archivoActual = null;
let adjuntos = [];
let generandoCodigo = false;
let streamTabName = null;

const chatBox = document.getElementById('chatBox');
const scrollBottomBtn = document.getElementById('scrollBottomBtn');
const inputWrapper = document.getElementById('inputWrapper');

const MAX_ADJUNTOS = 10;
const MAX_LINEAS_ARCHIVO = 5000;
const MAX_BYTES_ARCHIVO = 5 * 1024 * 1024;
const MAX_BYTES_TOTAL = 20 * 1024 * 1024;

const EXTENSIONES_BINARIAS = [
    'png','jpg','jpeg','gif','bmp','webp','svg','ico','tiff','tif',
    'pdf','doc','docx','xls','xlsx','ppt','pptx','odt','ods','odp',
    'zip','rar','7z','tar','gz','bz2','xz',
    'mp3','wav','ogg','flac','aac','m4a',
    'mp4','avi','mov','mkv','wmv','flv','webm',
    'exe','dll','so','dylib','bin','iso','img',
    'pyc','pyo','class','o','obj','lib','a'
];

/* ============================================================
   AUTO-SCROLL
   ============================================================ */
function isNearBottom(threshold = 90) {
    return (chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight) < threshold;
}

function scrollToBottomForce() {
    chatBox.scrollTop = chatBox.scrollHeight;
    scrollBottomBtn.classList.remove('visible');
}

function autoScrollIfNearBottom() {
    if (isNearBottom()) chatBox.scrollTop = chatBox.scrollHeight;
}

chatBox.addEventListener('scroll', () => {
    if (isNearBottom()) scrollBottomBtn.classList.remove('visible');
    else scrollBottomBtn.classList.add('visible');
});

/* ============================================================
   TOGGLE DEL OJO — activar/desactivar envío del archivo a la IA
   ============================================================ */
function toggleOjo(nombre, event) {
    if (event) event.stopPropagation();

    const info = archivosAbiertos[nombre];
    if (!info) return;

    info.ojoActivo = !info.ojoActivo;
    actualizarTabs();

    if (info.ojoActivo) {
        mostrarToast(`👁 ${nombre} · la IA leerá este archivo`);
    } else {
        mostrarToast(`○ ${nombre} · la IA ya no leerá este archivo`);
    }
}

/* ============================================================
   ABRIR ARCHIVO DEL PC — ojo activo por defecto
   ============================================================ */
async function abrirArchivoDelPC() {
    if (isProcessing) return;

    try {
        const res = await fetch('/abrir_archivo', { method: 'POST' });
        const data = await res.json();

        if (!res.ok || !data.success) {
            if (data.error && data.error !== 'Cancelado') {
                mostrarToast('❌ ' + data.error);
            }
            return;
        }

        const { nombre, contenido, lenguaje, ruta, lineas, truncado } = data;

        if (archivosAbiertos[nombre]) {
            archivoActual = nombre;
            actualizarTabs();
            cargarArchivo(nombre);
            mostrarToast(`📂 ${nombre} ya está abierto`);
            return;
        }

        archivosAbiertos[nombre] = {
            nombre,
            contenido,
            lenguaje,
            ruta,
            lineas,
            esPC: true,
            ojoActivo: true,
        };

        archivoActual = nombre;
        actualizarTabs();
        cargarArchivo(nombre);

        mostrarToast(truncado
            ? `📂 ${nombre} (truncado a 5000 líneas) · 👁 IA leyendo`
            : `📂 ${nombre} (${lineas} líneas) · 👁 IA leyendo`);
    } catch (err) {
        mostrarToast('❌ ' + err.message);
    }
}

/* ============================================================
   GESTIÓN DE ADJUNTOS
   ============================================================ */
function agregarAdjunto(nombre, contenido, pesoBytes, esPegado = false) {
    if (adjuntos.length >= MAX_ADJUNTOS) {
        mostrarToast(`Máximo ${MAX_ADJUNTOS} archivos`);
        return false;
    }
    if (adjuntos.some(a => a.nombre === nombre)) {
        mostrarToast(`"${nombre}" ya está adjunto`);
        return false;
    }
    const pesoTotal = adjuntos.reduce((s, a) => s + a.peso, 0) + pesoBytes;
    if (pesoTotal > MAX_BYTES_TOTAL) {
        mostrarToast(`Supera el límite de 20 MB`);
        return false;
    }
    const extension = nombre.split('.').pop().toLowerCase();
    if (EXTENSIONES_BINARIAS.includes(extension)) {
        mostrarToast(`"${nombre}" es binario`);
        return false;
    }
    if (pesoBytes > MAX_BYTES_ARCHIVO) {
        mostrarToast(`"${nombre}" supera los 5 MB`);
        return false;
    }
    const muestra = contenido.substring(0, 200);
    const caracteresRaros = (muestra.match(/[\x00-\x08\x0E-\x1F\uFFFD]/g) || []).length;
    if (caracteresRaros > 10) {
        mostrarToast(`"${nombre}" contiene datos binarios`);
        return false;
    }
    const lineas = contenido.split('\n');
    let truncado = false;
    if (lineas.length > MAX_LINEAS_ARCHIVO) {
        contenido = lineas.slice(0, MAX_LINEAS_ARCHIVO).join('\n');
        truncado = true;
    }
    const id = 'att_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7);
    adjuntos.push({
        id, nombre, contenido,
        peso: pesoBytes, esPegado,
        lineas: contenido.split('\n').length,
    });
    renderizarChips();
    if (truncado) mostrarToast(`"${nombre}" truncado a ${MAX_LINEAS_ARCHIVO} líneas`);
    else mostrarToast(`📎 ${nombre} adjuntado`);
    return true;
}

function eliminarAdjunto(id) {
    adjuntos = adjuntos.filter(a => a.id !== id);
    renderizarChips();
}

function limpiarAdjuntos() {
    adjuntos = [];
    renderizarChips();
}

function renderizarChips() {
    const contenedor = document.getElementById('attachmentsContainer');
    if (!contenedor) return;
    contenedor.innerHTML = '';
    adjuntos.forEach(a => {
        const chip = document.createElement('div');
        chip.className = 'mt-chip' + (a.esPegado ? ' pasted' : '');
        const icono = a.esPegado ? '📋' : iconoPorExtension(a.nombre);
        const meta = `${a.lineas} líneas · ${formatearPeso(a.peso)}`;
        chip.innerHTML = `
            <div class="mt-chip-icon">${icono}</div>
            <div class="mt-chip-info">
                <div class="mt-chip-name" title="${escapeHTML(a.nombre)}">${escapeHTML(a.nombre)}</div>
                <div class="mt-chip-meta">${meta}</div>
            </div>
            <button class="mt-chip-remove" title="Quitar" onclick="eliminarAdjunto('${a.id}')">✕</button>
        `;
        contenedor.appendChild(chip);
    });
}

function iconoPorExtension(nombre) {
    const ext = nombre.split('.').pop().toLowerCase();
    const mapa = {
        py: '🐍', js: '🟨', ts: '🟦', html: '🌐', css: '🎨',
        json: '📋', xml: '📋', yaml: '📋', yml: '📋',
        cpp: '⚙️', c: '⚙️', h: '⚙️', hpp: '⚙️',
        java: '☕', cs: '🎯', go: '🐹', rs: '🦀',
        php: '🐘', rb: '💎', swift: '🦅', kt: '🟪',
        sh: '⚡', bash: '⚡', ps1: '⚡', bat: '⚡',
        sql: '🗄️', md: '📝', txt: '📄', csv: '📊',
        vue: '💚', svelte: '🧡', dart: '🎯', lua: '🌙',
    };
    return mapa[ext] || '📄';
}

function formatearPeso(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
}

function handleFileSelect(input) {
    if (isProcessing) return;
    Array.from(input.files || []).forEach(f => leerArchivoYAdjuntar(f, false));
    input.value = '';
}

function leerArchivoYAdjuntar(file, esPegado) {
    const reader = new FileReader();
    reader.onload = e => agregarAdjunto(file.name, e.target.result, file.size, esPegado);
    reader.onerror = () => mostrarToast(`Error al leer "${file.name}"`);
    reader.readAsText(file, 'UTF-8');
}

/* ============================================================
   PEGAR CON Ctrl+V
   ============================================================ */
document.addEventListener('paste', (event) => {
    const items = event.clipboardData?.items;
    if (!items) return;
    let archivoPegado = false;
    for (const item of items) {
        if (item.kind === 'file') {
            const file = item.getAsFile();
            if (file) {
                if (file.type.startsWith('image/')) {
                    mostrarToast('Las imágenes no se pueden procesar');
                    archivoPegado = true;
                    continue;
                }
                leerArchivoYAdjuntar(file, true);
                archivoPegado = true;
            }
        }
    }
    if (archivoPegado) { event.preventDefault(); return; }
    const texto = event.clipboardData.getData('text');
    if (texto && texto.length > 5000) {
        const nombre = prompt('Texto grande pegado. ¿Nombre del archivo?', 'pegado.txt');
        if (nombre) {
            agregarAdjunto(nombre, texto, new Blob([texto]).size, true);
            event.preventDefault();
        }
    }
});

/* ============================================================
   DRAG & DROP
   ============================================================ */
if (inputWrapper) {
    inputWrapper.addEventListener('dragover', e => {
        e.preventDefault();
        inputWrapper.classList.add('dragover');
    });
    inputWrapper.addEventListener('dragleave', e => {
        if (!inputWrapper.contains(e.relatedTarget)) inputWrapper.classList.remove('dragover');
    });
    inputWrapper.addEventListener('drop', e => {
        e.preventDefault();
        inputWrapper.classList.remove('dragover');
        Array.from(e.dataTransfer.files || []).forEach(f => leerArchivoYAdjuntar(f, false));
    });
}

/* ============================================================
   MENSAJES
   ============================================================ */
function addSimpleMessage(html, tipo) {
    const div = document.createElement('div');
    div.className = tipo === 'user' ? 'mt-msg mt-msg-user' : 'mt-msg mt-msg-bot';
    div.innerHTML = html;
    chatBox.appendChild(div);
    autoScrollIfNearBottom();
    return div;
}

function setProcessingState(processing) {
    isProcessing = processing;
    document.getElementById('sendBtn').disabled = processing;
    document.getElementById('userInput').disabled = processing;
    const badge = document.getElementById('statusIndicator');
    const text = document.getElementById('statusText');
    if (processing) {
        badge.classList.add('processing');
        text.textContent = 'Procesando solicitud...';
    } else {
        badge.classList.remove('processing');
        text.textContent = 'Operador 1';
    }
}

/* ============================================================
   PARSEO DE RESPUESTA
   ============================================================ */
function parsearRespuesta(texto) {
    const segmentos = [];
    const regex = /```(\w*)\n([\s\S]*?)(?=```|$)/g;
    let ultimoIndex = 0;
    let match;

    while ((match = regex.exec(texto)) !== null) {
        if (match.index > ultimoIndex) {
            const textoAntes = texto.substring(ultimoIndex, match.index);
            if (textoAntes.trim()) {
                segmentos.push({ tipo: 'texto', contenido: textoAntes.trim() });
            }
        }
        const lenguaje = (match[1] || 'texto').toLowerCase() || 'texto';
        const codigo = (match[2] || '').replace(/\n$/, '');
        const cierre = texto.indexOf('```', match.index + match[0].length);
        const abierto = cierre === -1;

        if (codigo.length > 0) {
            segmentos.push({ tipo: 'codigo', lenguaje, contenido: codigo, abierto });
        }
        ultimoIndex = match.index + match[0].length;
    }

    if (ultimoIndex < texto.length) {
        const textoResto = texto.substring(ultimoIndex).replace(/^```\w*\n?/, '');
        if (textoResto.trim()) {
            segmentos.push({ tipo: 'texto', contenido: textoResto.trim() });
        }
    }
    if (segmentos.length === 0 && texto.trim()) {
        segmentos.push({ tipo: 'texto', contenido: texto.trim() });
    }
    return segmentos;
}

/* ============================================================
   RENDERIZADO
   ============================================================ */
function renderizarSegmentos(segmentos) {
    let html = '';
    segmentos.forEach((seg, idx) => {
        if (seg.tipo === 'texto') {
            html += `<div class="mt-assistant-text">${formatearTextoElegante(seg.contenido)}</div>`;
        } else {
            const lang = seg.lenguaje || 'texto';
            const idCode = 'code_' + idx + '_' + Math.random().toString(36).substring(2, 8);
            const nombreArchivo = nombrePorLenguaje(lang);
            html += `
                <div class="mt-code-block ${seg.abierto ? 'streaming' : ''}">
                    <div class="mt-code-header">
                        <div class="mt-code-header-left">
                            <div class="mt-code-dots"><span></span><span></span><span></span></div>
                            <span class="mt-code-lang">${escapeHTML(lang.toUpperCase())}</span>
                            <span class="mt-code-filename">${escapeHTML(nombreArchivo)}</span>
                        </div>
                        <button class="mt-code-copy" onclick="copiarCodigo('${idCode}')">
                            <span class="mt-code-copy-icon">⧉</span>
                            <span>Copiar</span>
                        </button>
                    </div>
                    <pre class="mt-code-body" id="${idCode}">${escapeHTML(seg.contenido)}</pre>
                </div>
            `;
        }
    });
    return html;
}

/* ============================================================
   FORMATEO DE TEXTO ELEGANTE
   ============================================================ */
function formatearTextoElegante(texto) {
    let t = escapeHTML(texto);
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
    t = t.replace(/`([^`]+)`/g, '<code class="mt-inline-code">$1</code>');
    t = t.replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>');
    t = t.replace(/(<li>[\s\S]*?<\/li>)+/g, m => `<ul class="mt-list">${m}</ul>`);
    t = t.replace(/^\s*(\d+)\.\s+(.+)$/gm, '<li class="mt-li-num" data-num="$1">$2</li>');
    t = t.replace(/(<li class="mt-li-num"[\s\S]*?<\/li>)+/g, m => `<ol class="mt-list-num">${m}</ol>`);
    t = t.replace(/^([A-ZÁÉÍÓÚÑ][^.\n]{0,80}:)/gm, '<strong class="mt-titulo">$1</strong>');
    t = t.replace(/\n/g, '<br>');
    return t;
}

/* ============================================================
   UTILIDADES
   ============================================================ */
function nombrePorLenguaje(lang) {
    const mapa = {
        python: 'script.py', py: 'script.py',
        javascript: 'script.js', js: 'script.js',
        typescript: 'script.ts', ts: 'script.ts',
        html: 'index.html', htm: 'index.html',
        css: 'styles.css',
        bash: 'install.sh', sh: 'install.sh', shell: 'install.sh',
        powershell: 'script.ps1', ps1: 'script.ps1',
        cpp: 'main.cpp', 'c++': 'main.cpp', c: 'main.c',
        java: 'Main.java', cs: 'Program.cs',
        go: 'main.go', rust: 'main.rs', rs: 'main.rs',
        php: 'index.php', ruby: 'script.rb', rb: 'script.rb',
        sql: 'query.sql', json: 'data.json', xml: 'data.xml',
        yaml: 'config.yaml', yml: 'config.yml',
        kotlin: 'Main.kt', swift: 'main.swift', dart: 'main.dart',
        markdown: 'README.md', md: 'README.md',
    };
    return mapa[lang] || `snippet.${lang}`;
}

function extensionDeLenguaje(lenguaje) {
    const mapa = {
        python: 'py', py: 'py',
        javascript: 'js', js: 'js',
        typescript: 'ts', ts: 'ts',
        html: 'html', htm: 'html',
        css: 'css',
        cpp: 'cpp', 'c++': 'cpp', c: 'c',
        java: 'java',
        json: 'json', xml: 'xml', yaml: 'yaml', yml: 'yaml',
        sql: 'sql', bash: 'sh', sh: 'sh', powershell: 'ps1',
        ruby: 'rb', php: 'php', go: 'go', rust: 'rs',
        kotlin: 'kt', swift: 'swift', dart: 'dart',
        markdown: 'md', md: 'md',
    };
    return mapa[lenguaje] || 'txt';
}

function escapeHTML(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function copiarCodigo(idCode) {
    const el = document.getElementById(idCode);
    if (!el) return;
    const texto = el.textContent;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto)
            .then(() => mostrarToast('📋 Código copiado'))
            .catch(() => copiarFallback(texto));
    } else {
        copiarFallback(texto);
    }
}

function copiarFallback(texto) {
    const ta = document.createElement('textarea');
    ta.value = texto;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        mostrarToast('📋 Código copiado');
    } catch (e) { mostrarToast('No se pudo copiar'); }
    document.body.removeChild(ta);
}

/* ============================================================
   DETECCIÓN DE CÓDIGO EN STREAM
   ============================================================ */
function extraerPrimerBloqueCodigo(textoParcial) {
    const match = textoParcial.match(/```(\w*)\n([\s\S]*?)(?:```|$)/);
    if (!match) return null;
    const lenguaje = (match[1] || 'texto').toLowerCase() || 'texto';
    let codigoParcial = match[2] || '';
    codigoParcial = codigoParcial.replace(/```[\s\S]*$/, '');
    if (!codigoParcial.trim()) return null;
    return { lenguaje, codigo: codigoParcial };
}

function escribirCodigoEnEditor(lenguaje, codigoParcial) {
    if (!streamTabName) {
        streamTabName = `stream.${extensionDeLenguaje(lenguaje)}`;
        archivosAbiertos[streamTabName] = {
            nombre: streamTabName,
            contenido: '',
            lenguaje,
            esStream: true,
            ojoActivo: false,
        };
    }
    archivosAbiertos[streamTabName].contenido = codigoParcial;
    archivosAbiertos[streamTabName].lenguaje = lenguaje;

    if (archivoActual !== streamTabName) {
        archivoActual = streamTabName;
        actualizarTabs();
    }

    const editor = document.getElementById('editorTextarea');
    const estabaAlFinal = editor.scrollTop + editor.clientHeight >= editor.scrollHeight - 20;
    editor.value = codigoParcial;
    if (estabaAlFinal) editor.scrollTop = editor.scrollHeight;

    actualizarEstadoEditor();
    sincronizarNumerosLinea();

    const codeArea = document.getElementById('codeArea');
    if (codeArea) codeArea.classList.add('streaming');
    generandoCodigo = true;
    actualizarTabs();
}

function terminarStreamingCodigo() {
    generandoCodigo = false;
    const codeArea = document.getElementById('codeArea');
    if (codeArea) codeArea.classList.remove('streaming');
}

function consolidarStreamConProyectos(proyectos) {
    if (streamTabName && archivosAbiertos[streamTabName]) {
        delete archivosAbiertos[streamTabName];
        if (archivoActual === streamTabName) archivoActual = null;
    }
    streamTabName = null;

    const nombres = [];
    proyectos.forEach(p => {
        nombres.push(p.nombre);
        archivosAbiertos[p.nombre] = {
            nombre: p.nombre,
            contenido: p.codigo || '',
            lenguaje: p.lenguaje || 'python',
            esStream: false,
            ojoActivo: true,
        };
    });

    if (nombres.length > 0) archivoActual = nombres[0];
    actualizarTabs();
    if (archivoActual) cargarArchivo(archivoActual);
}

/* ============================================================
   APLICAR EDICIONES "LINEA N: código" AL EDITOR
   ============================================================ */
function aplicarEdicionesAlEditor(textoRespuesta) {
    if (!archivoActual) return false;

    const regex = /^L[IÍ]NEA\s+(\d+)\s*:\s*(.+)$/gim;
    const ediciones = [];
    let match;

    while ((match = regex.exec(textoRespuesta)) !== null) {
        ediciones.push({
            linea: parseInt(match[1], 10),
            codigo: match[2],
        });
    }

    if (ediciones.length === 0) return false;

    const editor = document.getElementById('editorTextarea');
    const lineas = editor.value.split('\n');

    ediciones.forEach(ed => {
        const idx = ed.linea - 1;
        if (idx >= 0 && idx < lineas.length) {
            lineas[idx] = ed.codigo;
        } else if (idx === lineas.length) {
            lineas.push(ed.codigo);
        }
    });

    editor.value = lineas.join('\n');
    archivosAbiertos[archivoActual].contenido = editor.value;
    actualizarEstadoEditor();
    sincronizarNumerosLinea();

    mostrarToast(`✏️ ${ediciones.length} línea(s) modificada(s)`);
    return true;
}

/* ============================================================
   APLICAR BLOQUE NUMERADO AL EDITOR ACTIVO
   ============================================================ */
function aplicarBloqueAlEditor(codigoBloque) {
    if (!archivoActual || !archivosAbiertos[archivoActual]) return false;

    const lineas = codigoBloque.split('\n');
    const regexLinea = /^\s*(\d+)\s*\|\s?(.*)$/;
    const ediciones = [];

    for (const linea of lineas) {
        const m = linea.match(regexLinea);
        if (m) {
            ediciones.push({
                numero: parseInt(m[1], 10),
                contenido: m[2],
            });
        }
    }

    const totalLineasUtiles = lineas.filter(l => l.trim()).length;
    if (totalLineasUtiles === 0) return false;
    if (ediciones.length < totalLineasUtiles * 0.5) return false;

    const editor = document.getElementById('editorTextarea');
    const lineasActuales = editor.value.split('\n');

    ediciones.forEach(ed => {
        const idx = ed.numero - 1;
        if (idx >= 0 && idx < lineasActuales.length) {
            lineasActuales[idx] = ed.contenido;
        } else if (idx === lineasActuales.length) {
            lineasActuales.push(ed.contenido);
        }
    });

    editor.value = lineasActuales.join('\n');
    archivosAbiertos[archivoActual].contenido = editor.value;
    actualizarEstadoEditor();
    sincronizarNumerosLinea();

    mostrarToast(`✏️ ${ediciones.length} línea(s) aplicadas al editor`);
    return true;
}

/* ============================================================
   ENVIAR MENSAJE
   ============================================================ */
async function sendMessage() {
    if (isProcessing) return;

    const inputElement = document.getElementById('userInput');
    const messageText = inputElement.value.trim();

    // Recoger archivos con OJO ACTIVO
    const archivosConOjo = [];
    Object.keys(archivosAbiertos).forEach(nombre => {
        const info = archivosAbiertos[nombre];
        if (info.ojoActivo && info.contenido && info.contenido.trim().length > 0) {
            archivosConOjo.push({
                nombre: info.nombre,
                contenido: info.contenido,
                lenguaje: info.lenguaje || 'texto',
                numerado: true,
            });
        }
    });

    if (!messageText && adjuntos.length === 0 && archivosConOjo.length === 0) return;

    setProcessingState(true);

    // Rango de selección del editor actual
    let rangoSeleccion = null;
    if (archivoActual && archivosAbiertos[archivoActual]) {
        const editor = document.getElementById('editorTextarea');
        const inicio = editor.selectionStart;
        const fin = editor.selectionEnd;
        const textoAntes = editor.value.substring(0, inicio);
        const lineaInicio = textoAntes.split('\n').length;
        const textoSeleccionado = editor.value.substring(inicio, fin);
        const lineaFin = lineaInicio + textoSeleccionado.split('\n').length - 1;
        rangoSeleccion = { lineaInicio, lineaFin, archivo: archivoActual };
    }

    addSimpleMessage(
        escapeHTML(messageText || `📎 ${adjuntos.length} archivo(s) adjunto(s)`),
        'user'
    );
    inputElement.value = '';

    // ⭐ Forzar scroll al fondo al enviar la consulta
    scrollToBottomForce();

    const listaAdjuntos = adjuntos.map(a => ({ nombre: a.nombre, contenido: a.contenido }));
    const fileContentToSend = listaAdjuntos
        .map(a => `=== ARCHIVO: ${a.nombre} ===\n${a.contenido}\n=== FIN ${a.nombre} ===`)
        .join('\n\n');
    const fileNameToSend = listaAdjuntos.length === 1
        ? listaAdjuntos[0].nombre
        : `${listaAdjuntos.length}_archivos`;
    limpiarAdjuntos();

    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'mt-assistant-block';
    assistantDiv.innerHTML = `<div class="mt-assistant-text"><span class="mt-spinner"></span> Generando respuesta…</div>`;
    chatBox.appendChild(assistantDiv);

    // ⭐ Forzar scroll al fondo al añadir el contenedor del asistente
    scrollToBottomForce();

    streamTabName = null;
    terminarStreamingCodigo();

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: messageText || "Analiza los archivos con el ojo activo.",
                fileContent: fileContentToSend,
                fileName: fileNameToSend,
                archivosConOjo: archivosConOjo,
                rangoSeleccion: rangoSeleccion,
                stream: true
            })
        });

        if (!response.ok) throw new Error('Error de comunicación con el servidor local.');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let respuesta = '';
        let proyectos = [];

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const eventos = buffer.split('\n\n');
            buffer = eventos.pop();

            for (const evento of eventos) {
                if (!evento.startsWith('data: ')) continue;
                const dato = JSON.parse(evento.slice(6));
                if (dato.error) throw new Error(dato.error);

                if (dato.chunk) {
                    respuesta += dato.chunk;
                    const segmentos = parsearRespuesta(respuesta);
                    assistantDiv.innerHTML = renderizarSegmentos(segmentos);

                    // Aplicar en vivo si hay archivos con ojo activo
                    if (archivosConOjo.length > 0) {
                        const bloque = extraerPrimerBloqueCodigo(respuesta);
                        if (bloque && bloque.codigo.trim().length > 50) {
                            aplicarBloqueAlEditor(bloque.codigo);
                        }
                    } else {
                        const bloque = extraerPrimerBloqueCodigo(respuesta);
                        if (bloque) {
                            escribirCodigoEnEditor(bloque.lenguaje, bloque.codigo);
                        }
                    }

                    // ⭐ Forzar scroll al fondo durante el streaming
                    scrollToBottomForce();
                }

                if (dato.proyectos) proyectos = dato.proyectos;
            }
        }

        const segmentosFinales = parsearRespuesta(respuesta);
        assistantDiv.innerHTML = renderizarSegmentos(segmentosFinales);
        terminarStreamingCodigo();

        // ⭐ Forzar scroll al fondo al terminar
        scrollToBottomForce();

        // ─────────────────────────────────────────────────────────
        // FINAL DEL STREAM — decidir qué hacer con la respuesta
        // ─────────────────────────────────────────────────────────

        // 1. Intentar aplicar formato "LINEA N: código"
        if (archivoActual) {
            const aplicado = aplicarEdicionesAlEditor(respuesta);
            if (aplicado) {
                setProcessingState(false);
                inputElement.focus();
                return;
            }
        }

        // 2. Si hay archivos con ojo activo, intentar aplicar bloques numerados
        if (archivosConOjo.length > 0) {
            const bloqueFinal = extraerPrimerBloqueCodigo(respuesta);
            if (bloqueFinal) {
                const aplicado = aplicarBloqueAlEditor(bloqueFinal.codigo);
                if (aplicado) {
                    setProcessingState(false);
                    inputElement.focus();
                    return;
                }
            }
            mostrarToast('⚠️ La IA devolvió el código sin formato de edición. Revisa el bloque.');
            setProcessingState(false);
            inputElement.focus();
            return;
        }

        // 3. Sin archivos con ojo → flujo tradicional (abrir pestañas)
        if (proyectos.length === 0 && respuesta.includes('```')) {
            try {
                const creacion = await fetch('/crear_codigo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ respuesta })
                });
                const resultadoCreacion = await creacion.json();
                if (creacion.ok && resultadoCreacion.proyectos) proyectos = resultadoCreacion.proyectos;
            } catch (e) { /* silencioso */ }
        }

        if (proyectos.length > 0) {
            consolidarStreamConProyectos(proyectos);

            const nombres = proyectos.map(p => p.nombre);
            const notice = document.createElement('div');
            notice.className = 'mt-code-notice';
            notice.innerHTML = `<span>✓</span> <strong>Archivos generados:</strong> ${escapeHTML(nombres.join(', '))}`;
            chatBox.appendChild(notice);
            scrollToBottomForce();
        } else if (streamTabName && archivosAbiertos[streamTabName]) {
            const info = archivosAbiertos[streamTabName];
            const nombreDef = `codigo_${Date.now().toString().slice(-6)}.${extensionDeLenguaje(info.lenguaje)}`;
            delete archivosAbiertos[streamTabName];
            archivosAbiertos[nombreDef] = {
                nombre: nombreDef,
                contenido: info.contenido,
                lenguaje: info.lenguaje,
                esStream: false,
                ojoActivo: true,
            };
            if (archivoActual === streamTabName) archivoActual = nombreDef;
            streamTabName = null;
            actualizarTabs();
            cargarArchivo(archivoActual);
        }

    } catch (error) {
        assistantDiv.innerHTML = `<div class="mt-assistant-text">❌ ${escapeHTML(error.message)}</div>`;
        terminarStreamingCodigo();
        scrollToBottomForce();
    }

    setProcessingState(false);
    inputElement.focus();
}

/* ============================================================
   EDITOR
   ============================================================ */
function abrirArchivo(proyecto) {
    const nombre = proyecto.nombre;
    const contenido = proyecto.codigo || '';
    const lenguaje = proyecto.lenguaje || 'python';
    archivosAbiertos[nombre] = {
        nombre, contenido, lenguaje,
        ojoActivo: true,
    };
    archivoActual = nombre;
    actualizarTabs();
    cargarArchivo(nombre);
}

function actualizarTabs() {
    const tabsContainer = document.getElementById('editorTabs');
    tabsContainer.innerHTML = '';

    const nombres = Object.keys(archivosAbiertos);
    if (nombres.length === 0) {
        tabsContainer.innerHTML = '<span class="mt-tab-empty">Sin archivos abiertos</span>';
        return;
    }

    nombres.forEach(nombre => {
        const info = archivosAbiertos[nombre];
        const tab = document.createElement('button');

        let clases = 'mt-tab';
        if (nombre === archivoActual) clases += ' active';
        if (info.ojoActivo) clases += ' tab-ojo-on';
        tab.className = clases;

        const ojoHTML = `
            <span class="tab-eye ${info.ojoActivo ? 'on' : 'off'}"
                  title="${info.ojoActivo ? 'La IA está leyendo este archivo · click para desactivar' : 'Click para que la IA lea este archivo'}"
                  onclick="toggleOjo('${nombre}', event)">
                <span class="eye-pupil"></span>
            </span>
        `;

        let iconoTipo = '';
        if (info.esPC) iconoTipo = '📂';
        else if (info.esStream) iconoTipo = '⏳';
        else iconoTipo = '📄';

        tab.innerHTML = `
            ${ojoHTML}
            <span class="tab-icon">${iconoTipo}</span>
            <span>${escapeHTML(nombre)}</span>
            <span class="tab-close" onclick="event.stopPropagation();cerrarArchivo('${nombre}')">✕</span>
        `;

        tab.onclick = (e) => {
            if (e.target.classList.contains('tab-close')) return;
            if (e.target.classList.contains('tab-eye') ||
                e.target.classList.contains('eye-pupil')) return;
            archivoActual = nombre;
            cargarArchivo(nombre);
            actualizarTabs();
        };
        tabsContainer.appendChild(tab);
    });
}

function cargarArchivo(nombre) {
    const info = archivosAbiertos[nombre];
    if (!info) return;
    document.getElementById('editorTextarea').value = info.contenido;
    actualizarEstadoEditor();
}

function actualizarContenidoEditor() {
    if (archivoActual && archivosAbiertos[archivoActual]) {
        archivosAbiertos[archivoActual].contenido = document.getElementById('editorTextarea').value;
        archivosAbiertos[archivoActual].esStream = false;
    }
    actualizarEstadoEditor();
}

function actualizarEstadoEditor() {
    const editor = document.getElementById('editorTextarea');
    const lineas = editor.value.split('\n');
    document.getElementById('lineNumbers').textContent = lineas.map((_, i) => i + 1).join('\n');

    document.getElementById('editorLanguage').textContent =
        archivoActual && archivosAbiertos[archivoActual]
            ? (archivosAbiertos[archivoActual].lenguaje || 'Texto')
            : 'Texto';

    const pos = editor.selectionStart;
    const antes = editor.value.substring(0, pos);
    const linea = antes.split('\n').length;
    const col = pos - antes.lastIndexOf('\n');
    document.getElementById('editorPosition').textContent = `Ln ${linea}, Col ${col}`;
}

function sincronizarNumerosLinea() {
    document.getElementById('lineNumbers').scrollTop = document.getElementById('editorTextarea').scrollTop;
}

/* ============================================================
   GUARDAR
   ============================================================ */
async function guardarArchivo() {
    if (!archivoActual) {
        mostrarToast('No hay archivo abierto');
        return;
    }
    const contenido = document.getElementById('editorTextarea').value;
    const info = archivosAbiertos[archivoActual];

    if (info && info.esPC && info.ruta) {
        try {
            const res = await fetch('/guardar_en_ruta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ruta: info.ruta, contenido })
            });
            const data = await res.json();
            if (data.success) mostrarToast(`✅ Guardado en: ${info.ruta}`);
            else mostrarToast('❌ Error: ' + data.error);
            return;
        } catch (err) {
            mostrarToast('❌ ' + err.message);
            return;
        }
    }

    try {
        const res = await fetch('/guardar_como', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: archivoActual, contenido })
        });
        const data = await res.json();
        if (data.success) mostrarToast(`✅ Guardado en: ${data.ruta}`);
        else if (data.error !== 'Cancelado') mostrarToast('❌ Error: ' + (data.error || 'desconocido'));
    } catch (err) {
        mostrarToast('❌ ' + err.message);
    }
}

function cerrarArchivo(nombre) {
    if (nombre === archivoActual) archivoActual = null;
    delete archivosAbiertos[nombre];
    if (nombre === streamTabName) streamTabName = null;
    const nombres = Object.keys(archivosAbiertos);
    if (nombres.length > 0) archivoActual = nombres[0];
    actualizarTabs();
    if (archivoActual) cargarArchivo(archivoActual);
    else {
        document.getElementById('editorTextarea').value = '';
        actualizarEstadoEditor();
    }
}

function nuevoArchivo() {
    const nombre = prompt('Nombre del nuevo archivo:', `modulo_${Date.now()}.py`);
    if (!nombre) return;
    const lenguaje = nombre.split('.').pop().toLowerCase() || 'python';
    archivosAbiertos[nombre] = {
        nombre, contenido: '', lenguaje,
        ojoActivo: true,
    };
    archivoActual = nombre;
    actualizarTabs();
    cargarArchivo(nombre);
}

function limpiarEditor() {
    if (!archivoActual) return;
    if (!confirm(`¿Vaciar el contenido de "${archivoActual}"?`)) return;
    document.getElementById('editorTextarea').value = '';
    archivosAbiertos[archivoActual].contenido = '';
    actualizarEstadoEditor();
}

/* ============================================================
   TOAST
   ============================================================ */
function mostrarToast(mensaje) {
    let toast = document.getElementById('mtToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'mtToast';
        toast.className = 'mt-toast';
        document.body.appendChild(toast);
    }
    toast.textContent = mensaje;
    toast.classList.add('show');
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => toast.classList.remove('show'), 3500);
}