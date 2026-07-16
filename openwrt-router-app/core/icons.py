from __future__ import annotations

# Central, single-family icon set (Streamlit's built-in Material Symbols
# shortcode syntax): every icon in the app comes from here so they render
# in one consistent monochrome style instead of mismatched colorful emoji.
ICONS: dict[str, str] = {
    # Navigation / sections
    "home": ":material/router:",
    "connection": ":material/cable:",
    "commands": ":material/terminal:",
    "history": ":material/history:",
    "diagnostics": ":material/monitor_heart:",
    "topology": ":material/hub:",
    "about": ":material/info:",
    # General concepts
    "devices": ":material/computer:",
    "registry": ":material/dns:",
    "success": ":material/check_circle:",
    "error": ":material/cancel:",
    "warning": ":material/warning:",
    "critical": ":material/error:",
    "healthy": ":material/verified:",
    "list": ":material/list_alt:",
    "event": ":material/notifications:",
    "calendar": ":material/calendar_month:",
    "clock": ":material/schedule:",
    "code": ":material/code:",
    "link": ":material/link:",
    "search": ":material/search:",
    "download": ":material/download:",
    "delete": ":material/delete:",
    "clear_all": ":material/delete_sweep:",
    "add": ":material/add:",
    "edit": ":material/edit:",
    "settings": ":material/settings:",
    "connect": ":material/power:",
    "bolt": ":material/bolt:",
    "flag": ":material/flag:",
    "play": ":material/play_arrow:",
    "result": ":material/description:",
    # Diagnostic checks
    "check_ssh": ":material/lock:",
    "check_identity": ":material/badge:",
    "check_uptime": ":material/schedule:",
    "check_memory": ":material/memory:",
    "check_storage": ":material/storage:",
    "check_lan": ":material/lan:",
    "check_wan": ":material/public:",
    "check_ipv6": ":material/satellite_alt:",
    "check_wifi": ":material/wifi:",
}


def icon(name: str) -> str:
    """Returns the `:material/xxx:` shortcode for the given icon name."""
    return ICONS[name]
