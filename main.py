# main.py
"""
main.py - Lanzador del chatbot con Flask + pywebview
- Guardar como... con diálogo nativo (tkinter)
- Abrir archivo del PC con diálogo nativo
- Guardar en ruta original (archivos abiertos del PC)
- Cierre limpio
- Sirve /css/ y /js/ desde templates/modulo_A/
- Fragmenta archivos grandes (>1000 líneas) con lectura.py
- Sistema de aprendizaje con aprender.py
- NO guarda automáticamente los códigos generados por la IA
- Edición quirúrgica por línea (archivos con ojo activo)
- Lee los archivos con el OJO activo desde el frontend
- Backend pywebview con fallback automático: Qt -> GTK -> navegador
"""

import os
import sys
import json
import re
import threading
import time
import socket
import platform
import tempfile
from datetime import datetime
from typing import List, Dict
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory

# tkinter (para diálogos nativos)
try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_OK = True
except ImportError:
    TKINTER_OK = False

try:
    import webview
    PYWEBVIEW_OK = True
except ImportError:
    PYWEBVIEW_OK = False
    print("⚠️ Falta instalar pywebview. Ejecuta: pip install pywebview")

# ============================================================
# CODIFICACIÓN CONSOLA WINDOWS
# ============================================================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

# ============================================================
# BLOQUEAR pty EN WINDOWS
# ============================================================
if platform.system() == 'Windows':
    import builtins
    _real_import = builtins.__import__
    def _bloquear_pty(name, *args, **kwargs):
        if name in ('pty', 'ptyprocess', 'termios', 'tty'):
            raise ImportError(f"'{name}' no está disponible en Windows (bloqueado).")
        return _real_import(name, *args, **kwargs)
    builtins.__import__ = _bloquear_pty

# ============================================================
# RUTAS BASE  (todo relativo al propio archivo main.py)
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELO_PY_DIR = os.path.join(BASE_DIR, 'modelo_py')

if MODELO_PY_DIR not in sys.path:
    sys.path.insert(0, MODELO_PY_DIR)

# ============================================================
# IMPORTS ROBUSTOS
# ============================================================
_errores_import = []
try:
    from ia import IA, crear_ia, IAConfig
except ImportError as e1:
    try:
        from ia.ia import IA, crear_ia, IAConfig
    except ImportError as e2:
        _errores_import.append(f"IA: {e1} | {e2}")

try:
    from editor_ejecutor import CodeEditor
except ImportError as e1:
    try:
        from editor.editor_ejecutor import CodeEditor
    except ImportError as e2:
        _errores_import.append(f"CodeEditor: {e1} | {e2}")

LectorFragmentado = None
try:
    from lectura import LectorFragmentado
except ImportError:
    print("⚠️ lectura.py no encontrado.")

Aprendiz = None
try:
    from aprender import Aprendiz
except ImportError:
    print("⚠️ aprender.py no encontrado.")

if _errores_import:
    print("=" * 70)
    print("❌ ERRORES DE IMPORTACIÓN")
    for err in _errores_import:
        print(f"   • {err}")
    sys.exit(1)

# ============================================================
# FLASK
# ============================================================
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates', 'modulo_A')
if not os.path.isdir(TEMPLATE_DIR):
    TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

ia = None
editor = None
aprendiz = None

HOST = '127.0.0.1'
PORT = 5000
URL = f"http://{HOST}:{PORT}"

servidor_flask = None

UMBRAL_FRAGMENTACION_LINEAS = 1000
LINEAS_POR_TROZO = 500
MAX_LINEAS_TOTAL = 5000

OPERADOR_ACTUAL = "Operador 1"


# ============================================================
# RUTAS FLASK
# ============================================================
@app.route('/')
def home():
    if ia:
        try:
            ia.reiniciar_conversacion()
        except Exception:
            pass
    return render_template('main.html')


@app.route('/health')
def health():
    if ia and ia.esta_activo():
        return jsonify({'status': 'ok', 'ia': 'connected'}), 200
    return jsonify({'status': 'error', 'ia': 'disconnected'}), 503


@app.route('/css/<path:filename>')
def servir_css(filename):
    return send_from_directory(os.path.join(TEMPLATE_DIR, 'css'), filename)


@app.route('/js/<path:filename>')
def servir_js(filename):
    return send_from_directory(os.path.join(TEMPLATE_DIR, 'js'), filename)


# ------------------------------------------------------------
# DIÁLOGO NATIVO: ABRIR ARCHIVO DEL PC
# ------------------------------------------------------------
@app.route('/abrir_archivo', methods=['POST'])
def abrir_archivo():
    """Abre el diálogo nativo para seleccionar UN archivo del PC."""
    if not TKINTER_OK:
        return jsonify({'success': False, 'error': 'tkinter no disponible'})

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        ruta = filedialog.askopenfilename(
            parent=root,
            title="Abrir archivo de código",
            filetypes=[
                ("Todos los archivos", "*.*"),
                ("Python", "*.py"),
                ("JavaScript", "*.js"),
                ("TypeScript", "*.ts"),
                ("HTML", "*.html"),
                ("CSS", "*.css"),
                ("C++", "*.cpp"),
                ("C", "*.c"),
                ("Java", "*.java"),
                ("JSON", "*.json"),
                ("Markdown", "*.md"),
                ("Texto", "*.txt"),
                ("Shell", "*.sh"),
                ("PowerShell", "*.ps1"),
                ("SQL", "*.sql"),
                ("Rust", "*.rs"),
                ("Go", "*.go"),
                ("PHP", "*.php"),
                ("Ruby", "*.rb"),
                ("Kotlin", "*.kt"),
                ("Swift", "*.swift"),
            ]
        )
        root.destroy()

        if not ruta:
            return jsonify({'success': False, 'error': 'Cancelado'})

        if os.path.getsize(ruta) > 5 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'El archivo supera los 5 MB'})

        try:
            with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
                contenido = f.read()
        except Exception:
            with open(ruta, 'r', encoding='latin-1', errors='replace') as f:
                contenido = f.read()

        lineas = contenido.split('\n')
        truncado = False
        if len(lineas) > 5000:
            contenido = '\n'.join(lineas[:5000])
            truncado = True

        nombre = os.path.basename(ruta)
        ext = os.path.splitext(nombre)[1].lstrip('.').lower() or 'texto'

        print(f"📂 Archivo abierto: {nombre} ({len(contenido.split(chr(10)))} líneas)")

        return jsonify({
            'success': True,
            'nombre': nombre,
            'ruta': ruta,
            'contenido': contenido,
            'lenguaje': ext,
            'lineas': len(contenido.split('\n')),
            'truncado': truncado,
        })

    except Exception as e:
        print(f"❌ Error al abrir archivo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------
# GUARDAR EN RUTA ORIGINAL
# ------------------------------------------------------------
@app.route('/guardar_en_ruta', methods=['POST'])
def guardar_en_ruta():
    try:
        data = request.get_json()
        ruta = data.get('ruta')
        contenido = data.get('contenido', '')
        if not ruta:
            return jsonify({'success': False, 'error': 'Ruta no especificada'})
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f"💾 Guardado en: {ruta}")
        return jsonify({'success': True, 'ruta': ruta})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------
# APRENDIZAJE
# ------------------------------------------------------------
@app.route('/aprendizaje/estadisticas', methods=['GET'])
def api_estadisticas_aprendizaje():
    if not aprendiz:
        return jsonify({'activo': False}), 200
    try:
        stats = aprendiz.estadisticas()
        stats['activo'] = True
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'activo': False, 'error': str(e)}), 500


# ------------------------------------------------------------
# /ask
# ------------------------------------------------------------
@app.route('/ask', methods=['POST'])
def ask():
    try:
        if not ia or not ia.esta_activo():
            return jsonify({'reply': "❌ El motor local de la IA no está inicializado."}), 503

        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'reply': "⚠️ JSON inválido."}), 400

        user_message = data.get('message', '')
        file_content = data.get('fileContent', '')
        file_name = data.get('fileName', '')
        archivos_con_ojo = data.get('archivosConOjo', [])
        rango = data.get('rangoSeleccion')
        use_stream = data.get('stream', True)

        # CASO 1: archivos con ojo
        if archivos_con_ojo and len(archivos_con_ojo) > 0:
            nombres = ", ".join(a.get('nombre', '?') for a in archivos_con_ojo)
            print(f"👁 Enviando {len(archivos_con_ojo)} archivo(s) con ojo activo: {nombres}")

            user_msg_enriquecido = user_message
            if rango:
                user_msg_enriquecido += (
                    f"\n\n[El cursor está en {rango.get('archivo', '?')}, "
                    f"líneas {rango['lineaInicio']}-{rango['lineaFin']}]"
                )

            prompt_data = ia.get_prompt_manager().construir_prompt_archivo(
                file_name=archivos_con_ojo[0].get('nombre', 'archivo'),
                file_content='',
                user_message=user_msg_enriquecido,
                archivos_multiples=archivos_con_ojo,
            )
            contenido_prompt = prompt_data['prompt']

            print(f"📝 Prompt (primeros 300 chars): {contenido_prompt[:300]}...")

            if use_stream:
                return Response(
                    stream_with_context(
                        generar_respuesta_stream_directo(contenido_prompt, user_message)
                    ),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
                )
            else:
                resultado = ia.chat.enviar_consulta(contenido_prompt, '', '')
                if resultado.get('success'):
                    bot_reply = resultado['reply']
                    codigos_extraidos = extraer_todos_los_codigos(bot_reply)
                    response_data = {'reply': bot_reply}
                    if codigos_extraidos:
                        response_data['proyectos'] = codigos_extraidos
                    return jsonify(response_data)
                else:
                    return jsonify({'reply': resultado.get('reply', '❌ Error')}), 500

        # CASO 2: flujo tradicional
        if file_content and LectorFragmentado and file_name:
            total_lineas = len(file_content.split('\n'))
            if total_lineas > UMBRAL_FRAGMENTACION_LINEAS:
                try:
                    file_content = _fragmentar_archivo(file_content, file_name, total_lineas)
                except Exception as e:
                    print(f"⚠️ Error al fragmentar: {e}")

        contexto_aprendido = ""
        if aprendiz and user_message:
            try:
                contexto_aprendido = aprendiz.generar_contexto_aprendido(user_message)
            except Exception as e:
                print(f"⚠️ Error al generar contexto: {e}")

        mensaje_final = user_message
        if contexto_aprendido:
            mensaje_final = contexto_aprendido + "\n\n" + user_message

        if use_stream:
            return Response(
                stream_with_context(
                    generar_respuesta_stream(mensaje_final, file_content, file_name, user_message)
                ),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
            )
        else:
            resultado = ia.enviar_mensaje(mensaje_final, file_content, file_name)
            if resultado['success']:
                bot_reply = resultado['reply']
                response_data = {'reply': bot_reply}
                codigos_extraidos = extraer_todos_los_codigos(bot_reply)
                if codigos_extraidos:
                    response_data['proyectos'] = codigos_extraidos
                if aprendiz:
                    try:
                        aprendiz.aprender_interaccion(
                            prompt=user_message, respuesta=bot_reply,
                            lenguaje="", operador=OPERADOR_ACTUAL,
                            codigos_extraidos=codigos_extraidos,
                        )
                    except Exception:
                        pass
                return jsonify(response_data)
            else:
                return jsonify({'reply': resultado['reply']}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'reply': f"❌ Error interno: {str(e)}"}), 500


def _fragmentar_archivo(contenido: str, nombre: str, total_lineas: int) -> str:
    ext = os.path.splitext(nombre)[1] or '.txt'
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=ext, delete=False,
            encoding='utf-8', errors='replace'
        ) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name

        lector = LectorFragmentado(
            tmp_path,
            lineas_por_trozo=LINEAS_POR_TROZO,
            max_lineas_total=MAX_LINEAS_TOTAL,
            delay_entre_trozos=0.0,
            incluir_contexto=True,
        )

        fragmentos = []
        for trozo in lector.iterar_trozos():
            fragmentos.append(lector.trozo_a_prompt(trozo, nombre))

        return "\n\n".join(fragmentos)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def generar_respuesta_stream(mensaje_final: str, file_content: str, file_name: str, prompt_original: str):
    try:
        respuesta_completa = ""
        for data in ia.enviar_mensaje_stream(mensaje_final, file_content, file_name):
            if 'error' in data:
                yield f"data: {json.dumps({'error': data['error']})}\n\n"
                break
            if 'chunk' in data:
                respuesta_completa += data['chunk']
                yield f"data: {json.dumps({'chunk': data['chunk']})}\n\n"
            if data.get('final', False):
                break

        codigos_extraidos = extraer_todos_los_codigos(respuesta_completa)
        proyectos_creados = codigos_extraidos if codigos_extraidos else []

        if aprendiz and respuesta_completa:
            try:
                aprendiz.aprender_interaccion(
                    prompt=prompt_original, respuesta=respuesta_completa,
                    lenguaje="", operador=OPERADOR_ACTUAL,
                    codigos_extraidos=codigos_extraidos,
                )
            except Exception:
                pass

        yield f"data: {json.dumps({'final': True, 'proyectos': proyectos_creados})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def generar_respuesta_stream_directo(prompt_completo: str, prompt_original: str):
    try:
        respuesta_completa = ""
        for data in ia.enviar_mensaje_stream(prompt_completo, "", ""):
            if 'error' in data:
                yield f"data: {json.dumps({'error': data['error']})}\n\n"
                break
            if 'chunk' in data:
                respuesta_completa += data['chunk']
                yield f"data: {json.dumps({'chunk': data['chunk']})}\n\n"
            if data.get('final', False):
                break

        codigos_extraidos = extraer_todos_los_codigos(respuesta_completa)
        proyectos_creados = codigos_extraidos if codigos_extraidos else []

        if aprendiz and respuesta_completa:
            try:
                aprendiz.aprender_interaccion(
                    prompt=prompt_original, respuesta=respuesta_completa,
                    lenguaje="", operador=OPERADOR_ACTUAL,
                    codigos_extraidos=codigos_extraidos,
                )
            except Exception:
                pass

        yield f"data: {json.dumps({'final': True, 'proyectos': proyectos_creados})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def extraer_todos_los_codigos(respuesta: str) -> List[Dict]:
    codigos = []
    patron = r'```(\w*)\n(.*?)```'
    matches = re.findall(patron, respuesta, re.DOTALL)
    for i, (lenguaje, codigo) in enumerate(matches):
        codigo = codigo.strip()
        if codigo:
            lang_real = lenguaje.lower() if lenguaje else 'python'
            if lang_real in ['py', 'python']: lang_real = 'python'
            elif lang_real in ['js', 'javascript']: lang_real = 'javascript'
            elif lang_real in ['html', 'htm']: lang_real = 'html'
            elif lang_real in ['cpp', 'c++']: lang_real = 'cpp'
            elif lang_real in ['java']: lang_real = 'java'
            nombre = f"codigo_{datetime.now().strftime('%H%M%S')}_{i+1}"
            codigos.append({'codigo': codigo, 'lenguaje': lang_real, 'nombre': nombre, 'origen': 'ia'})
    return codigos


@app.route('/crear_codigo', methods=['POST'])
def crear_codigo():
    try:
        data = request.get_json()
        respuesta = data.get('respuesta', '')
        codigos = extraer_todos_los_codigos(respuesta)
        return jsonify({'success': True, 'proyectos': codigos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/guardar_codigo', methods=['POST'])
def guardar_codigo():
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        codigo = data.get('codigo')
        lenguaje = data.get('lenguaje', 'python')
        if not editor:
            return jsonify({'success': False, 'error': 'Editor no inicializado'}), 500
        nombre_sin_ext = os.path.splitext(nombre)[0]
        proyecto = editor.crear_archivo(codigo, nombre_sin_ext, lenguaje)
        return jsonify({'success': True, 'proyecto': proyecto})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/guardar_como', methods=['POST'])
def guardar_como():
    if not TKINTER_OK:
        return jsonify({'success': False, 'error': 'tkinter no disponible'})

    try:
        data = request.get_json()
        nombre_sugerido = data.get('nombre', 'codigo.txt')
        contenido = data.get('contenido', '')

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        ext = os.path.splitext(nombre_sugerido)[1] or '.txt'

        ruta = filedialog.asksaveasfilename(
            parent=root,
            title="Guardar archivo como...",
            initialfile=nombre_sugerido,
            defaultextension=ext,
            filetypes=[
                ("Todos los archivos", "*.*"),
                ("Python", "*.py"),
                ("JavaScript", "*.js"),
                ("TypeScript", "*.ts"),
                ("HTML", "*.html"),
                ("CSS", "*.css"),
                ("C++", "*.cpp"),
                ("C", "*.c"),
                ("Java", "*.java"),
                ("JSON", "*.json"),
                ("Texto", "*.txt"),
                ("Markdown", "*.md"),
            ]
        )
        root.destroy()

        if not ruta:
            return jsonify({'success': False, 'error': 'Cancelado'})

        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)

        print(f"💾 Guardado en: {ruta}")

        if aprendiz:
            try:
                aprendiz.aprender_codigo(
                    codigo=contenido,
                    lenguaje=os.path.splitext(ruta)[1].lstrip('.'),
                    nombre=os.path.basename(ruta),
                    origen='usuario_guardado',
                    prompt='guardado manual',
                )
            except Exception:
                pass

        return jsonify({'success': True, 'ruta': ruta})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/ejecutar_codigo', methods=['POST'])
def ejecutar_codigo():
    try:
        data = request.get_json()
        nombre = data.get('nombre', 'script.py')
        codigo = data.get('codigo', '')
        lenguaje = data.get('lenguaje', 'python')
        if not codigo:
            return jsonify({'success': False, 'error': 'Sin código'}), 400

        ext = os.path.splitext(nombre)[1] or '.txt'
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=ext, delete=False,
            encoding='utf-8', errors='replace'
        ) as tmp:
            tmp.write(codigo)
            tmp_path = tmp.name

        try:
            resultado = _ejecutar_temporal(tmp_path, lenguaje)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return jsonify(resultado)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _ejecutar_temporal(ruta: str, lenguaje: str) -> Dict:
    import subprocess
    import shutil as _sh
    try:
        if lenguaje in ('python', 'py'):
            r = subprocess.run([sys.executable, ruta], capture_output=True,
                               text=True, timeout=30, encoding='utf-8', errors='replace')
            return {'success': r.returncode == 0, 'output': r.stdout or '',
                    'error': r.stderr if r.returncode != 0 else None}
        elif lenguaje in ('javascript', 'js'):
            node = _sh.which('node')
            if not node:
                return {'success': False, 'error': 'Node.js no instalado', 'output': ''}
            r = subprocess.run([node, ruta], capture_output=True,
                               text=True, timeout=30, encoding='utf-8', errors='replace')
            return {'success': r.returncode == 0, 'output': r.stdout or '',
                    'error': r.stderr if r.returncode != 0 else None}
        else:
            return {'success': False, 'error': f'Lenguaje {lenguaje} no soportado', 'output': ''}
    except Exception as e:
        return {'success': False, 'error': str(e), 'output': ''}


# ============================================================
# SERVIDOR FLASK EN HILO APARTE
# ============================================================
def iniciar_flask():
    global servidor_flask
    from werkzeug.serving import make_server
    servidor_flask = make_server(HOST, PORT, app, threaded=True)
    servidor_flask.serve_forever()


def esperar_servidor(timeout=15):
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


# ============================================================
# ABRIR VENTANA CON FALLBACK AUTOMÁTICO
# ============================================================
def _backend_disponible(nombre: str) -> bool:
    """Comprueba si un backend de pywebview es importable."""
    try:
        if nombre == 'qt':
            import qtpy  # noqa: F401
            return True
        if nombre == 'gtk':
            import gi  # noqa: F401
            return True
    except Exception:
        return False
    return False


def abrir_ventana():
    """Intenta abrir la ventana con Qt, luego GTK, y si no, abre el navegador."""
    if not PYWEBVIEW_OK:
        print("⚠️ pywebview no disponible. Abriendo en el navegador...")
        return _abrir_en_navegador()

    # 1. Intentar Qt (más estable en Ubuntu 26.04)
    if _backend_disponible('qt'):
        print("🪟 Abriendo ventana con backend Qt...")
        try:
            webview.create_window(
                title="MyndTeks · Modulación de Programación de Equipo de Trabajo",
                url=URL,
                width=1400,
                height=900,
                min_size=(900, 600),
                resizable=True,
                text_select=True,
            )
            webview.start(debug=False, gui='qt')
            return
        except Exception as e:
            print(f"⚠️ Falló el backend Qt: {e}")

    # 2. Intentar GTK
    if _backend_disponible('gtk'):
        print("🪟 Abriendo ventana con backend GTK...")
        try:
            webview.create_window(
                title="MyndTeks · Modulación de Programación de Equipo de Trabajo",
                url=URL,
                width=1400,
                height=900,
                min_size=(900, 600),
                resizable=True,
                text_select=True,
            )
            webview.start(debug=False, gui='gtk')
            return
        except Exception as e:
            print(f"⚠️ Falló el backend GTK: {e}")

    # 3. Fallback: navegador
    print("⚠️ Ningún backend nativo funcionó. Abriendo en el navegador...")
    _abrir_en_navegador()


def _abrir_en_navegador():
    import webbrowser
    webbrowser.open(URL)
    print(f"🌐 App abierta en: {URL}")
    print("   (deja esta terminal abierta para no cerrar el servidor)")
    try:
        # Mantener vivo el proceso principal (Flask corre en hilo daemon)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


# ============================================================
# CIERRE LIMPIO
# ============================================================
def cerrar_todo():
    print("\n🛑 Cerrando aplicación...")
    if ia:
        try:
            ia.detener()
        except Exception:
            pass
    if servidor_flask:
        try:
            servidor_flask.shutdown()
        except Exception:
            pass
    if aprendiz:
        try:
            stats = aprendiz.estadisticas()
            print(f"🧠 Conocimiento guardado: "
                  f"{stats['total_codigos']} códigos · "
                  f"{stats['total_prompts']} prompts")
        except Exception:
            pass
    print("👋 ¡Hasta luego!")
    os._exit(0)


# ============================================================
# MAIN
# ============================================================
def main():
    global ia, editor, aprendiz

    print("=" * 70)
    print("🚀 MYNDTEKS · MODULACIÓN DE PROGRAMACIÓN DE EQUIPO DE TRABAJO")
    print("=" * 70)
    print(f"📁 Directorio base: {BASE_DIR}")
    print(f"📁 Templates: {TEMPLATE_DIR}")
    print("=" * 70)

    try:
        editor = CodeEditor()
        if hasattr(editor, 'inicializar'):
            if not editor.inicializar():
                print("⚠️ Advertencia al inicializar el editor.")
    except Exception as e:
        print(f"❌ Error al crear el editor: {e}")
        sys.exit(1)

    if Aprendiz:
        try:
            aprendiz = Aprendiz()
            stats = aprendiz.estadisticas()
            print(f"🧠 Sistema de aprendizaje activo")
            print(f"   📂 Carpeta: {stats['carpeta']}")
            print(f"   📊 Conocimiento: "
                  f"{stats['total_codigos']} códigos · "
                  f"{stats['total_prompts']} prompts")
        except Exception as e:
            print(f"⚠️ Error al inicializar el aprendiz: {e}")
            aprendiz = None

    try:
        ia = crear_ia(tipo='coder')
        if not ia.iniciar():
            print("❌ La IA no pudo iniciar.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error al inicializar la IA: {e}")
        sys.exit(1)

    hilo_flask = threading.Thread(target=iniciar_flask, daemon=True)
    hilo_flask.start()
    print(f"⏳ Esperando a que Flask responda en {URL} ...")

    if not esperar_servidor(timeout=15):
        print("❌ El servidor Flask no respondió a tiempo.")
        sys.exit(1)

    print(f"✅ Servidor Flask listo en {URL}")

    # Abrir ventana (con fallback automático Qt -> GTK -> navegador)
    abrir_ventana()
    cerrar_todo()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        cerrar_todo()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        os._exit(1)