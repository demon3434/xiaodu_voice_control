from __future__ import annotations

from pathlib import Path

import yaml

from homeassistant.core import HomeAssistant

from .const import (
    CONFIG_YAML_FILENAME,
    CONF_INTERNAL_API_TOKEN,
    CONF_XIAODU_CLIENT_SECRET,
    CONF_SERVICE_URL,
    CONF_XIAODU_OPEN_UIDS,
    CONF_XIAODU_SKILL_ID,
    DEVICES_YAML_FILENAME,
)


class XiaoduDeviceStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._path = Path(hass.config.path(DEVICES_YAML_FILENAME))
        self._default_path = Path(__file__).resolve().parent / "defaults" / "devices.yaml"

    async def async_load(self) -> list[dict]:
        return await self._hass.async_add_executor_job(self._load_sync)

    async def async_save(self, devices: list[dict]) -> None:
        await self._hass.async_add_executor_job(self._save_sync, devices)

    def _load_sync(self) -> list[dict]:
        if not self._path.exists():
            devices = self._load_yaml(self._default_path)
            self._save_sync(devices)
            return devices
        return self._load_yaml(self._path)

    def _save_sync(self, devices: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"devices": devices}
        self._path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _load_yaml(path: Path) -> list[dict]:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return list(raw.get("devices", []))


class XiaoduConfigStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._path = Path(hass.config.path(CONFIG_YAML_FILENAME))

    async def async_load(self) -> dict:
        return await self._hass.async_add_executor_job(self._load_sync)

    async def async_save(self, config: dict) -> dict:
        return await self._hass.async_add_executor_job(self._save_sync, config)

    def _load_sync(self) -> dict:
        if not self._path.exists():
            return {}
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return self._normalize(raw)

    def _save_sync(self, config: dict) -> dict:
        normalized = self._normalize(config)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return normalized

    @staticmethod
    def _normalize(config: dict) -> dict:
        normalized = dict(config or {})
        if normalized.get(CONF_SERVICE_URL) is not None:
            normalized[CONF_SERVICE_URL] = str(normalized.get(CONF_SERVICE_URL, "")).strip()
        if normalized.get(CONF_INTERNAL_API_TOKEN) is not None:
            normalized[CONF_INTERNAL_API_TOKEN] = str(normalized.get(CONF_INTERNAL_API_TOKEN, "")).strip()
        normalized[CONF_XIAODU_CLIENT_SECRET] = str(normalized.get(CONF_XIAODU_CLIENT_SECRET, "")).strip()
        normalized[CONF_XIAODU_SKILL_ID] = str(normalized.get(CONF_XIAODU_SKILL_ID, "")).strip()
        open_uids = normalized.get(CONF_XIAODU_OPEN_UIDS) or []
        if isinstance(open_uids, str):
            open_uids = [item.strip() for item in open_uids.split(",") if item.strip()]
        normalized[CONF_XIAODU_OPEN_UIDS] = [
            str(item).strip() for item in open_uids if str(item).strip()
        ]
        return normalized
