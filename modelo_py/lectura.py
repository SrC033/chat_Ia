# lectura.py
"""
lectura.py - Divisor y lector rápido de archivos grandes

Divide cualquier archivo de texto/código en trozos (chunks) manejables
y los entrega a la IA de forma secuencial para que procese archivos
de miles de líneas a alta velocidad.

Uso:
    from lectura import LectorFragmentado

    lector = LectorFragmentado(ruta_archivo)
    for trozo in lector.iterar_trozos():
        print(trozo)
"""

import os
import time
from typing import Generator, Dict, List, Optional


class LectorFragmentado:
    """
    Divide un archivo en fragmentos por líneas, preservando bloques
    lógicos (funciones, clases) cuando es posible, y los entrega
    secuencialmente a alta velocidad.
    """

    # Configuración por defecto
    LINEAS_POR_TROZO = 500          # líneas por fragmento (óptimo para streaming)
    MAX_TROZOS = 20                 # límite de fragmentos a procesar
    MAX_LINEAS_TOTAL = 5000         # límite total de líneas a leer
    DELAY_ENTRE_TROZOS = 0.0        # sin delay = máxima velocidad
    INCLUIR_CONTEXTO = True         # incluir últimas 20 líneas del trozo anterior

    # Marcadores típicos de "inicio de bloque lógico" para cortar limpio
    MARCADORES_INICIO = (
        'def ', 'class ', 'async def ', 'function ', 'const ', 'let ', 'var ',
        'public ', 'private ', 'protected ', 'void ', 'int ', 'float ', 'struct ',
        'interface ', 'enum ', 'export ', 'import ', '<template', '<script',
        '/*', '/*', '<!--', 'section ', 'module ', 'namespace ', 'package ',
    )

    def __init__(
        self,
        ruta: str,
        lineas_por_trozo: Optional[int] = None,
        max_lineas_total: Optional[int] = None,
        max_trozos: Optional[int] = None,
        delay_entre_trozos: Optional[float] = None,
        incluir_contexto: Optional[bool] = None,
    ):
        self.ruta = ruta
        self.lineas_por_trozo = lineas_por_trozo or self.LINEAS_POR_TROZO
        self.max_lineas_total = max_lineas_total or self.MAX_LINEAS_TOTAL
        self.max_trozos = max_trozos or self.MAX_TROZOS
        self.delay_entre_trozos = (
            self.DELAY_ENTRE_TROZOS if delay_entre_trozos is None else delay_entre_trozos
        )
        self.incluir_contexto = (
            self.INCLUIR_CONTEXTO if incluir_contexto is None else incluir_contexto
        )

        # Métricas
        self.total_lineas = 0
        self.total_trozos = 0
        self.tiempo_total = 0.0
        self._lineas_cache: Optional[List[str]] = None

    # ------------------------------------------------------------------
    # CARGA DEL ARCHIVO
    # ------------------------------------------------------------------
    def _cargar_lineas(self) -> List[str]:
        """Carga el archivo en memoria una sola vez."""
        if self._lineas_cache is not None:
            return self._lineas_cache

        if not os.path.exists(self.ruta):
            raise FileNotFoundError(f"No existe el archivo: {self.ruta}")

        # Tamaño máximo: 5 MB
        size = os.path.getsize(self.ruta)
        if size > 5 * 1024 * 1024:
            raise ValueError(
                f"El archivo pesa {size / 1024 / 1024:.2f} MB. "
                f"Máximo permitido: 5 MB."
            )

        try:
            with open(self.ruta, 'r', encoding='utf-8', errors='replace') as f:
                lineas = f.readlines()
        except UnicodeDecodeError:
            # Fallback para archivos con codificación no UTF-8
            with open(self.ruta, 'r', encoding='latin-1', errors='replace') as f:
                lineas = f.readlines()

        # Truncar a MAX_LINEAS_TOTAL
        if len(lineas) > self.max_lineas_total:
            lineas = lineas[:self.max_lineas_total]

        self.total_lineas = len(lineas)
        self._lineas_cache = lineas
        return lineas

    # ------------------------------------------------------------------
    # FRAGMENTACIÓN
    # ------------------------------------------------------------------
    def _encontrar_corte_limpio(self, lineas: List[str], inicio: int, fin_ideal: int) -> int:
        """
        Busca un punto de corte "limpio" cerca de `fin_ideal` mirando hacia atrás
        hasta 50 líneas. Un corte limpio es antes de una línea que empieza con
        alguno de los MARCADORES_INICIO (función, clase, etc.).
        """
        minimo = max(inicio + 1, fin_ideal - 50)
        for i in range(fin_ideal, minimo, -1):
            if i >= len(lineas):
                continue
            linea = lineas[i].lstrip()
            if any(linea.startswith(m) for m in self.MARCADORES_INICIO):
                return i
        return min(fin_ideal, len(lineas))

    def dividir_en_trozos(self) -> List[Dict]:
        """
        Divide el archivo en trozos y devuelve lista de dicts:
        {
            'indice': int,
            'inicio': int,       # línea de inicio (1-based)
            'fin': int,          # línea final (1-based)
            'total_lineas': int,
            'contenido': str,
            'contexto_previo': str,  # últimas líneas del trozo anterior
        }
        """
        lineas = self._cargar_lineas()
        trozos = []
        inicio = 0
        indice = 0
        contexto_previo = ""

        while inicio < len(lineas) and indice < self.max_trozos:
            fin_ideal = inicio + self.lineas_por_trozo

            if fin_ideal >= len(lineas):
                fin = len(lineas)
            else:
                fin = self._encontrar_corte_limpio(lineas, inicio, fin_ideal)

            fragmento = lineas[inicio:fin]
            contenido = ''.join(fragmento).rstrip('\n')

            if not contenido.strip():
                inicio = fin
                continue

            trozos.append({
                'indice': indice + 1,
                'inicio': inicio + 1,
                'fin': fin,
                'total_lineas': fin - inicio,
                'contenido': contenido,
                'contexto_previo': contexto_previo,
            })

            # Guardar las últimas N líneas como contexto del siguiente trozo
            if self.incluir_contexto:
                contexto_previo = ''.join(fragmento[-20:]).rstrip('\n')

            inicio = fin
            indice += 1

        self.total_trozos = len(trozos)
        return trozos

    # ------------------------------------------------------------------
    # ITERACIÓN RÁPIDA (GENERADOR)
    # ------------------------------------------------------------------
    def iterar_trozos(self) -> Generator[Dict, None, None]:
        """
        Genera los trozos uno por uno a alta velocidad.
        Ideal para enviar a la IA en streaming.
        """
        inicio_tiempo = time.time()
        trozos = self.dividir_en_trozos()

        for trozo in trozos:
            yield trozo
            if self.delay_entre_trozos > 0:
                time.sleep(self.delay_entre_trozos)

        self.tiempo_total = time.time() - inicio_tiempo

    # ------------------------------------------------------------------
    # FORMATO PARA LA IA
    # ------------------------------------------------------------------
    def trozo_a_prompt(self, trozo: Dict, nombre_archivo: str = None) -> str:
        """
        Convierte un trozo en texto formateado para enviar a la IA.
        Incluye cabecera con número de fragmento y rango de líneas.
        """
        nombre = nombre_archivo or os.path.basename(self.ruta)
        lenguaje = os.path.splitext(nombre)[1].lstrip('.') or 'texto'

        partes = []
        partes.append(
            f"=== FRAGMENTO {trozo['indice']}/{self.total_trozos} · "
            f"{nombre} · líneas {trozo['inicio']}-{trozo['fin']} ==="
        )

        if trozo.get('contexto_previo'):
            partes.append(
                f"\n[CONTEXTO PREVIO DEL FRAGMENTO ANTERIOR]\n"
                f"{trozo['contexto_previo']}\n"
                f"[FIN DEL CONTEXTO]\n"
            )

        partes.append(f"```{lenguaje}\n{trozo['contenido']}\n```")

        return "\n".join(partes)

    def iterar_prompts(self, nombre_archivo: str = None) -> Generator[str, None, None]:
        """
        Genera los trozos ya formateados como prompts listos para la IA.
        """
        for trozo in self.iterar_trozos():
            yield self.trozo_a_prompt(trozo, nombre_archivo)

    # ------------------------------------------------------------------
    # ESTADÍSTICAS
    # ------------------------------------------------------------------
    def estadisticas(self) -> Dict:
        """Devuelve métricas del procesamiento."""
        return {
            'archivo': self.ruta,
            'total_lineas': self.total_lineas,
            'total_trozos': self.total_trozos,
            'lineas_por_trozo': self.lineas_por_trozo,
            'tiempo_total_seg': round(self.tiempo_total, 4),
            'lineas_por_segundo': round(
                self.total_lineas / self.tiempo_total, 2
            ) if self.tiempo_total > 0 else 0,
            'tamano_bytes': os.path.getsize(self.ruta) if os.path.exists(self.ruta) else 0,
        }


# ==================================================================
# FUNCIONES DE CONVENIENCIA
# ==================================================================
def dividir_archivo(ruta: str, lineas_por_trozo: int = 500) -> List[Dict]:
    """
    Atajo: divide un archivo y devuelve la lista de trozos.
    """
    lector = LectorFragmentado(ruta, lineas_por_trozo=lineas_por_trozo)
    return lector.dividir_en_trozos()


def leer_archivo_rapido(ruta: str) -> str:
    """
    Lee un archivo completo como string, sin fragmentar.
    Útil para archivos pequeños (< 1000 líneas).
    """
    lector = LectorFragmentado(ruta, max_lineas_total=10**9)
    lineas = lector._cargar_lineas()
    return ''.join(lineas)


def leer_con_progreso(ruta: str, callback=None) -> List[Dict]:
    """
    Lee un archivo y llama a `callback(trozo, indice, total)` en cada fragmento.
    Devuelve la lista completa de trozos.
    """
    lector = LectorFragmentado(ruta)
    trozos = lector.dividir_en_trozos()

    if callback:
        for i, trozo in enumerate(trozos):
            callback(trozo, i, len(trozos))

    return trozos


# ==================================================================
# EJEMPLO DE USO
# ==================================================================
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Uso: python lectura.py <ruta_archivo>")
        sys.exit(1)

    ruta = sys.argv[1]
    print(f"📂 Leyendo: {ruta}\n")

    lector = LectorFragmentado(ruta, lineas_por_trozo=500)

    for trozo in lector.iterar_trozos():
        print(
            f"▶ Fragmento {trozo['indice']:>2}  "
            f"│ líneas {trozo['inicio']:>5}-{trozo['fin']:<5} "
            f"│ {trozo['total_lineas']:>4} líneas "
            f"│ {len(trozo['contenido']):>7} caracteres"
        )

    print("\n" + "=" * 70)
    print("📊 ESTADÍSTICAS")
    print("=" * 70)
    stats = lector.estadisticas()
    for k, v in stats.items():
        print(f"  {k:>22}: {v}")