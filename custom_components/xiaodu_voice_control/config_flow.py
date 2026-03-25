from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_INTERNAL_API_TOKEN, CONF_SERVICE_URL, DEFAULT_SERVICE_URL, DOMAIN


class XiaoDuVoiceControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            user_input[CONF_INTERNAL_API_TOKEN] = secrets.token_urlsafe(32)
            return self.async_create_entry(
                title="XiaoDu Voice Control",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_SERVICE_URL, default=DEFAULT_SERVICE_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
