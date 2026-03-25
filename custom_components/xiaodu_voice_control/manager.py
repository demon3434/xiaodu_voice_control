from __future__ import annotations

import json
from typing import Any

from aiohttp import web

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_INTERNAL_API_TOKEN,
    CONF_SERVICE_URL,
    CONF_XIAODU_CLIENT_SECRET,
    CONF_XIAODU_OPEN_UIDS,
    CONF_XIAODU_SKILL_ID,
    DATA_CONFIG_STORE,
    DATA_DEVICE_STORE,
    DATA_ENTRY_DATA,
    DATA_YAML_DATA,
    DEVICES_YAML_FILENAME,
    DOMAIN,
)


class XiaoduVoiceControlManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    @property
    def _entry_data(self) -> dict[str, Any]:
        return self._hass.data.get(DOMAIN, {}).get(DATA_ENTRY_DATA, {})

    @property
    def service_url(self) -> str:
        if self._entry_data.get(CONF_SERVICE_URL):
            return str(self._entry_data.get(CONF_SERVICE_URL, "")).rstrip("/")
        yaml_data = self._hass.data.get(DOMAIN, {}).get(DATA_YAML_DATA, {})
        return str(yaml_data.get(CONF_SERVICE_URL, "")).rstrip("/")

    @property
    def internal_api_token(self) -> str:
        if self._entry_data.get(CONF_INTERNAL_API_TOKEN):
            return str(self._entry_data.get(CONF_INTERNAL_API_TOKEN, ""))
        yaml_data = self._hass.data.get(DOMAIN, {}).get(DATA_YAML_DATA, {})
        return str(yaml_data.get(CONF_INTERNAL_API_TOKEN, ""))

    async def async_get_yaml_config(self) -> dict[str, Any]:
        return await self._hass.data[DOMAIN][DATA_CONFIG_STORE].async_load()

    async def async_save_yaml_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        store = self._hass.data[DOMAIN][DATA_CONFIG_STORE]
        current = await store.async_load()
        current.update(updates)
        saved = await store.async_save(current)
        self._hass.data[DOMAIN][DATA_YAML_DATA] = saved
        return saved

    async def async_ensure_seed_data(self) -> None:
        store = self._hass.data[DOMAIN][DATA_DEVICE_STORE]
        devices = await store.async_load()
        await store.async_save(devices)
        yaml_config = await self.async_get_yaml_config()
        if yaml_config:
            self._hass.data[DOMAIN][DATA_YAML_DATA] = yaml_config

    async def async_get_devices(self) -> list[dict]:
        return await self._hass.data[DOMAIN][DATA_DEVICE_STORE].async_load()

    async def async_add_device(self, device: dict) -> dict:
        devices = await self.async_get_devices()
        appliance_id = str(device.get("appliance_id", "")).strip()
        if not appliance_id:
            raise ValueError("appliance_id is required")
        if any(item["appliance_id"] == appliance_id for item in devices):
            raise ValueError(f"duplicate appliance_id: {appliance_id}")
        normalized = self._normalize_device(device)
        devices.append(normalized)
        await self._hass.data[DOMAIN][DATA_DEVICE_STORE].async_save(devices)
        return normalized

    async def async_update_device(self, appliance_id: str, device: dict) -> dict:
        devices = await self.async_get_devices()
        normalized = self._normalize_device(device)
        updated = False
        for index, item in enumerate(devices):
            if item["appliance_id"] == appliance_id:
                devices[index] = normalized
                updated = True
                break
        if not updated:
            raise KeyError(appliance_id)
        await self._hass.data[DOMAIN][DATA_DEVICE_STORE].async_save(devices)
        return normalized

    async def async_delete_device(self, appliance_id: str) -> None:
        devices = await self.async_get_devices()
        filtered = [item for item in devices if item["appliance_id"] != appliance_id]
        await self._hass.data[DOMAIN][DATA_DEVICE_STORE].async_save(filtered)

    async def async_get_service_settings(self) -> dict[str, Any]:
        session = async_get_clientsession(self._hass, verify_ssl=False)
        headers = {"X-Internal-Token": self.internal_api_token}
        try:
            async with session.get(
                f"{self.service_url}/internal/settings",
                headers=headers,
            ) as response:
                if response.status >= 400:
                    return {}
                return await response.json()
        except Exception:
            return {}

    async def async_get_runtime_config(self) -> dict[str, Any]:
        yaml_config = await self.async_get_yaml_config()
        service_settings = await self.async_get_service_settings()
        service_open_uids = list(service_settings.get("open_uids") or [])
        yaml_open_uids = list(yaml_config.get(CONF_XIAODU_OPEN_UIDS) or [])
        merged_open_uids = list(dict.fromkeys(yaml_open_uids + service_open_uids))
        if merged_open_uids != yaml_open_uids:
            yaml_config = await self.async_save_yaml_config({CONF_XIAODU_OPEN_UIDS: merged_open_uids})
        return {
            "service_url": self.service_url,
            "devices_yaml": DEVICES_YAML_FILENAME,
            "xiaodu_skill_id": yaml_config.get(CONF_XIAODU_SKILL_ID, ""),
            "xiaodu_client_secret": yaml_config.get(CONF_XIAODU_CLIENT_SECRET, ""),
            "internal_api_token": yaml_config.get(CONF_INTERNAL_API_TOKEN, ""),
            "open_uids": merged_open_uids,
            "panel_title": "小度语音设备",
        }

    async def async_save_runtime_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        yaml_config = await self.async_get_yaml_config()
        skill_id = str(payload.get(CONF_XIAODU_SKILL_ID, "")).strip()
        client_secret = str(payload.get(CONF_XIAODU_CLIENT_SECRET, yaml_config.get(CONF_XIAODU_CLIENT_SECRET, ""))).strip()
        service_url = str(payload.get(CONF_SERVICE_URL, yaml_config.get(CONF_SERVICE_URL, self.service_url))).strip()
        new_internal_token = str(payload.get(CONF_INTERNAL_API_TOKEN, yaml_config.get(CONF_INTERNAL_API_TOKEN, self.internal_api_token))).strip()
        open_uids = [
            str(item).strip()
            for item in (payload.get(CONF_XIAODU_OPEN_UIDS, yaml_config.get(CONF_XIAODU_OPEN_UIDS, [])) or [])
            if str(item).strip()
        ]
        await self.async_push_runtime_settings(
            auth_token=self.internal_api_token,
            payload_override={
                "xiaodu_skill_id": skill_id,
                "xiaodu_client_secret": client_secret,
                "internal_api_token": new_internal_token,
                "open_uids": open_uids,
            },
        )
        saved = await self.async_save_yaml_config(
            {
                CONF_XIAODU_SKILL_ID: skill_id,
                CONF_XIAODU_CLIENT_SECRET: client_secret,
                CONF_INTERNAL_API_TOKEN: new_internal_token,
                CONF_SERVICE_URL: service_url,
                CONF_XIAODU_OPEN_UIDS: open_uids,
            }
        )
        return {
            "service_url": saved.get(CONF_SERVICE_URL, self.service_url),
            "xiaodu_skill_id": saved.get(CONF_XIAODU_SKILL_ID, ""),
            "xiaodu_client_secret": saved.get(CONF_XIAODU_CLIENT_SECRET, ""),
            "internal_api_token": saved.get(CONF_INTERNAL_API_TOKEN, ""),
            "open_uids": saved.get(CONF_XIAODU_OPEN_UIDS, []),
        }

    async def async_push_runtime_settings(
        self,
        *,
        auth_token: str | None = None,
        payload_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        yaml_config = await self.async_get_yaml_config()
        session = async_get_clientsession(self._hass, verify_ssl=False)
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": auth_token or self.internal_api_token,
        }
        payload = {
            "xiaodu_skill_id": str(yaml_config.get(CONF_XIAODU_SKILL_ID, "")).strip(),
            "xiaodu_client_secret": str(yaml_config.get(CONF_XIAODU_CLIENT_SECRET, "")).strip(),
            "internal_api_token": str(yaml_config.get(CONF_INTERNAL_API_TOKEN, self.internal_api_token)).strip(),
            "open_uids": list(yaml_config.get(CONF_XIAODU_OPEN_UIDS) or []),
        }
        if payload_override:
            payload.update(payload_override)
        async with session.put(
            f"{self.service_url}/internal/settings",
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"settings sync failed: {response.status} {text}")
            data = await response.json()
        service_open_uids = list(data.get("open_uids") or [])
        if service_open_uids != list(yaml_config.get(CONF_XIAODU_OPEN_UIDS) or []):
            await self.async_save_yaml_config({CONF_XIAODU_OPEN_UIDS: service_open_uids})
        return data

    async def async_push_runtime_context(self, sync_cloud: bool) -> dict:
        devices = await self.async_get_devices()
        settings_result = await self.async_push_runtime_settings()
        session = async_get_clientsession(self._hass, verify_ssl=False)
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": self.internal_api_token,
        }
        payload = {"devices": devices}
        async with session.put(
            f"{self.service_url}/internal/devices",
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"sync failed: {response.status} {text}")
            data = await response.json()
            result = {
                "status": "ok",
                "count": data.get("count", len(devices)),
                "settings": settings_result,
            }
        if sync_cloud:
            async with session.post(
                f"{self.service_url}/internal/device-sync",
                headers=headers,
            ) as response:
                text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(f"device sync failed: {response.status} {text}")
                sync_data = await response.json()
                result["device_sync"] = sync_data
            latest = await self.async_get_service_settings()
            latest_open_uids = list(latest.get("open_uids") or [])
            current_yaml = await self.async_get_yaml_config()
            if latest_open_uids != list(current_yaml.get(CONF_XIAODU_OPEN_UIDS) or []):
                await self.async_save_yaml_config({CONF_XIAODU_OPEN_UIDS: latest_open_uids})
        return result

    async def async_sync_devices(self) -> dict:
        return await self.async_push_runtime_context(sync_cloud=True)

    async def proxy_request(self, request, upstream_path: str) -> web.Response:
        target_url = self.service_url + upstream_path
        if request.query_string:
            target_url = target_url + "?" + request.query_string

        headers = {}
        content_type = request.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type

        session = async_get_clientsession(self._hass, verify_ssl=False)
        body = await request.read()
        async with session.request(
            request.method,
            target_url,
            data=body if body else None,
            headers=headers or None,
        ) as response:
            payload = await response.read()
            proxy_response = web.Response(body=payload, status=response.status)
            response_content_type = response.headers.get("Content-Type")
            if response_content_type:
                proxy_response.headers["Content-Type"] = response_content_type
            return proxy_response

    @staticmethod
    def _normalize_device(device: dict) -> dict:
        normalized = {
            "appliance_id": str(device.get("appliance_id", "")).strip(),
            "name": str(device.get("name", "")).strip(),
            "type": str(device.get("type", "")).strip(),
            "entity_id": str(device.get("entity_id", "")).strip(),
            "actions": [str(item).strip() for item in device.get("actions", []) if str(item).strip()],
            "properties": [str(item).strip() for item in device.get("properties", []) if str(item).strip()],
        }
        required = ("appliance_id", "name", "type", "entity_id")
        missing = [key for key in required if not normalized[key]]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        return normalized
