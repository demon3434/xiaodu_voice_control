from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from aiohttp import web

from homeassistant.components import frontend
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_INTERNAL_API_TOKEN,
    CONF_SERVICE_URL,
    DATA_CONFIG_STORE,
    DATA_DEVICE_STORE,
    DATA_ENTRY_DATA,
    DATA_MANAGER,
    DATA_YAML_DATA,
    DEFAULT_SERVICE_URL,
    DEVICES_YAML_FILENAME,
    DOMAIN,
    PANEL_URL_PATH,
    SERVICE_SYNC_DEVICES,
    STATIC_URL_PATH,
)
from .manager import XiaoduVoiceControlManager
from .storage import XiaoduConfigStore, XiaoduDeviceStore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SERVICE_URL, default=DEFAULT_SERVICE_URL): cv.string,
                vol.Optional(CONF_INTERNAL_API_TOKEN): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def _get_service_url(hass: HomeAssistant) -> str:
    entry_data = hass.data.get(DOMAIN, {}).get(DATA_ENTRY_DATA)
    if entry_data and entry_data.get(CONF_SERVICE_URL):
        return str(entry_data[CONF_SERVICE_URL])
    yaml_data = hass.data.get(DOMAIN, {}).get(DATA_YAML_DATA)
    if yaml_data and yaml_data.get(CONF_SERVICE_URL):
        return str(yaml_data[CONF_SERVICE_URL])
    return DEFAULT_SERVICE_URL


def _get_manager(hass: HomeAssistant) -> XiaoduVoiceControlManager:
    return hass.data[DOMAIN][DATA_MANAGER]


def _require_admin(request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not getattr(user, "is_admin", False):
        return web.json_response({"error": "admin privileges required"}, status=403)
    return None


class XiaoduVoiceControlProxyView(HomeAssistantView):
    requires_auth = False

    def __init__(self, hass: HomeAssistant, url: str, name: str, upstream_path: str) -> None:
        self._hass = hass
        self.url = url
        self.name = name
        self._upstream_path = upstream_path

    async def _proxy(self, request) -> web.Response:
        return await _get_manager(self._hass).proxy_request(request, self._upstream_path)

    async def get(self, request):
        return await self._proxy(request)

    async def post(self, request):
        return await self._proxy(request)


class XiaoduVoiceControlDevicesView(HomeAssistantView):
    url = "/api/xiaodu_voice_control/devices"
    name = "api:xiaodu_voice_control:devices"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        devices = await _get_manager(self._hass).async_get_devices()
        return self.json({"devices": devices})

    async def post(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        payload = await request.json()
        try:
            device = await _get_manager(self._hass).async_add_device(payload)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return self.json({"device": device})

    async def put(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        payload = await request.json()
        appliance_id = str(payload.get("appliance_id", "")).strip()
        if not appliance_id:
            return web.json_response({"error": "appliance_id is required"}, status=400)
        try:
            device = await _get_manager(self._hass).async_update_device(appliance_id, payload)
        except KeyError:
            return web.json_response({"error": "device not found"}, status=404)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return self.json({"device": device})

    async def delete(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        payload = await request.json()
        appliance_id = str(payload.get("appliance_id", "")).strip()
        if not appliance_id:
            return web.json_response({"error": "appliance_id is required"}, status=400)
        await _get_manager(self._hass).async_delete_device(appliance_id)
        return self.json({"status": "ok"})


class XiaoduVoiceControlSyncView(HomeAssistantView):
    url = "/api/xiaodu_voice_control/sync"
    name = "api:xiaodu_voice_control:sync"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def post(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        try:
            result = await _get_manager(self._hass).async_sync_devices()
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=502)
        return self.json(result)


class XiaoduVoiceControlConfigView(HomeAssistantView):
    url = "/api/xiaodu_voice_control/config"
    name = "api:xiaodu_voice_control:config"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        return self.json(await _get_manager(self._hass).async_get_runtime_config())

    async def post(self, request):
        denied = _require_admin(request)
        if denied is not None:
            return denied
        payload = await request.json()
        try:
            result = await _get_manager(self._hass).async_save_runtime_config(payload)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return self.json(result)


async def _register_static_and_panel(hass: HomeAssistant) -> None:
    local = Path(__file__).resolve().parent / "panel"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL_PATH, str(local), False)]
    )
    panels = hass.data.setdefault(DATA_PANELS, {})
    if PANEL_URL_PATH not in panels:
        frontend.async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="小度语音设备",
            sidebar_icon="mdi:account-voice",
            frontend_url_path=PANEL_URL_PATH,
            config={"url": f"{STATIC_URL_PATH}/index.html?v=20260325a"},
            require_admin=True,
        )


def _register_views(hass: HomeAssistant) -> None:
    hass.http.register_view(
        XiaoduVoiceControlProxyView(
            hass,
            "/xiaoduvc/auth/authorize",
            "xiaodu_voice_control:authorize",
            "/xiaoduvc/auth/authorize",
        )
    )
    hass.http.register_view(
        XiaoduVoiceControlProxyView(
            hass,
            "/xiaoduvc/auth/token",
            "xiaodu_voice_control:token",
            "/xiaoduvc/auth/token",
        )
    )
    hass.http.register_view(
        XiaoduVoiceControlProxyView(
            hass,
            "/xiaoduvc/service",
            "xiaodu_voice_control:service",
            "/xiaoduvc/service",
        )
    )
    hass.http.register_view(
        XiaoduVoiceControlProxyView(
            hass,
            "/xiaoduvc/health",
            "xiaodu_voice_control:health",
            "/health",
        )
    )
    hass.http.register_view(XiaoduVoiceControlDevicesView(hass))
    hass.http.register_view(XiaoduVoiceControlSyncView(hass))
    hass.http.register_view(XiaoduVoiceControlConfigView(hass))


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_YAML_DATA] = config.get(DOMAIN, {})
    hass.data[DOMAIN][DATA_DEVICE_STORE] = XiaoduDeviceStore(hass)
    hass.data[DOMAIN][DATA_CONFIG_STORE] = XiaoduConfigStore(hass)
    hass.data[DOMAIN][DATA_MANAGER] = XiaoduVoiceControlManager(hass)

    async def _handle_sync(call: ServiceCall) -> None:
        await _get_manager(hass).async_sync_devices()

    if not hass.services.has_service(DOMAIN, SERVICE_SYNC_DEVICES):
        hass.services.async_register(DOMAIN, SERVICE_SYNC_DEVICES, _handle_sync)

    _register_views(hass)
    await _register_static_and_panel(hass)
    manager = _get_manager(hass)
    if _get_service_url(hass) and manager.internal_api_token:
        async def _push_startup_context() -> None:
            try:
                await manager.async_push_runtime_context(sync_cloud=False)
            except Exception as exc:
                _LOGGER.warning("[%s] startup runtime sync skipped: %s", DOMAIN, exc)

        hass.async_create_task(_push_startup_context())
    _LOGGER.info("[%s] integration loaded with service_url=%s", DOMAIN, _get_service_url(hass))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_ENTRY_DATA] = dict(entry.data)
    manager = _get_manager(hass)
    await manager.async_ensure_seed_data()
    try:
        await manager.async_push_runtime_context(sync_cloud=False)
    except Exception as exc:
        _LOGGER.warning("[%s] initial runtime sync skipped: %s", DOMAIN, exc)
    _LOGGER.info("[%s] config entry loaded: %s", DOMAIN, entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.get(DOMAIN, {}).pop(DATA_ENTRY_DATA, None)
    _LOGGER.info("[%s] config entry unloaded: %s", DOMAIN, entry.entry_id)
    return True
