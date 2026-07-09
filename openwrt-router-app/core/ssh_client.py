from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass

import paramiko

from core.exceptions import (
    CommandExecutionError,
    SSHAuthenticationError,
    SSHConnectionError,
    SSHTimeoutError,
)
from models.connection import ConnectionConfig, HostKeyPolicy

logger = logging.getLogger(__name__)


@dataclass
class CommandOutput:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


class SSHClient:
    """Thin context-manager wrapper around paramiko.SSHClient.

    `AutoAddPolicy` (host_key_policy="auto") silently trusts unknown host
    keys and is only meant for a controlled lab network during the MVP.
    Use host_key_policy="reject" for anything beyond that.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config
        self._client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        client = paramiko.SSHClient()
        if self._config.host_key_policy == HostKeyPolicy.REJECT:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logger.info(
            "Conectando por SSH host=%s puerto=%s usuario=%s",
            self._config.host,
            self._config.port,
            self._config.username,
        )
        try:
            client.connect(
                hostname=self._config.host,
                port=self._config.port,
                username=self._config.username,
                password=self._config.password.get_secret_value(),
                timeout=self._config.timeout,
                auth_timeout=self._config.timeout,
                banner_timeout=self._config.timeout,
                look_for_keys=False,
                allow_agent=False,
            )
        except paramiko.AuthenticationException as exc:
            raise SSHAuthenticationError(str(exc)) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise SSHTimeoutError("Tiempo de espera agotado al conectar por SSH.") from exc
        except (paramiko.SSHException, OSError) as exc:
            raise SSHConnectionError(str(exc)) from exc

        self._client = client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def execute(self, command: str, timeout: int) -> CommandOutput:
        if self._client is None:
            raise SSHConnectionError("No hay una conexión SSH activa.")

        started = time.monotonic()
        try:
            _stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")
        except socket.timeout as exc:
            raise SSHTimeoutError(f"El comando superó el tiempo máximo de {timeout}s.") from exc
        except paramiko.SSHException as exc:
            raise CommandExecutionError(str(exc)) from exc
        duration = time.monotonic() - started

        return CommandOutput(
            stdout=stdout_text,
            stderr=stderr_text,
            exit_code=exit_code,
            duration_seconds=duration,
        )
