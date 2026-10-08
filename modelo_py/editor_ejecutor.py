# editor_ejecutor.py
"""
editor_ejecutor.py - Editor y ejecutor de código portable
Ubicación: chat_programar_IA\modelo_py\editor_ejecutor.py

Responsabilidades:
  • Crear y guardar archivos de código en disco.
  • Ejecutar código Python y devolver stdout/stderr.
  • Renderizar HTML (se sirve al frontend vía iframe).
  • Listar proyectos guardados.
  • Compilar/ejecutar C++ y Java si están disponibles en el sistema.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from typing import Dict, List, Optional, Any


class CodeEditor:
    """Gestor de archivos y ejecutor de código."""

    # Extensiones soportadas por lenguaje
    EXTENSIONES = {
        'python':     '.py',
        'py':         '.py',
        'javascript': '.js',
        'js':         '.js',
        'html':       '.html',
        'htm':        '.html',
        'css':        '.css',
        'cpp':        '.cpp',
        'c++':        '.cpp',
        'c':          '.c',
        'java':       '.java',
        'json':       '.json',
        'txt':        '.txt',
        'texto':      '.txt',
        'markdown':   '.md',
        'md':         '.md',
    }

    def __init__(self, proyectos_dir: Optional[str] = None):
        # Carpeta por defecto: <raíz_proyecto>/proyectos
        base = os.path.dirname(os.path.abspath(__file__))
        raiz = os.path.dirname(base)  # sube un nivel desde modelo_py/
        self.proyectos_dir = proyectos_dir or os.path.join(raiz, 'proyectos')
        self.proyectos: Dict[str, Dict[str, Any]] = {}
        self.inicializado = False

    # ------------------------------------------------------------------
    # INICIALIZACIÓN
    # ------------------------------------------------------------------
    def inicializar(self) -> bool:
        try:
            os.makedirs(self.proyectos_dir, exist_ok=True)
            self.inicializado = True
            print(f"✅ Editor inicializado. Carpeta de proyectos: {self.proyectos_dir}")
            return True
        except Exception as e:
            print(f"❌ Error al inicializar el editor: {e}")
            return False

    # ------------------------------------------------------------------
    # CREAR / GUARDAR ARCHIVOS
    # ------------------------------------------------------------------
    def crear_archivo(self, codigo: str, nombre: str, lenguaje: str = 'python') -> Optional[Dict[str, Any]]:
        """
        Crea (o sobreescribe) un archivo en disco con el código dado.
        Devuelve un dict con metadatos del proyecto o None si falla.
        """
        if not self.inicializado:
            self.inicializar()

        try:
            lenguaje_norm = (lenguaje or 'python').lower().strip()
            extension = self.EXTENSIONES.get(lenguaje_norm, '.txt')

            # Asegurar nombre sin extensión duplicada
            nombre_base = os.path.splitext(nombre)[0]
            nombre_archivo = f"{nombre_base}{extension}"
            ruta = os.path.join(self.proyectos_dir, nombre_archivo)

            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(codigo)

            info = {
                'nombre': nombre_archivo,
                'codigo': codigo,
                'lenguaje': lenguaje_norm,
                'ruta': ruta,
            }
            self.proyectos[nombre_archivo] = info
            print(f"📄 Archivo creado: {nombre_archivo}")
            return info

        except Exception as e:
            print(f"❌ Error al crear archivo '{nombre}': {e}")
            return None

    # ------------------------------------------------------------------
    # EJECUTAR
    # ------------------------------------------------------------------
    def ejecutar(self, nombre: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Ejecuta el archivo indicado. Devuelve dict con:
          { success: bool, output: str, error: str|None }
        """
        info = self.proyectos.get(nombre)

        # Si no lo tenemos en memoria, buscar en disco
        if info is None:
            ruta_disco = os.path.join(self.proyectos_dir, nombre)
            if os.path.exists(ruta_disco):
                lenguaje = self._detectar_lenguaje_por_extension(nombre)
                info = {
                    'nombre': nombre,
                    'codigo': open(ruta_disco, 'r', encoding='utf-8').read(),
                    'lenguaje': lenguaje,
                    'ruta': ruta_disco,
                }
                self.proyectos[nombre] = info
            else:
                return {'success': False, 'error': f"Archivo '{nombre}' no encontrado.", 'output': ''}

        lenguaje = info['lenguaje']
        ruta = info['ruta']

        try:
            if lenguaje in ('python', 'py'):
                return self._ejecutar_python(ruta, timeout)
            elif lenguaje in ('javascript', 'js'):
                return self._ejecutar_javascript(ruta, timeout)
            elif lenguaje in ('html', 'htm'):
                # El HTML se renderiza en el navegador (iframe del frontend)
                return {
                    'success': True,
                    'output': '🌐 HTML listo para previsualizar en el navegador.',
                    'error': None,
                }
            elif lenguaje in ('cpp', 'c++'):
                return self._ejecutar_cpp(ruta, timeout)
            elif lenguaje == 'java':
                return self._ejecutar_java(ruta, timeout)
            else:
                return {
                    'success': False,
                    'error': f"Lenguaje '{lenguaje}' no soportado para ejecución.",
                    'output': '',
                }
        except Exception as e:
            return {'success': False, 'error': f"Error de ejecución: {e}", 'output': ''}

    # ------------------------------------------------------------------
    # EJECUTORES ESPECÍFICOS
    # ------------------------------------------------------------------
    def _ejecutar_python(self, ruta: str, timeout: int) -> Dict[str, Any]:
        resultado = subprocess.run(
            [sys.executable, ruta],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
        )
        return {
            'success': resultado.returncode == 0,
            'output': resultado.stdout or '',
            'error': resultado.stderr if resultado.returncode != 0 else None,
        }

    def _ejecutar_javascript(self, ruta: str, timeout: int) -> Dict[str, Any]:
        node = shutil.which('node')
        if not node:
            return {
                'success': False,
                'error': 'Node.js no está instalado o no está en el PATH.',
                'output': '',
            }
        resultado = subprocess.run(
            [node, ruta],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
        )
        return {
            'success': resultado.returncode == 0,
            'output': resultado.stdout or '',
            'error': resultado.stderr if resultado.returncode != 0 else None,
        }

    def _ejecutar_cpp(self, ruta: str, timeout: int) -> Dict[str, Any]:
        gpp = shutil.which('g++')
        if not gpp:
            return {
                'success': False,
                'error': 'g++ no está instalado o no está en el PATH.',
                'output': '',
            }
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, 'programa.exe' if os.name == 'nt' else 'programa')
            compilacion = subprocess.run(
                [gpp, ruta, '-o', exe],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
            )
            if compilacion.returncode != 0:
                return {
                    'success': False,
                    'error': f"Error de compilación:\n{compilacion.stderr}",
                    'output': '',
                }
            ejecucion = subprocess.run(
                [exe],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
            )
            return {
                'success': ejecucion.returncode == 0,
                'output': ejecucion.stdout or '',
                'error': ejecucion.stderr if ejecucion.returncode != 0 else None,
            }

    def _ejecutar_java(self, ruta: str, timeout: int) -> Dict[str, Any]:
        javac = shutil.which('javac')
        java = shutil.which('java')
        if not javac or not java:
            return {
                'success': False,
                'error': 'Java (javac/java) no está instalado o no está en el PATH.',
                'output': '',
            }
        with tempfile.TemporaryDirectory() as tmp:
            copia = os.path.join(tmp, os.path.basename(ruta))
            shutil.copy(ruta, copia)
            compilacion = subprocess.run(
                [javac, copia],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
            )
            if compilacion.returncode != 0:
                return {
                    'success': False,
                    'error': f"Error de compilación:\n{compilacion.stderr}",
                    'output': '',
                }
            clase = os.path.splitext(os.path.basename(ruta))[0]
            ejecucion = subprocess.run(
                [java, '-cp', tmp, clase],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
            )
            return {
                'success': ejecucion.returncode == 0,
                'output': ejecucion.stdout or '',
                'error': ejecucion.stderr if ejecucion.returncode != 0 else None,
            }

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------
    def _detectar_lenguaje_por_extension(self, nombre: str) -> str:
        ext = os.path.splitext(nombre)[1].lower()
        for lenguaje, extension in self.EXTENSIONES.items():
            if extension == ext:
                return lenguaje
        return 'txt'

    def listar_proyectos(self) -> List[Dict[str, Any]]:
        """Devuelve la lista de proyectos registrados."""
        return list(self.proyectos.values())

    def listar_archivos_disco(self) -> List[str]:
        """Lista los archivos realmente presentes en la carpeta de proyectos."""
        if not os.path.isdir(self.proyectos_dir):
            return []
        return [
            f for f in os.listdir(self.proyectos_dir)
            if os.path.isfile(os.path.join(self.proyectos_dir, f))
        ]

    def obtener_codigo(self, nombre: str) -> Optional[str]:
        """Devuelve el código fuente guardado en memoria o disco."""
        info = self.proyectos.get(nombre)
        if info:
            return info['codigo']
        ruta = os.path.join(self.proyectos_dir, nombre)
        if os.path.exists(ruta):
            with open(ruta, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def eliminar_archivo(self, nombre: str) -> bool:
        """Elimina un archivo del disco y del registro en memoria."""
        try:
            ruta = os.path.join(self.proyectos_dir, nombre)
            if os.path.exists(ruta):
                os.remove(ruta)
            self.proyectos.pop(nombre, None)
            return True
        except Exception as e:
            print(f"❌ Error al eliminar '{nombre}': {e}")
            return False