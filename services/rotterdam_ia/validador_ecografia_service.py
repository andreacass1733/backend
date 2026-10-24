"""
Servicio de Validación de Calidad de Imagen Médica y Detección Fuera de Dominio (OOD Filter).
Módulo de Seguridad Clínica para el Criterio 3 de Rotterdam.

Evita que imágenes ajenas a la ecografía ovárica (como fotos a color de perros, personas,
radiografías de tórax, ecografías obstétricas fetales o tiroides) sean procesadas
indebidamente por la red EfficientNet-B0 o reciban recuentos foliculares artificiales.
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Any
from services.rotterdam_ia.criterio3_service import evaluar_y_recortar_ecografia


def validar_ecografia_ovarica(img_bgr: np.ndarray) -> Tuple[bool, str, str, Dict[str, Any]]:
    """
    Evalúa la imagen mediante un pipeline jerárquico de 4 niveles antes de permitir
    la inferencia con EfficientNet-B0 y el análisis de folículos:

    Retorna:
      (es_valida: bool, codigo_error: str, mensaje_clinico: str, metadatos: dict)
    """
    if img_bgr is None:
        return (
            False,
            "ARCHIVO_CORRUPTO",
            "No se pudo decodificar el archivo como una imagen médica válida o el formato está dañado.",
            {}
        )

    h, w = img_bgr.shape[:2]
    if h < 80 or w < 80:
        return (
            False,
            "RESOLUCION_INSUFICIENTE",
            "La resolución de la imagen es insuficiente para una evaluación diagnóstica confiable.",
            {"alto": h, "ancho": w}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # NIVEL 1: FILTRO CROMÁTICO (Anti-fotos cotidianas: animales, selfies, ropa)
    # ══════════════════════════════════════════════════════════════════════════
    # Las ecografías Modo-B médicas son monocromáticas (escala de grises casi pura).
    # Las fotos convencionales presentan alta saturación y divergencia BGR.
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    sat_media = float(np.mean(sat))
    
    b = img_bgr[:, :, 0].astype(float)
    g = img_bgr[:, :, 1].astype(float)
    r = img_bgr[:, :, 2].astype(float)
    diff_cromatica = float(np.mean(np.abs(r - g) + np.abs(g - b) + np.abs(r - b)))

    if sat_media > 24.0 or diff_cromatica > 20.0:
        return (
            False,
            "FOTO_COLOR_DETECTADA",
            (
                f"Imagen no válida: Se detectaron colores naturales ajenos a un ultrasonido médico "
                f"(saturación cromática: {sat_media:.1f}). El clasificador solo procesa ecografías ginecológicas "
                f"en escala de grises (Modo-B)."
            ),
            {"saturacion_media": round(sat_media, 2), "divergencia_cromatica": round(diff_cromatica, 2)}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # NIVEL 2: RECORTAR SECTOR ACÚSTICO Y EVALUAR DISPERSIÓN (SPECKLE NOISE)
    # ══════════════════════════════════════════════════════════════════════════
    img_roi = evaluar_y_recortar_ecografia(img_bgr)
    if img_roi is None:
        img_roi = img_bgr

    rh, rw = img_roi.shape[:2]
    gris_roi = cv2.cvtColor(img_roi, cv2.COLOR_BGR2GRAY)

    # El ultrasonido en tejidos biológicos produce una textura de moteado acústico
    # (Speckle Noise por dispersión Rayleigh). Si la varianza laplaciana es mínima,
    # es un gráfico digital plano, texto o dibujo.
    lap = float(cv2.Laplacian(gris_roi, cv2.CV_64F).var())
    if lap < 12.0:
        return (
            False,
            "SIN_TEXTURA_ECOGRAFICA",
            (
                "La imagen carece del patrón de moteado acústico (speckle noise) característico de un ultrasonido biológico. "
                "Verifique que no sea un gráfico digital o captura sin contenido ecográfico."
            ),
            {"varianza_laplaciana": round(lap, 2)}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # NIVEL 3: FILTRO DE MODALIDAD RADIOGRÁFICA (Anti-Radiografías de Tórax/Huesos)
    # ══════════════════════════════════════════════════════════════════════════
    # Las radiografías de tórax tienen grandes bandas radiopacas continuas de estructuras
    # óseas (costillas, clavículas, columna) que saturan el blanco (> 240) en más del 28-30%
    # del campo visual, sin presentar la caída acústica de tejido blando.
    pct_blanco_puro = float(np.mean(gris_roi > 240))
    if pct_blanco_puro > 0.28:
        return (
            False,
            "MODALIDAD_RADIOGRAFICA",
            (
                "Densidad radiopaca excesiva: La imagen presenta características de una radiografía ósea o de tórax "
                "(rayos X), no de una ecografía ginecológica de tejido blando."
            ),
            {"porcentaje_blanco_puro": round(pct_blanco_puro * 100, 2)}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # NIVEL 4: FILTRO ANATÓMICO (Anti-Feto Obstétrico / Grandes Cavidades Amnióticas)
    # ══════════════════════════════════════════════════════════════════════════
    # En una ecografía obstétrica fetal (2do/3er trimestre), el líquido amniótico o
    # la cavidad gestacional forman lagunas anecoicas masivas (> 55% del área útil),
    # mientras que los folículos de SOP son múltiples cavidades pequeñas de 2 a 9 mm.
    _, mask_anecoica = cv2.threshold(gris_roi, 25, 255, cv2.THRESH_BINARY_INV)
    contornos_anecoicos, _ = cv2.findContours(mask_anecoica, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_roi = float(rh * rw)
    
    for c in contornos_anecoicos:
        area_c = cv2.contourArea(c)
        ratio_c = area_c / area_roi
        # Cavidad anecoica masiva indiscutible (> 55% del campo util)
        if ratio_c > 0.55:
            return (
                False,
                "PATRON_OBSTETRICO_FETAL",
                (
                    "Estructura no compatible con ovario: Se detectó una cavidad anecoica desproporcionada "
                    f"({ratio_c * 100:.1f}% del área útil) compatible con líquido amniótico gestacional "
                    "(ecografía obstétrica de feto) u otra región anatómica ajena a los ovarios."
                ),
                {"area_cavidad_relativa": round(ratio_c * 100, 2)}
            )
        # Cavidad anecoica extensa (> 33% del área útil) corroborada con ausencia de arquitectura folicular ovárica
        if ratio_c > 0.33:
            try:
                from services.rotterdam_ia.criterio3_service import _detectar_envoltorios_foliculares
                env = _detectar_envoltorios_foliculares(gris_roi, prob_sop=0.8)
                if len(env) == 0:
                    return (
                        False,
                        "PATRON_OBSTETRICO_FETAL",
                        (
                            "Estructura no compatible con ovario: Se detectó una cavidad anecoica extensa "
                            f"({ratio_c * 100:.1f}% del área) sin arquitectura folicular ovárica detectable, "
                            "característica de líquido amniótico gestacional (ecografía obstétrica de embarazo)."
                        ),
                        {"area_cavidad_relativa": round(ratio_c * 100, 2), "foliculos_detectados": 0}
                    )
            except Exception:
                pass

    return (
        True,
        "ECOGRAFIA_OVARICA_VALIDA",
        "Imagen compatible con ecografía ovárica ginecológica Modo-B.",
        {
            "saturacion_media": round(sat_media, 2),
            "speckle_laplaciano": round(lap, 2),
            "pct_blanco": round(pct_blanco_puro * 100, 2)
        }
    )
