# aprender.py
"""
aprender.py - Sistema de aprendizaje y memoria del modelo

Guarda en la carpeta del modelo (modelo_IA/aprendido/) todo lo que el usuario
sube o pide: código, prompts, estructuras, patrones y preferencias. Así el
modelo puede "recordar" y reutilizar el conocimiento en futuras consultas.

Estructura generada:
    modelo_IA/
    └── aprendido/
        ├── indice.json              # Índice general de todo lo aprendido
        ├── codigos/                 # Fragmentos de código aprendidos
        │   └── <hash>.json
        ├── prompts/                 # Patrones de prompts del usuario
        │   └── <hash>.json
        ├── estructuras/             # Estructuras de código (funciones, clases)
        │   └── <hash>.json
        ├── preferencias.json        # Lenguajes, estilos, temas preferidos
        └── historial.jsonl          # Historial completo (línea por línea)
"""

import os
import re
import json
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Any


class Aprendiz:
    """Gestor de aprendizaje y memoria persistente del modelo."""

    # ------------------------------------------------------------------
    # CONFIGURACIÓN
    # ------------------------------------------------------------------
    VERSION = "1.0"
    MAX_HISTORIAL = 5000          # máximo de entradas en historial.jsonl
    MAX_CODIGOS = 2000            # máximo de fragmentos de código guardados
    MAX_PROMPTS = 2000            # máximo de prompts guardados
    MAX_ESTRUCTURAS = 1000        # máximo de estructuras guardadas

    # ------------------------------------------------------------------
    # INICIALIZACIÓN
    # ------------------------------------------------------------------
    def __init__(self, modelo_dir: Optional[str] = None):
        """
        :param modelo_dir: Ruta a la carpeta del modelo.
                          Si es None, usa: <raíz_proyecto>/modelo_IA
        """
        if modelo_dir is None:
            base = os.path.dirname(os.path.abspath(__file__))
            raiz = os.path.dirname(base)  # sube un nivel desde modelo_py/
            modelo_dir = os.path.join(raiz, 'modelo_IA')

        self.modelo_dir = modelo_dir
        self.aprendido_dir = os.path.join(modelo_dir, 'aprendido')
        self.codigos_dir = os.path.join(self.aprendido_dir, 'codigos')
        self.prompts_dir = os.path.join(self.aprendido_dir, 'prompts')
        self.estructuras_dir = os.path.join(self.aprendido_dir, 'estructuras')

        self.indice_path = os.path.join(self.aprendido_dir, 'indice.json')
        self.preferencias_path = os.path.join(self.aprendido_dir, 'preferencias.json')
        self.historial_path = os.path.join(self.aprendido_dir, 'historial.jsonl')

        self.inicializado = False
        self._inicializar()

    def _inicializar(self):
        """Crea las carpetas y archivos base si no existen."""
        try:
            for d in (self.aprendido_dir, self.codigos_dir,
                      self.prompts_dir, self.estructuras_dir):
                os.makedirs(d, exist_ok=True)

            if not os.path.exists(self.indice_path):
                self._guardar_json(self.indice_path, {
                    'version': self.VERSION,
                    'creado': datetime.now().isoformat(),
                    'actualizado': datetime.now().isoformat(),
                    'total_codigos': 0,
                    'total_prompts': 0,
                    'total_estructuras': 0,
                    'total_historial': 0,
                })

            if not os.path.exists(self.preferencias_path):
                self._guardar_json(self.preferencias_path, {
                    'lenguajes': {},
                    'estilos': {},
                    'temas': {},
                    'operadores': {},
                    'actualizado': datetime.now().isoformat(),
                })

            self.inicializado = True
        except Exception as e:
            print(f"⚠️ Error al inicializar el aprendiz: {e}")

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------
    def _hash(self, texto: str) -> str:
        """Genera un hash corto y estable a partir de un texto."""
        return hashlib.sha256(texto.encode('utf-8')).hexdigest()[:16]

    def _guardar_json(self, ruta: str, datos: Dict):
        """Guarda un dict como JSON con indentación."""
        try:
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error al guardar {ruta}: {e}")

    def _cargar_json(self, ruta: str) -> Dict:
        """Carga un JSON. Devuelve {} si falla."""
        if not os.path.exists(ruta):
            return {}
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error al cargar {ruta}: {e}")
            return {}

    def _append_jsonl(self, ruta: str, datos: Dict):
        """Añade una línea a un archivo JSONL."""
        try:
            with open(ruta, 'a', encoding='utf-8') as f:
                f.write(json.dumps(datos, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"⚠️ Error al escribir en {ruta}: {e}")

    def _rotar_jsonl(self, ruta: str, max_lineas: int):
        """Mantiene solo las últimas `max_lineas` líneas del JSONL."""
        if not os.path.exists(ruta):
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                lineas = f.readlines()
            if len(lineas) > max_lineas:
                with open(ruta, 'w', encoding='utf-8') as f:
                    f.writelines(lineas[-max_lineas:])
        except Exception as e:
            print(f"⚠️ Error al rotar {ruta}: {e}")

    def _actualizar_indice(self, campo: str, delta: int = 1):
        """Actualiza el índice general."""
        indice = self._cargar_json(self.indice_path)
        indice[campo] = indice.get(campo, 0) + delta
        indice['actualizado'] = datetime.now().isoformat()
        self._guardar_json(self.indice_path, indice)

    # ==================================================================
    # 1. APRENDER CÓDIGO
    # ==================================================================
    def aprender_codigo(
        self,
        codigo: str,
        lenguaje: str,
        nombre: str = "",
        origen: str = "usuario",   # "usuario" o "ia"
        prompt: str = "",
    ) -> Optional[str]:
        """
        Guarda un fragmento de código aprendido.
        Devuelve el hash del código guardado, o None si falló.
        """
        if not codigo or not codigo.strip():
            return None

        try:
            h = self._hash(codigo)
            ruta = os.path.join(self.codigos_dir, f"{h}.json")

            entrada = {
                'hash': h,
                'lenguaje': lenguaje or 'texto',
                'nombre': nombre or f"codigo_{h}",
                'origen': origen,
                'prompt_origen': prompt[:1000] if prompt else "",
                'longitud_chars': len(codigo),
                'longitud_lineas': codigo.count('\n') + 1,
                'aprendido': datetime.now().isoformat(),
                'codigo': codigo,
            }

            self._guardar_json(ruta, entrada)
            self._actualizar_indice('total_codigos')

            # Historial
            self._append_jsonl(self.historial_path, {
                'tipo': 'codigo',
                'hash': h,
                'lenguaje': lenguaje,
                'nombre': nombre,
                'origen': origen,
                'fecha': datetime.now().isoformat(),
            })
            self._rotar_jsonl(self.historial_path, self.MAX_HISTORIAL)

            return h
        except Exception as e:
            print(f"⚠️ Error al aprender código: {e}")
            return None

    # ==================================================================
    # 2. APRENDER PROMPT (cómo pide el usuario)
    # ==================================================================
    def aprender_prompt(
        self,
        prompt: str,
        lenguaje_detectado: str = "",
        intencion: str = "",
        operador: str = "Operador 1",
    ) -> Optional[str]:
        """
        Guarda un prompt del usuario para recordar cómo pide las cosas.
        Devuelve el hash del prompt o None.
        """
        if not prompt or not prompt.strip():
            return None

        try:
            h = self._hash(prompt)
            ruta = os.path.join(self.prompts_dir, f"{h}.json")

            # Extraer palabras clave
            palabras = self._extraer_palabras_clave(prompt)

            entrada = {
                'hash': h,
                'prompt': prompt,
                'lenguaje_detectado': lenguaje_detectado,
                'intencion': intencion,
                'operador': operador,
                'palabras_clave': palabras,
                'longitud': len(prompt),
                'aprendido': datetime.now().isoformat(),
            }

            self._guardar_json(ruta, entrada)
            self._actualizar_indice('total_prompts')

            # Actualizar preferencias
            self._actualizar_preferencias(
                lenguaje=lenguaje_detectado,
                intencion=intencion,
                operador=operador,
                palabras=palabras,
            )

            self._append_jsonl(self.historial_path, {
                'tipo': 'prompt',
                'hash': h,
                'lenguaje': lenguaje_detectado,
                'intencion': intencion,
                'operador': operador,
                'fecha': datetime.now().isoformat(),
            })
            self._rotar_jsonl(self.historial_path, self.MAX_HISTORIAL)

            return h
        except Exception as e:
            print(f"⚠️ Error al aprender prompt: {e}")
            return None

    def _extraer_palabras_clave(self, texto: str) -> List[str]:
        """Extrae las palabras más relevantes del prompt."""
        # Quitar signos y pasar a minúsculas
        limpio = re.sub(r'[^\wáéíóúñ\s]', ' ', texto.lower())
        palabras = limpio.split()

        # Filtrar stopwords en español
        stopwords = {
            'de', 'la', 'el', 'en', 'y', 'a', 'que', 'los', 'las', 'un', 'una',
            'por', 'con', 'para', 'sin', 'sobre', 'al', 'del', 'es', 'son',
            'como', 'me', 'te', 'se', 'mi', 'tu', 'su', 'lo', 'le', 'nos',
            'haz', 'hacer', 'crea', 'crear', 'genera', 'generar', 'dame',
            'quiero', 'necesito', 'puedes', 'por favor', 'favor',
        }
        filtradas = [p for p in palabras if len(p) > 3 and p not in stopwords]

        # Top 10 más repetidas
        from collections import Counter
        return [w for w, _ in Counter(filtradas).most_common(10)]

    def _actualizar_preferencias(
        self,
        lenguaje: str = "",
        intencion: str = "",
        operador: str = "",
        palabras: Optional[List[str]] = None,
    ):
        """Incrementa contadores de preferencias."""
        try:
            pref = self._cargar_json(self.preferencias_path)
            pref.setdefault('lenguajes', {})
            pref.setdefault('estilos', {})
            pref.setdefault('temas', {})
            pref.setdefault('operadores', {})

            if lenguaje:
                pref['lenguajes'][lenguaje] = pref['lenguajes'].get(lenguaje, 0) + 1

            if intencion:
                pref['estilos'][intencion] = pref['estilos'].get(intencion, 0) + 1

            if operador:
                pref['operadores'][operador] = pref['operadores'].get(operador, 0) + 1

            if palabras:
                for p in palabras:
                    pref['temas'][p] = pref['temas'].get(p, 0) + 1

            pref['actualizado'] = datetime.now().isoformat()
            self._guardar_json(self.preferencias_path, pref)
        except Exception as e:
            print(f"⚠️ Error al actualizar preferencias: {e}")

    # ==================================================================
    # 3. APRENDER ESTRUCTURA DE CÓDIGO
    # ==================================================================
    def aprender_estructura(
        self,
        codigo: str,
        lenguaje: str,
        nombre: str = "",
    ) -> Optional[str]:
        """
        Analiza el código y guarda su estructura: funciones, clases,
        imports, variables globales, etc.
        """
        if not codigo:
            return None

        try:
            estructura = self._extraer_estructura(codigo, lenguaje)

            # Solo guardar si hay algo útil
            if not any(estructura[k] for k in ('funciones', 'clases', 'imports')):
                return None

            h = self._hash(codigo)
            ruta = os.path.join(self.estructuras_dir, f"{h}.json")

            entrada = {
                'hash': h,
                'nombre': nombre or f"estructura_{h}",
                'lenguaje': lenguaje,
                'estructura': estructura,
                'aprendido': datetime.now().isoformat(),
            }

            self._guardar_json(ruta, entrada)
            self._actualizar_indice('total_estructuras')

            return h
        except Exception as e:
            print(f"⚠️ Error al aprender estructura: {e}")
            return None

    def _extraer_estructura(self, codigo: str, lenguaje: str) -> Dict[str, List[str]]:
        """Extrae funciones, clases, imports, etc. según el lenguaje."""
        estructura = {
            'funciones': [],
            'clases': [],
            'imports': [],
            'variables_globales': [],
        }

        try:
            if lenguaje in ('python', 'py'):
                estructura['funciones'] = re.findall(
                    r'^\s*(?:async\s+)?def\s+(\w+)', codigo, re.MULTILINE)
                estructura['clases'] = re.findall(
                    r'^\s*class\s+(\w+)', codigo, re.MULTILINE)
                estructura['imports'] = re.findall(
                    r'^\s*(?:from\s+[\w.]+\s+import\s+.+|import\s+.+)',
                    codigo, re.MULTILINE)

            elif lenguaje in ('javascript', 'js', 'typescript', 'ts'):
                estructura['funciones'] = re.findall(
                    r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))',
                    codigo)
                estructura['funciones'] = [f[0] or f[1] for f in estructura['funciones'] if f[0] or f[1]]
                estructura['clases'] = re.findall(
                    r'class\s+(\w+)', codigo)
                estructura['imports'] = re.findall(
                    r'^\s*import\s+.+', codigo, re.MULTILINE)

            elif lenguaje in ('cpp', 'c++', 'c'):
                estructura['funciones'] = re.findall(
                    r'^\s*(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{', codigo, re.MULTILINE)
                estructura['clases'] = re.findall(
                    r'^\s*(?:class|struct)\s+(\w+)', codigo, re.MULTILINE)
                estructura['imports'] = re.findall(
                    r'^\s*#include\s+.+', codigo, re.MULTILINE)

            elif lenguaje == 'java':
                estructura['funciones'] = re.findall(
                    r'(?:public|private|protected)\s+(?:static\s+)?\w+\s+(\w+)\s*\(', codigo)
                estructura['clases'] = re.findall(
                    r'(?:public\s+)?class\s+(\w+)', codigo)
                estructura['imports'] = re.findall(
                    r'^\s*import\s+.+', codigo, re.MULTILINE)

            else:
                # Genérico: buscar "def", "function", "class"
                estructura['funciones'] = re.findall(
                    r'(?:def|function)\s+(\w+)', codigo)
                estructura['clases'] = re.findall(r'class\s+(\w+)', codigo)

        except Exception as e:
            print(f"⚠️ Error extrayendo estructura: {e}")

        return estructura

    # ==================================================================
    # 4. APRENDER INTERACCIÓN COMPLETA (prompt + respuesta + código)
    # ==================================================================
    def aprender_interaccion(
        self,
        prompt: str,
        respuesta: str,
        lenguaje: str = "",
        operador: str = "Operador 1",
        codigos_extraidos: Optional[List[Dict]] = None,
    ):
        """
        Guarda una interacción completa: prompt del usuario, respuesta de la IA,
        y los códigos generados. Esto es lo que da "memoria" al sistema.
        """
        try:
            # 1. Aprender el prompt
            self.aprender_prompt(prompt, lenguaje, "consulta", operador)

            # 2. Aprender los códigos de la respuesta
            if codigos_extraidos:
                for cod in codigos_extraidos:
                    self.aprender_codigo(
                        codigo=cod.get('codigo', ''),
                        lenguaje=cod.get('lenguaje', lenguaje or 'texto'),
                        nombre=cod.get('nombre', ''),
                        origen='ia',
                        prompt=prompt,
                    )
                    self.aprender_estructura(
                        codigo=cod.get('codigo', ''),
                        lenguaje=cod.get('lenguaje', lenguaje or 'texto'),
                        nombre=cod.get('nombre', ''),
                    )

            # 3. Historial completo
            self._append_jsonl(self.historial_path, {
                'tipo': 'interaccion',
                'prompt': prompt[:500],
                'respuesta': respuesta[:500],
                'lenguaje': lenguaje,
                'operador': operador,
                'fecha': datetime.now().isoformat(),
            })
            self._rotar_jsonl(self.historial_path, self.MAX_HISTORIAL)
            self._actualizar_indice('total_historial')

        except Exception as e:
            print(f"⚠️ Error al aprender interacción: {e}")

    # ==================================================================
    # 5. RECUPERAR CONOCIMIENTO (para dar contexto a la IA)
    # ==================================================================
    def buscar_codigos_similares(self, prompt: str, limite: int = 3) -> List[Dict]:
        """
        Busca códigos aprendidos que sean similares al prompt actual.
        Usa coincidencia simple de palabras clave.
        """
        palabras_prompt = set(self._extraer_palabras_clave(prompt))
        if not palabras_prompt:
            return []

        resultados = []
        try:
            for archivo in os.listdir(self.codigos_dir):
                if not archivo.endswith('.json'):
                    continue
                ruta = os.path.join(self.codigos_dir, archivo)
                entrada = self._cargar_json(ruta)
                if not entrada:
                    continue

                # Comparar palabras clave del prompt de origen
                prompt_origen = entrada.get('prompt_origen', '')
                palabras_origen = set(self._extraer_palabras_clave(prompt_origen))

                # Puntuación = intersección de palabras
                puntuacion = len(palabras_prompt & palabras_origen)
                if puntuacion > 0:
                    resultados.append({
                        'puntuacion': puntuacion,
                        'nombre': entrada.get('nombre', ''),
                        'lenguaje': entrada.get('lenguaje', ''),
                        'codigo': entrada.get('codigo', ''),
                        'origen_prompt': prompt_origen,
                    })

            resultados.sort(key=lambda x: x['puntuacion'], reverse=True)
            return resultados[:limite]
        except Exception as e:
            print(f"⚠️ Error al buscar códigos similares: {e}")
            return []

    def obtener_preferencias(self) -> Dict:
        """Devuelve las preferencias actuales del usuario."""
        return self._cargar_json(self.preferencias_path)

    def obtener_indice(self) -> Dict:
        """Devuelve el índice general de lo aprendido."""
        return self._cargar_json(self.indice_path)

    def generar_contexto_aprendido(self, prompt: str) -> str:
        """
        Genera un bloque de texto con lo aprendido relevante para el prompt actual.
        Se puede inyectar en el prompt que se envía a la IA.
        """
        try:
            similares = self.buscar_codigos_similares(prompt, limite=2)
            pref = self.obtener_preferencias()

            if not similares and not pref.get('lenguajes'):
                return ""

            partes = ["\n=== CONOCIMIENTO PREVIO APRENDIDO ===\n"]

            # Lenguajes preferidos
            lenguajes = pref.get('lenguajes', {})
            if lenguajes:
                top_langs = sorted(lenguajes.items(), key=lambda x: -x[1])[:3]
                partes.append(
                    "Lenguajes más usados por el operador: "
                    + ", ".join(f"{l} ({n})" for l, n in top_langs)
                )

            # Códigos similares
            if similares:
                partes.append("\nFragmentos de código previos similares:")
                for s in similares:
                    partes.append(
                        f"\n--- {s['nombre']} ({s['lenguaje']}) ---\n"
                        f"{s['codigo'][:800]}"
                    )

            partes.append("\n=== FIN DEL CONOCIMIENTO PREVIO ===\n")
            return "\n".join(partes)
        except Exception as e:
            print(f"⚠️ Error al generar contexto: {e}")
            return ""

    # ==================================================================
    # 6. ESTADÍSTICAS
    # ==================================================================
    def estadisticas(self) -> Dict:
        """Devuelve un resumen completo del aprendizaje."""
        indice = self.obtener_indice()
        pref = self.obtener_preferencias()

        return {
            'version': self.VERSION,
            'carpeta': self.aprendido_dir,
            'total_codigos': indice.get('total_codigos', 0),
            'total_prompts': indice.get('total_prompts', 0),
            'total_estructuras': indice.get('total_estructuras', 0),
            'total_historial': indice.get('total_historial', 0),
            'lenguajes_top': sorted(
                pref.get('lenguajes', {}).items(),
                key=lambda x: -x[1]
            )[:5],
            'temas_top': sorted(
                pref.get('temas', {}).items(),
                key=lambda x: -x[1]
            )[:10],
            'operadores': pref.get('operadores', {}),
        }


# ==================================================================
# FUNCIONES DE CONVENIENCIA
# ==================================================================
_instancia_global: Optional[Aprendiz] = None


def obtener_aprendiz(modelo_dir: Optional[str] = None) -> Aprendiz:
    """Devuelve la instancia singleton del aprendiz."""
    global _instancia_global
    if _instancia_global is None:
        _instancia_global = Aprendiz(modelo_dir)
    return _instancia_global


def aprender(
    prompt: str,
    respuesta: str,
    lenguaje: str = "",
    operador: str = "Operador 1",
    codigos_extraidos: Optional[List[Dict]] = None,
    modelo_dir: Optional[str] = None,
):
    """Atajo: aprende una interacción completa."""
    return obtener_aprendiz(modelo_dir).aprender_interaccion(
        prompt, respuesta, lenguaje, operador, codigos_extraidos
    )


def contexto_aprendido(prompt: str, modelo_dir: Optional[str] = None) -> str:
    """Atajo: obtiene el contexto aprendido relevante."""
    return obtener_aprendiz(modelo_dir).generar_contexto_aprendido(prompt)


def estadisticas(modelo_dir: Optional[str] = None) -> Dict:
    """Atajo: obtiene las estadísticas."""
    return obtener_aprendiz(modelo_dir).estadisticas()


# ==================================================================
# EJEMPLO DE USO
# ==================================================================
if __name__ == '__main__':
    print("=" * 70)
    print("🧠 SISTEMA DE APRENDIZAJE - MyndTeks")
    print("=" * 70)

    aprendiz = Aprendiz()

    # Ejemplo 1: aprender un código
    codigo_ejemplo = '''
def saludar(nombre):
    """Saluda a una persona."""
    return f"Hola, {nombre}!"

class Persona:
    def __init__(self, nombre):
        self.nombre = nombre

    def presentarse(self):
        return self.saludar()

import os
import sys
'''
    h = aprendiz.aprender_codigo(
        codigo=codigo_ejemplo,
        lenguaje='python',
        nombre='ejemplo_saludo.py',
        origen='usuario',
        prompt='crea una función para saludar y una clase Persona'
    )
    print(f"✅ Código aprendido: {h}")

    # Ejemplo 2: aprender la estructura
    h2 = aprendiz.aprender_estructura(
        codigo=codigo_ejemplo,
        lenguaje='python',
        nombre='ejemplo_saludo.py'
    )
    print(f"✅ Estructura aprendida: {h2}")

    # Ejemplo 3: aprender un prompt
    h3 = aprendiz.aprender_prompt(
        prompt='crea una función para saludar y una clase Persona',
        lenguaje_detectado='python',
        intencion='crear_codigo',
        operador='Operador 1'
    )
    print(f"✅ Prompt aprendido: {h3}")

    # Ejemplo 4: buscar códigos similares
    similares = aprendiz.buscar_codigos_similares('hazme una función de saludo')
    print(f"\n🔍 Códigos similares encontrados: {len(similares)}")
    for s in similares:
        print(f"   → {s['nombre']} ({s['lenguaje']}) · puntuación {s['puntuacion']}")

    # Ejemplo 5: contexto aprendido
    contexto = aprendiz.generar_contexto_aprendido('hazme una función de saludo')
    if contexto:
        print("\n📚 Contexto aprendido:")
        print(contexto[:500])

    # Estadísticas
    print("\n" + "=" * 70)
    print("📊 ESTADÍSTICAS")
    print("=" * 70)
    stats = aprendiz.estadisticas()
    for k, v in stats.items():
        print(f"  {k:>22}: {v}")