from __future__ import annotations


class RouterAppError(Exception):
    """Base exception for all application errors.

    Carries a generic, user-safe `friendly_message` (class-level, shown in
    the UI) and an optional `detail` with a short technical summary (shown
    only as a collapsed/secondary hint). Never put credentials or a full
    traceback in either.
    """

    friendly_message: str = "Ocurrió un error inesperado."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(detail or self.friendly_message)


class SSHConnectionError(RouterAppError):
    friendly_message = "No fue posible contactar el router. Verifica la IP, el puerto y la conectividad de red."


class SSHAuthenticationError(RouterAppError):
    friendly_message = "La autenticación SSH fue rechazada. Verifica el usuario y la contraseña."


class SSHTimeoutError(RouterAppError):
    friendly_message = "Se agotó el tiempo de espera al comunicarse con el router."


class CommandNotAllowedError(RouterAppError):
    friendly_message = "El comando no está autorizado."


class CommandConfigurationError(RouterAppError):
    friendly_message = "La configuración de comandos (config/commands.yaml) no es válida."


class DiagnosticConfigurationError(RouterAppError):
    friendly_message = "La configuración de umbrales de diagnóstico (config/diagnostic_thresholds.yaml) no es válida."


class CommandExecutionError(RouterAppError):
    friendly_message = "Ocurrió un error al ejecutar el comando en el router."


class ParserError(RouterAppError):
    friendly_message = "No fue posible interpretar la salida del comando."
