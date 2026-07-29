---
name: OpenWrt Router Diagnostic App (IDAF)
description: Panel operativo de diagnóstico SSH para routers OpenWrt de laboratorio — primer módulo de una tesis de observabilidad IoT.
colors:
  primary: "#94b43b"
  primary-deep: "#6f872c"
  surface-tint: "#f2f6e9"
  canvas: "#ffffff"
  ink: "#1b1b1b"
  state-healthy: "#2ecc71"
  state-warning: "#f1c40f"
  state-degraded: "#e67e22"
  state-critical: "#e74c3c"
  state-unknown: "#95a5a6"
typography:
  body:
    fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  heading:
    fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif"
    fontWeight: 600
  label:
    fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif"
    fontWeight: 600
    fontSize: "0.85rem"
rounded:
  sm: "8px"
  md: "12px"
spacing:
  sm: "8px"
  md: "16px"
components:
  metric-card:
    backgroundColor: "{colors.surface-tint}"
    rounded: "{rounded.md}"
    padding: "16px"
  state-badge:
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "2px 10px"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
---

# Design System: OpenWrt Router Diagnostic App (IDAF)

## Overview

**Creative North Star: "The Lab Notebook"**

Una herramienta interna, técnica, sin ambición de marketing: la interfaz de un cuaderno de laboratorio bien llevado — legible al primer vistazo, sin decoración que no cargue información, y con el estado del router siempre visible sin ambigüedad. El verde institucional de la Universidad Nacional de Colombia (`#94b43b`) marca identidad de forma discreta (nunca más del acento puntual: título, botón primario, hover del menú lateral); el resto de la superficie se mantiene neutro para que los datos —estados, tablas, código crudo de SSH— sean lo único que compite por atención.

Se rechaza explícitamente cualquier borde de color grueso decorativo (>1px) en tarjetas o alertas, y cualquier texto de estado que dependa solo del color sin contraste verificado: cada color de estado (HEALTHY/WARNING/DEGRADED/CRITICAL/UNREACHABLE/UNKNOWN) se empareja con texto oscuro (`#1b1b1b`) que cumple ≥4.5:1 en todos los casos, nunca blanco.

**Key Characteristics:**
- Superficie plana, casi sin sombra; el color de estado es la única señal decorativa que se permite ser vívida.
- Un solo acento de marca (verde UNAL), usado con moderación (título, botones primarios, hover de navegación).
- Un solo sistema tipográfico y un solo set de iconos (Material Symbols) en toda la app.
- El color nunca es el único portador de significado: todo estado lleva también su etiqueta de texto (`HEALTHY`, `WARNING`, etc.).

## Colors

Paleta acotada: un acento de marca, cinco colores de estado (impuestos por el dominio del diagnóstico, no elegidos por gusto visual) y una escala neutra de superficie.

### Primary
- **Verde UNAL** (`#94b43b`): título de página (`h1`), botones primarios, hover de navegación lateral. Úsalo con moderación — es el acento, no el color de fondo dominante.
- **Verde UNAL profundo** (`#6f872c`): estado `:hover` del botón primario y texto del `h1` sobre fondo blanco (7.3:1 de contraste).

### Neutral
- **Blanco** (`#ffffff`): fondo de página (`backgroundColor` del tema).
- **Verde pálido** (`#f2f6e9`): fondo de tarjetas de métricas, hover del menú lateral, expanders — distingue "superficie elevada" del lienzo blanco sin usar sombra.
- **Tinta** (`#1b1b1b`): texto de cuerpo y texto sobre cualquier color de estado (nunca blanco sobre estado: ver Named Rule abajo).

### Colores de estado (impuestos por el dominio, no por elección estética)
- **Healthy** (`#2ecc71`)
- **Warning** (`#f1c40f`)
- **Degraded** (`#e67e22`)
- **Critical / Unreachable** (`#e74c3c`)
- **Unknown** (`#95a5a6`)

Definidos en un único lugar (`core/branding.py`) e importados por `topology/renderer.py` — antes existían dos copias del mismo diccionario de colores; ahora hay una sola fuente de verdad.

### Named Rules
**The Dark-Text-On-State Rule.** Todo texto sobre un color de estado usa `#1b1b1b`, nunca blanco. Blanco sobre estos cinco colores cae entre 1.66:1 y 3.82:1 (falla WCAG AA); texto oscuro sube el rango a 4.51–10.37:1 en los cinco casos.

**The One Accent Rule.** El verde de marca aparece en como máximo 2–3 elementos por pantalla (título, botón primario, hover de navegación). Los colores de estado —no la marca— son el segundo lenguaje de color permitido, y solo para transmitir salud del router.

**Light-only, conocido y aceptado.** `.streamlit/config.toml` fija un tema claro; los componentes custom (`topology/renderer.py`) asumen fondos claros (`white`, `#fafafa`) sin variante para tema oscuro. Si el usuario cambia manualmente a tema oscuro desde el menú de Streamlit, estos fondos no reaccionan — limitación conocida, no implementada, no un tema para resolver de forma incidental en un ajuste visual menor.

## Typography

**Body/Heading Font:** IBM Plex Sans (con fallback a system-ui/Segoe UI/Arial)

**Character:** Técnica y precisa sin caer en el cliché de Inter/Arial de cualquier producto genérico de IA; IBM Plex tiene origen en un sistema de diseño de ingeniería (IBM), coherente con una herramienta de diagnóstico de infraestructura.

### Hierarchy
- **Heading** (600, tamaño por defecto de `st.title`/`st.subheader`): título de página y secciones. Sin regla decorativa debajo — el color (`#6f872c`) y el peso ya le dan jerarquía, no necesita una barra adicional.
- **Body** (400, 1rem, line-height 1.5): texto de párrafo, descripciones de comando, mensajes de estado.
- **Label** (600, 0.85rem): etiquetas de métricas (`stMetricLabel`) y pastillas de estado.
- **Code:** fuente monoespaciada por defecto de Streamlit para `st.code`/`st.json` — no se toca; es uso legítimo de monospace (datos/código), no decorativo.

## Layout

Streamlit multipage con `layout="wide"`; el framework colapsa columnas a una sola cuando el viewport se angosta (comportamiento nativo, sin CSS propio que lo bloquee). Ritmo de página consistente: título → texto introductorio → `st.divider()` → secciones agrupadas en columnas de métricas o pestañas (`st.tabs`). Cada página termina con la sección de resultados/detalle y, cuando aplica, un botón de limpieza destructivo protegido por checkbox de confirmación.

## Elevation & Depth

**The Flat-By-Default Rule.** Sin sombras salvo la topología interactiva (`topology/renderer.py`), donde una sombra sutil con offset (`0 4px 14px rgba(0,0,0,0.18)`) distingue los nodos flotantes del lienzo del diagrama; en el resto de la app la profundidad se transmite con el tinte de superficie (`#f2f6e9`) y un borde de 1px, no con sombra.

## Shapes

Escala de radios de dos pasos: `sm` (8px) para controles interactivos pequeños (botones, enlaces de navegación, pastillas de estado) y `md` (12px) para contenedores (tarjetas de métrica, expanders, nodos de topología). Antes había 4 valores distintos (8/10/12/16px) sin relación entre sí; ahora hay una escala de 2 pasos reutilizada en toda la app.

## Components

### Buttons
- **Shape:** radio `sm` (8px).
- **Primary:** fondo `#94b43b`, texto oscuro.
- **Hover:** fondo `#6f872c`.
- **Secondary/destructivo:** botón por defecto de Streamlit (sin color propio); las acciones destructivas (eliminar dispositivo/historial) siempre están deshabilitadas hasta marcar un checkbox de confirmación explícito — el guardrail es funcional, no cromático.

### Cards (tarjetas de métrica `st.metric`)
- **Corner Style:** radio `md` (12px).
- **Background:** `#f2f6e9`.
- **Border:** 1px sólido, tono neutro derivado de la marca (sin el borde de acento grueso que tenía antes).
- **Shadow Strategy:** ninguna — ver Elevation & Depth.

### State badges / pills (`state_badge()`, pastillas de nodo en topología)
- **Style:** fondo = color de estado, texto = `#1b1b1b`, radio `sm` (8px), padding `2px 10px`.
- **Regla:** el color nunca es el único portador de significado — el texto del estado (`HEALTHY`, `WARNING`, ...) siempre acompaña al color.

### Navigation (sidebar)
- Logo institucional centrado arriba; enlaces con radio `sm` y hover en `#f2f6e9`.

## Do's and Don'ts

### Do:
- **Do** usar `#1b1b1b` como texto sobre cualquier color de estado (Dark-Text-On-State Rule).
- **Do** mantener una sola fuente de verdad para los colores de estado (`core/branding.py`), importada donde se necesite.
- **Do** reservar el verde de marca para acentos puntuales (One Accent Rule).
- **Do** acompañar todo color de estado con su etiqueta de texto.

### Don't:
- **Don't** usar texto blanco sobre colores de estado (falla contraste en los 5 casos verificados).
- **Don't** agregar bordes de color >1px como acento decorativo en tarjetas o alertas.
- **Don't** duplicar el diccionario de colores de estado en más de un módulo.
- **Don't** tocar la lógica de negocio, las llamadas SSH, los contratos de datos o las rutas al hacer ajustes visuales — ver `CLAUDE.md`.
