"""
prom.py - Módulo de gestión de prompts para la IA
Ubicación: chat_programar_IA\modelo_py\prom.py

DISEÑO PRINCIPAL:
  - El prompt NO impone reglas de formato a la IA.
  - La IA hace LITERALMENTE lo que el usuario pide en lenguaje natural.
  - El prompt solo:
      1. Envuelve los archivos con el ojo activo (nombre, lenguaje, líneas numeradas).
      2. Añade el mensaje del usuario tal cual.
      3. Deja que la IA responda como quiera.
  - El frontend detecta automáticamente el formato de la respuesta:
      · Bloques ``` con líneas numeradas "N | código" → aplica al editor
      · Líneas "LINEA N: código"                    → aplica al editor
      · Bloques ``` sin numerar                     → abre pestaña nueva
      · Texto normal                                → lo muestra en el chat
  - Mantiene memoria de hilo conversacional con ventana deslizante.
"""

import os
from typing import Dict, List, Optional


class PromptManager:
    # ============================================================
    # CONFIGURACIÓN DE MEMORIA
    # ============================================================
    MAX_HISTORIAL_MENSAJES = 8
    MAX_TOKENS_HISTORIAL = 3000
    MAX_CHARS_MENSAJE_HISTORIAL = 2500
    MAX_FILE_CHARS = 8000

    def __init__(self):
        self.max_context_tokens = 4096
        self.max_file_chars = self.MAX_FILE_CHARS

        self.mapa_extension_lenguaje = {
            'py': 'python', 'pyw': 'python', 'pyi': 'python',
            'js': 'javascript', 'jsx': 'javascript', 'mjs': 'javascript', 'cjs': 'javascript',
            'ts': 'typescript', 'tsx': 'typescript',
            'html': 'html', 'htm': 'html',
            'css': 'css', 'scss': 'css', 'sass': 'css', 'less': 'css',
            'cpp': 'cpp', 'cc': 'cpp', 'cxx': 'cpp', 'h': 'cpp', 'hpp': 'cpp', 'hxx': 'cpp',
            'c': 'c',
            'java': 'java', 'kt': 'kotlin', 'kts': 'kotlin',
            'scala': 'scala', 'groovy': 'groovy',
            'cs': 'csharp', 'vb': 'vbnet', 'fs': 'fsharp',
            'go': 'go', 'rs': 'rust', 'rb': 'ruby', 'php': 'php',
            'swift': 'swift', 'dart': 'dart', 'lua': 'lua',
            'r': 'r', 'jl': 'julia',
            'pl': 'perl', 'pm': 'perl',
            'sh': 'bash', 'bash': 'bash', 'zsh': 'bash', 'fish': 'bash',
            'bat': 'batch', 'cmd': 'batch', 'ps1': 'powershell', 'psm1': 'powershell',
            'sql': 'sql', 'graphql': 'graphql', 'gql': 'graphql',
            'json': 'json', 'xml': 'xml', 'yaml': 'yaml', 'yml': 'yaml',
            'toml': 'toml', 'ini': 'ini', 'cfg': 'ini', 'conf': 'ini',
            'env': 'dotenv', 'properties': 'properties',
            'md': 'markdown', 'markdown': 'markdown', 'rst': 'rst',
            'txt': 'texto', 'log': 'texto', 'csv': 'csv', 'tsv': 'tsv',
            'asm': 'asm', 's': 'asm', 'tex': 'latex', 'bib': 'latex',
            'vue': 'vue', 'svelte': 'svelte', 'astro': 'astro',
            'ipynb': 'jupyter',
        }

    # ============================================================
    # UTILIDADES
    # ============================================================
    def _estimar_tokens(self, texto: str) -> int:
        return len(texto) // 4 if isinstance(texto, str) else 0

    def detectar_lenguaje_por_extension(self, file_name: str) -> Optional[str]:
        if not file_name:
            return None
        ext = os.path.splitext(file_name)[1].lower().lstrip('.')
        if not ext:
            nombre_bajo = file_name.lower()
            if nombre_bajo == 'dockerfile': return 'dockerfile'
            if nombre_bajo == 'makefile':   return 'makefile'
            if nombre_bajo == 'cmake':      return 'cmake'
            return None
        return self.mapa_extension_lenguaje.get(ext, ext)

    # ============================================================
    # SYSTEM PROMPT — SIN REGLAS DE FORMATO
    # Solo define el rol y el idioma.
    # ============================================================
    def get_system_prompt(self, tipo='default') -> str:
        return (
            "Eres un asistente experto en programación. "
            "Haces exactamente lo que el usuario te pide, ni más ni menos. "
            "Cuando te adjunten archivos, los verás con su nombre, lenguaje "
            "y las líneas numeradas. Úsalos como contexto para responder. "
            "Respondes SIEMPRE en español, de forma clara y directa."
        )

    # ============================================================
    # CONSTRUCCIÓN DEL PROMPT
    # ============================================================
    def construir_prompt_archivo(
        self,
        file_name: str = "",
        file_content: str = "",
        user_message: str = "",
        tipo_analisis: str = 'auto',
        archivos_multiples: Optional[List[Dict]] = None,
    ) -> Dict:
        system_prompt = self.get_system_prompt()
        bloque_archivos = ""

        if archivos_multiples:
            for arch in archivos_multiples:
                nombre = arch.get('nombre', 'archivo')
                contenido = arch.get('contenido', '')
                lenguaje = (
                    arch.get('lenguaje')
                    or self.detectar_lenguaje_por_extension(nombre)
                    or 'texto'
                )
                numerado = arch.get('numerado', True)

                if numerado:
                    lineas = contenido.split('\n')
                    contenido_mostrar = '\n'.join(
                        f"{i+1:4d} | {l}" for i, l in enumerate(lineas)
                    )
                else:
                    contenido_mostrar = contenido

                bloque_archivos += (
                    f"\n\n=== ARCHIVO: {nombre} ===\n"
                    f"Lenguaje: {lenguaje}\n"
                    f"Total líneas: {len(contenido.split(chr(10)))}\n"
                    f"Contenido:\n"
                    f"{contenido_mostrar[:self.max_file_chars]}\n"
                    f"=== FIN: {nombre} ==="
                )

        elif file_content:
            lenguaje = self.detectar_lenguaje_por_extension(file_name) or 'texto'
            lineas = file_content.split('\n')
            contenido_numerado = '\n'.join(
                f"{i+1:4d} | {l}" for i, l in enumerate(lineas)
            )
            bloque_archivos = (
                f"\n\n=== ARCHIVO: {file_name or 'archivo'} ===\n"
                f"Lenguaje: {lenguaje}\n"
                f"Total líneas: {len(lineas)}\n"
                f"Contenido:\n"
                f"{contenido_numerado[:self.max_file_chars]}\n"
                f"=== FIN: {file_name or 'archivo'} ==="
            )

        prompt = (
            f"{system_prompt}\n\n"
            f"{user_message or '(sin texto)'}"
            f"{bloque_archivos}"
        )

        return {
            'prompt': prompt,
            'metadatos': {'tipo': 'archivo' if bloque_archivos else 'texto'},
            'tokens_estimados': self._estimar_tokens(prompt),
            'lenguaje_detectado': (
                self.detectar_lenguaje_por_extension(file_name)
                if file_name else 'texto'
            ),
        }

    # ============================================================
    # MEMORIA DE HILO
    # ============================================================
    def optimizar_historial(self, historial: List[Dict], max_mensajes: int = None) -> List[Dict]:
        if not historial:
            return historial

        max_msgs = max_mensajes if max_mensajes is not None else self.MAX_HISTORIAL_MENSAJES

        sistema = [m for m in historial if m.get('role') == 'system']
        resto = [m for m in historial if m.get('role') != 'system']

        resto_recortado = []
        for m in resto:
            contenido = m.get('content', '')
            if isinstance(contenido, str) and len(contenido) > self.MAX_CHARS_MENSAJE_HISTORIAL:
                contenido = contenido[:self.MAX_CHARS_MENSAJE_HISTORIAL] + "\n[...recortado]"
                m = dict(m, content=contenido)
            resto_recortado.append(m)

        if len(resto_recortado) > max_msgs:
            resto_recortado = resto_recortado[-max_msgs:]

        resultado = []
        tokens_acumulados = 0
        for m in reversed(resto_recortado):
            contenido = m.get('content', '')
            tokens_msg = self._estimar_tokens(contenido)
            if tokens_acumulados + tokens_msg > self.MAX_TOKENS_HISTORIAL:
                break
            resultado.insert(0, m)
            tokens_acumulados += tokens_msg

        return sistema + resultado

    # ============================================================
    # DEBUG
    # ============================================================
    def resumir_historial(self, historial: List[Dict]) -> str:
        if not historial:
            return "(historial vacío)"
        lineas = [f"📜 Historial ({len(historial)} mensajes):"]
        for i, m in enumerate(historial):
            rol = m.get('role', '?')
            contenido = m.get('content', '')
            preview = contenido[:80].replace('\n', ' ') if isinstance(contenido, str) else ''
            tokens = self._estimar_tokens(contenido)
            lineas.append(f"  [{i}] {rol:>9}: {preview}... (~{tokens} tok)")
        total = sum(self._estimar_tokens(m.get('content', '')) for m in historial)
        lineas.append(f"  Total: ~{total} tokens")
        return "\n".join(lineas)


# ==================================================================
# FUNCIONES DE CONVENIENCIA
# ==================================================================
def crear_prompt_ia(file_content: str, file_name: str = "",
                     user_message: str = "", tipo_prompt: str = 'default') -> str:
    manager = PromptManager()
    return manager.construir_prompt_archivo(
        file_name=file_name,
        file_content=file_content,
        user_message=user_message,
    )['prompt']


def crear_prompt_con_archivos(archivos: List[Dict], user_message: str = "") -> str:
    manager = PromptManager()
    return manager.construir_prompt_archivo(
        user_message=user_message,
        archivos_multiples=archivos,
    )['prompt']