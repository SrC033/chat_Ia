"""
ia.py - Módulo principal de la IA usando llama-cpp-python
Ubicación: chat_programar_IA/modelo_py/ia.py

Características:
  - Auto-detección de cualquier archivo .gguf en ../modelo_IA/
  - Límite de 500 tokens de respuesta (equilibrio velocidad/uso)
  - Optimizado para i7-12700 (12 núcleos físicos)
  - chat_format autodetectado por llama.cpp
"""

import os
import sys
import time
import glob
from typing import Dict, List, Optional, Any, Generator

try:
    from llama_cpp import Llama
except ImportError:
    print("⚠️ Falta instalar la librería llama-cpp-python. Ejecuta: pip install llama-cpp-python")
    Llama = None

try:
    from .prom import PromptManager, crear_prompt_ia
except ImportError:
    try:
        from prom import PromptManager, crear_prompt_ia
    except ImportError:
        class PromptManager:
            def __init__(self):
                self.max_file_chars = 2000
            def construir_prompt_archivo(self, file_name, file_content, user_message, tipo_analisis='default', archivos_multiples=None):
                return {'prompt': f"{user_message}\n{file_content[:2000]}",
                        'metadatos': {}, 'tokens_estimados': 0,
                        'es_peticion_codigo': True, 'lenguaje_detectado': 'texto'}
            def get_system_prompt(self, tipo='default'):
                return "Programador experto. Devuelve código funcional en bloques Markdown. Español."
            def optimizar_historial(self, historial, max_mensajes):
                return historial

try:
    from .editor_ejecutor import CodeEditor
except ImportError:
    try:
        from editor_ejecutor import CodeEditor
    except ImportError:
        class CodeEditor:
            def __init__(self): pass
            def inicializar(self): return True
            def crear_archivo(self, codigo, nombre, lenguaje):
                return {'nombre': f"{nombre}.py", 'codigo': codigo, 'lenguaje': lenguaje}
            def ejecutar(self, nombre):
                return {'success': False, 'error': 'Editor no disponible'}
            def listar_proyectos(self): return []
            def obtener_codigo(self, nombre): return None


# ==================================================================
# DETECCIÓN AUTOMÁTICA DE MODELOS
# ==================================================================
def detectar_modelos(carpeta: str) -> List[str]:
    """Devuelve la lista de archivos .gguf en la carpeta, ordenados por prioridad."""
    if not os.path.isdir(carpeta):
        return []

    archivos = glob.glob(os.path.join(carpeta, "*.gguf"))
    if not archivos:
        return []

    def prioridad(ruta: str) -> int:
        n = os.path.basename(ruta).lower()
        puntos = 0
        # Tamaño del modelo
        if "7b" in n:       puntos += 70
        elif "4b" in n:     puntos += 40
        elif "3b" in n:     puntos += 30
        elif "1.5b" in n:   puntos += 15
        elif "0.5b" in n:   puntos += 5
        # Tipo
        if "coder" in n:    puntos += 20
        if "instruct" in n: puntos += 5
        # Cuantización
        if "q5_k_m" in n:     puntos += 8
        elif "q4_k_m" in n:   puntos += 6
        elif "q4" in n:       puntos += 4
        return puntos

    return sorted(archivos, key=prioridad, reverse=True)


def elegir_modelo(carpeta: str) -> Optional[str]:
    """Elige el modelo a usar, respetando la variable CHAT_MODELO si existe."""
    forzado = os.environ.get("CHAT_MODELO", "").strip()
    if forzado:
        ruta = os.path.join(carpeta, forzado) if not os.path.isabs(forzado) else forzado
        if os.path.isfile(ruta):
            print(f"🎯 Modelo forzado por CHAT_MODELO: {os.path.basename(ruta)}")
            return ruta
        print(f"⚠️ CHAT_MODELO='{forzado}' no encontrado, buscando automáticamente...")

    modelos = detectar_modelos(carpeta)
    if not modelos:
        return None

    if len(modelos) == 1:
        print(f"🔍 Modelo detectado: {os.path.basename(modelos[0])}")
        return modelos[0]

    print(f"🔍 {len(modelos)} modelos detectados en {carpeta}:")
    for i, m in enumerate(modelos, 1):
        marca = "→" if i == 1 else " "
        print(f"   {marca} [{i}] {os.path.basename(m)}")
    print(f"✅ Usando por prioridad: {os.path.basename(modelos[0])}")
    return modelos[0]


# ==================================================================
# CONFIGURACIÓN
# ==================================================================
class IAConfig:
    """Configuración optimizada para i7-12700 + 14GB RAM."""

    def __init__(self):
        # ------------------------------------------------------
        # RUTA DEL MODELO (auto-detectada)
        # ------------------------------------------------------
        _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.modelo_dir = os.path.join(_base_dir, "modelo_IA")
        self.modelo_path = elegir_modelo(self.modelo_dir)

        # ------------------------------------------------------
        # ⚡ CPU OPTIMIZADO PARA i7-12700 (12 núcleos físicos)
        # ------------------------------------------------------
        self.n_threads = 12          # núcleos físicos (no los 20 hilos lógicos)
        self.n_gpu_layers = 0
        self.n_batch = 256
        self.use_mmap = True         # imprescindible con 14GB RAM
        self.use_mlock = False

        # ------------------------------------------------------
        # ⚡ CONTEXTO Y RESPUESTA
        # ------------------------------------------------------
        self.max_context_tokens = 4096
        self.max_response_tokens = 500        # ⭐ LÍMITE DE 500 TOKENS
        self.temperature = 0.1
        self.tipo_sistema = 'coder'
        self.max_historial = 4

        # ------------------------------------------------------
        # ⚡ GENERACIÓN (anti-bucles)
        # ------------------------------------------------------
        self.top_p = 0.9
        self.top_k = 40
        self.repeat_penalty = 1.15            # más alto = menos repeticiones
        self.chat_format = None               # autodetectado por llama.cpp

    def mostrar_configuracion(self):
        print("=" * 70)
        print("📋 CONFIGURACIÓN DEL MODELO")
        print("=" * 70)
        if self.modelo_path:
            print(f"📁 Modelo: {self.modelo_path}")
            print(f"📦 Tamaño: {os.path.getsize(self.modelo_path) / 1024 / 1024:.1f} MB")
        else:
            print("📁 Modelo: ❌ NO ENCONTRADO")
        print(f"🧵 Hilos CPU: {self.n_threads} (de {os.cpu_count()} hilos lógicos)")
        print(f"📦 Contexto: {self.max_context_tokens} tokens")
        print(f"📝 Respuesta máx: {self.max_response_tokens} tokens")
        print(f"⚡ Batch: {self.n_batch}")
        print(f"💾 mmap: {self.use_mmap} · mlock: {self.use_mlock}")
        print(f"🌡️ Temperatura: {self.temperature} · repeat_penalty: {self.repeat_penalty}")
        print("=" * 70)


# ==================================================================
# SERVIDOR DE IA
# ==================================================================
class IAServidor:
    def __init__(self, config: IAConfig):
        self.config = config
        self.llm = None
        self.activo = False

    def verificar(self) -> bool:
        return self.activo and self.llm is not None

    def iniciar(self) -> bool:
        if Llama is None:
            print("❌ ERROR: La librería 'llama-cpp-python' no está instalada.")
            return False

        if not self.config.modelo_path:
            print(f"❌ ERROR: No hay ningún archivo .gguf en: {self.config.modelo_dir}")
            print(f"   Descarga uno y colócalo ahí, por ejemplo:")
            print(f"   cd {self.config.modelo_dir}")
            print(f"   wget https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
            return False

        if not os.path.exists(self.config.modelo_path):
            print(f"❌ ERROR: No se encuentra el archivo .gguf: {self.config.modelo_path}")
            return False

        print(f"⏳ Cargando el modelo GGUF en memoria RAM...")
        t0 = time.time()
        try:
            kwargs = dict(
                model_path=self.config.modelo_path,
                n_ctx=self.config.max_context_tokens,
                n_threads=self.config.n_threads,
                n_gpu_layers=self.config.n_gpu_layers,
                n_batch=self.config.n_batch,
                use_mmap=self.config.use_mmap,
                use_mlock=self.config.use_mlock,
                verbose=False,
            )
            if self.config.chat_format:
                kwargs["chat_format"] = self.config.chat_format

            self.llm = Llama(**kwargs)
            self.activo = True
            print(f"✅ ¡Modelo cargado exitosamente en {time.time() - t0:.2f}s!")
            return True
        except Exception as e:
            print(f"❌ Error al cargar el modelo: {e}")
            return False

    def detener(self):
        self.llm = None
        self.activo = False
        print("🛑 Modelo descargado de la memoria.")

    def crear_chat_completion_stream(
        self, messages: List[Dict], temperature: float, max_tokens: int
    ) -> Generator:
        try:
            stream = self.llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                repeat_penalty=self.config.repeat_penalty,
                stream=True,
            )
            for chunk in stream:
                yield chunk
        except Exception as e:
            yield {'error': str(e)}

    def crear_chat_completion_sync(
        self, messages: List[Dict], temperature: float, max_tokens: int
    ) -> Dict:
        try:
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=self.config.top_p,
                top_k=self.config.top_k,
                repeat_penalty=self.config.repeat_penalty,
                stream=False,
            )
            return response
        except Exception as e:
            return {'error': str(e)}


# ==================================================================
# CHAT
# ==================================================================
class IAChat:
    def __init__(self, config: IAConfig, servidor: IAServidor):
        self.config = config
        self.servidor = servidor
        self.prompt_manager = PromptManager()
        self.editor = CodeEditor()
        self.historial = []
        self.inicializar_conversacion()

    def inicializar_conversacion(self):
        system_prompt = self.prompt_manager.get_system_prompt(self.config.tipo_sistema)
        self.historial = [{"role": "system", "content": system_prompt}]

    def reiniciar(self):
        self.inicializar_conversacion()
        print("🔄 Conversación reiniciada.")

    def agregar_mensaje(self, role: str, content: str):
        MAX_CHARS_HISTORIAL = 2000
        contenido = content[:MAX_CHARS_HISTORIAL] if len(content) > MAX_CHARS_HISTORIAL else content
        self.historial.append({"role": role, "content": contenido})
        self.historial = self.prompt_manager.optimizar_historial(
            self.historial,
            self.config.max_historial
        )

    def enviar_consulta_stream(self, user_message: str = "", file_content: str = "", file_name: str = ""):
        if not self.servidor.verificar():
            yield {'error': 'Motor de IA no inicializado', 'final': True}
            return

        if file_content:
            prompt_data = self.prompt_manager.construir_prompt_archivo(
                file_name=file_name or 'archivo',
                file_content=file_content,
                user_message=user_message,
            )
            contenido_actual = prompt_data['prompt']
        else:
            contenido_actual = user_message

        self.agregar_mensaje("user", contenido_actual)
        print(f"🔄 Generando respuesta en streaming...")
        respuesta_completa = ""

        stream = self.servidor.crear_chat_completion_stream(
            messages=self.historial,
            temperature=self.config.temperature,
            max_tokens=self.config.max_response_tokens,
        )

        for chunk in stream:
            if isinstance(chunk, dict) and 'error' in chunk:
                yield {'error': chunk['error'], 'final': True}
                return
            try:
                delta = chunk['choices'][0]['delta']
                content = delta.get('content', '')
                if content:
                    respuesta_completa += content
                    yield {'chunk': content, 'final': False}
            except (KeyError, IndexError):
                continue

        self.agregar_mensaje("assistant", respuesta_completa)
        yield {'final': True, 'proyecto': None}

    def enviar_consulta(self, user_message: str = "", file_content: str = "", file_name: str = "") -> Dict[str, Any]:
        if not self.servidor.verificar():
            return {'success': False, 'reply': "❌ Motor de IA no inicializado.", 'error': 'server_offline'}

        if file_content:
            prompt_data = self.prompt_manager.construir_prompt_archivo(
                file_name=file_name or 'archivo',
                file_content=file_content,
                user_message=user_message,
            )
            contenido_actual = prompt_data['prompt']
        else:
            contenido_actual = user_message

        self.agregar_mensaje("user", contenido_actual)

        response_data = self.servidor.crear_chat_completion_sync(
            messages=self.historial,
            temperature=self.config.temperature,
            max_tokens=self.config.max_response_tokens,
        )

        if 'error' in response_data:
            return {'success': False, 'reply': f"❌ Error de IA: {response_data['error']}", 'error': 'ia_error'}

        try:
            bot_reply = response_data['choices'][0]['message']['content']
            self.agregar_mensaje("assistant", bot_reply)
            return {'success': True, 'reply': bot_reply,
                    'metadatos': {'tipo': 'mensaje_solo'}, 'proyecto_creado': None}
        except (KeyError, IndexError) as e:
            return {'success': False, 'reply': f"❌ Error procesando respuesta: {str(e)}", 'error': 'parse_error'}

    def obtener_historial(self):
        return self.historial

    def limpiar_historial(self):
        self.inicializar_conversacion()


# ==================================================================
# INTERFAZ PRINCIPAL
# ==================================================================
class IA:
    def __init__(self, config: Optional[IAConfig] = None):
        self.config = config or IAConfig()
        self.servidor = IAServidor(self.config)
        self.chat = IAChat(self.config, self.servidor)
        self.initialized = False

    def get_prompt_manager(self):
        return self.chat.prompt_manager

    def iniciar(self) -> bool:
        self.config.mostrar_configuracion()
        if self.servidor.iniciar():
            self.initialized = True
            return True
        return False

    def detener(self):
        self.servidor.detener()
        self.initialized = False

    def enviar_mensaje(self, mensaje: str, archivo_contenido: str = "", archivo_nombre: str = ""):
        if not self.initialized:
            return {'success': False, 'reply': "❌ IA no inicializada."}
        return self.chat.enviar_consulta(mensaje, archivo_contenido, archivo_nombre)

    def enviar_mensaje_stream(self, mensaje: str, archivo_contenido: str = "", archivo_nombre: str = ""):
        if not self.initialized:
            yield {'error': "❌ IA no inicializada.", 'final': True}
            return
        yield from self.chat.enviar_consulta_stream(mensaje, archivo_contenido, archivo_nombre)

    def reiniciar_conversacion(self):
        self.chat.reiniciar()

    def esta_activo(self) -> bool:
        return self.initialized and self.servidor.verificar()

    def get_config(self) -> IAConfig:
        return self.config


def crear_ia(tipo='coder', puerto=8081):
    config = IAConfig()
    config.tipo_sistema = tipo
    return IA(config)