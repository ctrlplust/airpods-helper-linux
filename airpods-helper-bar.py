#!/usr/bin/env python3
"""Waybar module for airpods-helper (reads org.costa.AirPods over D-Bus).

Usage:
  airpods-helper-bar.py            # plain text
  airpods-helper-bar.py --json     # waybar custom module (return-type: json)
"""
import sys

import gi

gi.require_version("Gio", "2.0")

from gi.repository import Gio, GLib

SVC = "org.costa.AirPods"
PATH = "/org/costa/AirPods"
IFACE = "org.costa.AirPods"


def get_state():
    try:
        pp = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            SVC,
            PATH,
            "org.freedesktop.DBus.Properties",
            None,
        )
        res = pp.call_sync(
            "GetAll",
            GLib.Variant("(s)", (IFACE,)),
            Gio.DBusCallFlags.NONE,
            2000,
            None,
        )
        body = res.unpack()
        data = body[0] if isinstance(body, (tuple, list)) else body
        out = {}
        for k, v in data.items():
            if isinstance(v, GLib.Variant) and v.get_type_string() == "v":
                v = v.get_child_value(0)
                out[k] = v.unpack()
            elif hasattr(v, "unpack"):
                out[k] = v.unpack()
            else:
                out[k] = v
        return out
    except Exception:
        return None


def fmt(v):
    return "--" if v is None or v < 0 else f"{v}"


def main():
    use_json = "--json" in sys.argv
    s = get_state()
    if not s or not s.get("Connected", False):
        if use_json:
            print('{"text": "", "class": "disconnected"}')
        return 0

    L = s.get("BatteryLeft", -1)
    R = s.get("BatteryRight", -1)
    C = s.get("BatteryCase", -1)

    if use_json:
        vals = [x for x in (L, R) if x is not None and x >= 0]
        pct = min(vals) if vals else -1
        cls = "high"
        if 0 <= pct < 30:
            cls = "critical"
        elif 0 <= pct < 60:
            cls = "low"
        anc = {
            "noise": "Cancelación",
            "transparency": "Transparencia",
            "adaptive": "Adaptativo",
            "off": "Off",
        }.get(s.get("AncMode", "off"), s.get("AncMode", "off"))
        model = s.get("ModelName", "AirPods")
        tooltip = (
            f"{model}\n"
            f"Izquierdo {fmt(L)}%   Derecho {fmt(R)}%   Estuche {fmt(C)}%\n"
            f"ANC: {anc}"
        )
        print(
            '{"text": "  L%s%%  R%s%%  C%s%%", "class": "%s", '
            '"tooltip": "%s"}' % (fmt(L), fmt(R), fmt(C), cls, tooltip)
        )
    else:
        print(f"L {fmt(L)}% R {fmt(R)}% C {fmt(C)}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())