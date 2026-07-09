from __future__ import annotations

from diagnostics.enums import DiagnosticState
from diagnostics.models import DiagnosticCheckResult


def consolidate(
    checks: list[DiagnosticCheckResult],
    required_check_ids: set[str],
) -> tuple[DiagnosticState, str]:
    """Consolida el estado general siguiendo el orden de reglas de la sección 9 del MVP.

    No es un promedio ni un health score: sigue una jerarquía de reglas donde
    un chequeo obligatorio en estado crítico/degradado domina, cualquier
    warning (obligatorio u opcional) sube el resultado a WARNING, y solo si
    todos los chequeos obligatorios están HEALTHY el resultado es HEALTHY.
    """
    ssh_check = next((c for c in checks if c.check_id == "ssh"), None)
    if ssh_check is not None and ssh_check.state == DiagnosticState.UNREACHABLE:
        return DiagnosticState.UNREACHABLE, "El router no es alcanzable por SSH."

    required_checks = [c for c in checks if c.check_id in required_check_ids]

    if any(c.state == DiagnosticState.CRITICAL for c in required_checks):
        return DiagnosticState.CRITICAL, _summary_for(DiagnosticState.CRITICAL, checks)
    if any(c.state == DiagnosticState.DEGRADED for c in required_checks):
        return DiagnosticState.DEGRADED, _summary_for(DiagnosticState.DEGRADED, checks)
    if any(c.state == DiagnosticState.WARNING for c in checks):
        return DiagnosticState.WARNING, _summary_for(DiagnosticState.WARNING, checks)
    if any(c.state == DiagnosticState.UNKNOWN for c in required_checks):
        return DiagnosticState.UNKNOWN, _summary_for(DiagnosticState.UNKNOWN, checks)

    return (
        DiagnosticState.HEALTHY,
        "El router está accesible y sus recursos principales se encuentran dentro de condiciones normales.",
    )


def _summary_for(state: DiagnosticState, checks: list[DiagnosticCheckResult]) -> str:
    matching_names = [c.check_name for c in checks if c.state == state]
    if state == DiagnosticState.CRITICAL:
        return f"El router presenta condiciones críticas en: {', '.join(matching_names)}."
    if state == DiagnosticState.DEGRADED:
        return f"El router está degradado en: {', '.join(matching_names)}."
    if state == DiagnosticState.WARNING:
        return f"El router está operativo, pero requiere atención en: {', '.join(matching_names)}."
    if state == DiagnosticState.UNKNOWN:
        return f"No fue posible evaluar completamente: {', '.join(matching_names)}."
    return "El router está accesible y sus recursos principales se encuentran dentro de condiciones normales."
