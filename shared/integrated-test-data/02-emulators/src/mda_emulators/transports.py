from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, TextIO


class EventTransport(Protocol):
    def publish(self, topic: str, event: dict[str, Any]) -> None: ...

    def close(self) -> None: ...


class JsonLinesTransport:
    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout

    def publish(self, topic: str, event: dict[str, Any]) -> None:
        record = _build_record(topic, event)
        self.stream.write(json.dumps(record, sort_keys=True) + "\n")

    def close(self) -> None:
        self.stream.flush()


class FileTransport(JsonLinesTransport):
    def __init__(self, path: str | Path) -> None:
        self._handle = Path(path).open("w", encoding="utf-8")
        super().__init__(self._handle)

    def close(self) -> None:
        super().close()
        self._handle.close()


class KafkaTransport:
    """Kafka producer using Microsoft Entra OAuth; never uses connection strings."""

    def __init__(
        self,
        bootstrap_servers: str,
        *,
        client_id: str | None = None,
    ) -> None:
        try:
            from azure.identity import DefaultAzureCredential
            from confluent_kafka import Producer
        except ImportError as exc:
            raise RuntimeError(
                "Kafka mode requires the 'kafka' optional dependencies"
            ) from exc

        self._credential = DefaultAzureCredential(managed_identity_client_id=client_id)
        token_scope = event_hubs_token_scope(bootstrap_servers)
        self._publish_errors: list[str] = []
        self._last_statistics: str | None = None

        def oauth_callback(_: str) -> tuple[str, float]:
            token = self._credential.get_token(token_scope)
            return token.token, float(token.expires_on)

        def error_callback(error: Any) -> None:
            self._publish_errors.append(str(error))

        def statistics_callback(statistics: str) -> None:
            self._last_statistics = statistics

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "security.protocol": "SASL_SSL",
                "sasl.mechanism": "OAUTHBEARER",
                "oauth_cb": oauth_callback,
                "enable.idempotence": True,
                "acks": "all",
                "retries": 12,
                "retry.backoff.ms": 250,
                "socket.keepalive.enable": True,
                "statistics.interval.ms": 60000,
                "error_cb": error_callback,
                "stats_cb": statistics_callback,
                "client.id": "mda-demo-emulators",
            }
        )

    def publish(self, topic: str, event: dict[str, Any]) -> None:
        record = _build_record(topic, event)
        self._producer.produce(
            topic=topic,
            key=record["key"].encode("utf-8"),
            value=json.dumps(record, separators=(",", ":")).encode("utf-8"),
        )
        self._producer.poll(0)

    def close(self) -> None:
        outstanding = self._producer.flush(30)
        if outstanding:
            raise RuntimeError(f"{outstanding} Kafka event(s) were not delivered")
        if self._publish_errors:
            diagnostics = self._last_statistics or "no Kafka statistics captured"
            raise RuntimeError(
                "Kafka transport reported errors: "
                + "; ".join(self._publish_errors)
                + f" | diagnostics: {diagnostics}"
            )


def _stamp_publish_time(event: dict[str, Any]) -> dict[str, Any]:
    published_event = dict(event)
    published_event["published_time_utc"] = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    return published_event


def _build_record(topic: str, event: dict[str, Any]) -> dict[str, Any]:
    published_event = _stamp_publish_time(event)
    return {
        "topic": topic,
        "key": published_event["ordering_key"],
        "event": published_event,
    }


def event_hubs_token_scope(bootstrap_servers: str) -> str:
    first_server = bootstrap_servers.split(",", maxsplit=1)[0].strip()
    namespace_fqdn = first_server.split(":", maxsplit=1)[0]
    if not namespace_fqdn.endswith(".servicebus.windows.net"):
        raise ValueError("Kafka bootstrap server must be an Event Hubs namespace")
    return f"https://{namespace_fqdn}/.default"
