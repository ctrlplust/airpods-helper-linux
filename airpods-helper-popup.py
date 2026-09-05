#!/usr/bin/env python3
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gdk, Gio, GLib, Gtk

APP_ID = "org.costa.AirPodsPopup"
SVC = "org.costa.AirPods"
PATH = "/org/costa/AirPods"
IFACE = "org.costa.AirPods"

CSS = """
window { background: transparent; }
.card {
  background: rgba(249, 249, 251, 0.97);
  border-radius: 26px;
  box-shadow: 0 14px 44px rgba(0, 0, 0, 0.38);
  padding: 20px 24px 18px 24px;
}
.title { font-weight: 800; font-size: 17px; color: #1c1c1e; }
.status { font-size: 12px; color: #8e8e93; }
.big { font-weight: 800; font-size: 26px; color: #1c1c1e; }
.caption { font-size: 11px; color: #8e8e93; }
.bar trough { min-height: 7px; border-radius: 4px; background-color: #e5e5ea; }
.bar progress { min-height: 7px; border-radius: 4px; background-color: #30d158; }
.bar.low progress { background-color: #ff9f0a; }
.bar.critical progress { background-color: #ff3b30; }
.charging { font-size: 11px; color: #30d158; font-weight: 700; }
.chargecloud { font-size: 11px; color: #8e8e93; font-weight: 700; }
"""


def unpack_value(value):
    if value is None:
        return None
    if not isinstance(value, GLib.Variant):
        return value
    t = value.get_type_string()
    if t == "v":
        return value.get_child_value(0).unpack()
    return value.unpack()


class Popup:
    def __init__(self):
        self.state = {}
        self.hide_timer = None
        self.last_snap = None
        self.app = Gtk.Application(
            application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.app.connect("activate", self.on_activate)
        self.win = None
        self.revealer = None
        self.lbl_title = None
        self.lbl_sub = None
        self.cols = None

    # ---------------------------------------------------------------- dbus
    def dbus_connect(self):
        try:
            self.proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                SVC,
                PATH,
                IFACE,
                None,
            )
            self.proxy.connect("g-properties-changed", self.on_props_changed)
            self.proxy.connect("g-signal", self.on_signal)
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
            for k, v in data.items():
                self.state[k] = unpack_value(v)
        except Exception as e:
            print(f"[airpods-popup] dbus error: {e}", file=sys.stderr)

    def on_props_changed(self, proxy, changed, invalidated):
        try:
            was_connected = bool(self.state.get("Connected"))
            for k in changed.keys():
                self.state[k] = unpack_value(changed.lookup_value(k, None))
            connected = bool(self.state.get("Connected"))
            if self.win and self.revealer.get_reveal_child():
                self.refresh_card()
                new_snap = self.snapshot()
                if new_snap != self.last_snap:
                    self.reset_hide_timer()
                    self.last_snap = new_snap
            elif connected and not was_connected:
                self.show_pop()
        except Exception as e:
            print(f"[airpods-popup] props error: {e}", file=sys.stderr)

    def on_signal(self, proxy, sender, signal, params):
        try:
            if signal == "DeviceConnected":
                self.state["Connected"] = True
                self.refresh_card()
                self.show_pop()
            elif signal == "DeviceDisconnected":
                self.state["Connected"] = False
                self.hide_pop()
        except Exception as e:
            print(f"[airpods-popup] signal error: {e}", file=sys.stderr)

    # ------------------------------------------------------------------ ui
    def build_window(self, app):
        win = Gtk.Window(application=app)
        win.set_title("AirPods")
        win.set_decorated(False)
        win.set_resizable(False)
        win.set_default_size(360, 40)

        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        card.add_css_class("card")

        self.lbl_title = Gtk.Label(label="AirPods")
        self.lbl_title.add_css_class("title")
        card.append(self.lbl_title)

        self.lbl_sub = Gtk.Label(label="")
        self.lbl_sub.add_css_class("status")
        card.append(self.lbl_sub)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30)
        row.set_halign(Gtk.Align.CENTER)
        self.cols = {}
        for key, caption in (("L", "Izquierdo"), ("R", "Derecho"), ("C", "Estuche")):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            col.set_halign(Gtk.Align.CENTER)
            big = Gtk.Label(label="--")
            big.add_css_class("big")
            col.append(big)
            bar = Gtk.ProgressBar()
            bar.set_size_request(96, -1)
            bar.add_css_class("bar")
            col.append(bar)
            cap = Gtk.Label(label=caption)
            cap.add_css_class("caption")
            col.append(cap)
            charge = Gtk.Label(label="")
            charge.add_css_class("chargecloud")
            col.append(charge)
            self.cols[key] = {"big": big, "bar": bar, "charge": charge}
            row.append(col)
        card.append(row)

        self.revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=260,
            valign=Gtk.Align.START,
        )
        self.revealer.set_child(card)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self.revealer)
        win.set_child(outer)

        win.connect("notify::width", lambda *a: self.reposition())
        win.connect("notify::height", lambda *a: self.reposition())
        self.win = win

    def reposition(self):
        if not self.win:
            return
        display = self.win.get_display()
        monitor = None
        surface = self.win.get_surface()
        if surface:
            monitor = display.get_monitor_at_surface(surface)
        if not monitor:
            monitors = list(display.get_monitors())
            monitor = monitors[0] if monitors else None
        if not monitor:
            return
        geo = monitor.get_geometry()
        w = self.win.get_width()
        h = self.win.get_height()
        if w <= 0 or h <= 0:
            return
        x = geo.x + (geo.width - w) // 2
        y = geo.y + int(geo.height * 0.16)
        self.win.move(x, y)

    def refresh_card(self):
        if not self.win:
            return
        model = self.state.get("ModelName", "AirPods")
        fw = self.state.get("Firmware", "")
        self.lbl_title.set_text(model)

        connected = bool(self.state.get("Connected"))
        anc = {"noise": "Cancelación", "transparency": "Transparencia",
               "adaptive": "Adaptativo", "off": "Off"}.get(
            self.state.get("AncMode", "off"), self.state.get("AncMode", "off"))
        if connected:
            ears = []
            if self.state.get("EarLeft"):
                ears.append("L")
            if self.state.get("EarRight"):
                ears.append("R")
            ear_text = ("En oído: " + " ".join(ears)) if ears else "Fuera del oído"
            self.lbl_sub.set_text(f"ANC: {anc}   •   {ear_text}")
        else:
            self.lbl_sub.set_text("Desconectados")

        for key in ("L", "R", "C"):
            col = self.cols[key]
            level = int(self.state.get(
                {"L": "BatteryLeft", "R": "BatteryRight", "C": "BatteryCase"}[key],
                -1,
            ) or -1)
            charging = bool(self.state.get(
                {"L": "ChargingLeft", "R": "ChargingRight", "C": "ChargingCase"}[key],
                False,
            ))
            bar = col["bar"]
            bar.remove_css_class("low")
            bar.remove_css_class("critical")
            if level < 0:
                col["big"].set_text("--")
                col["bar"].set_fraction(0.0)
                col["charge"].set_text("")
                col["charge"].remove_css_class("charging")
            else:
                col["big"].set_text(f"{level}")
                col["bar"].set_fraction(max(0.0, min(1.0, level / 100.0)))
                if level < 30:
                    bar.add_css_class("critical")
                elif level < 60:
                    bar.add_css_class("low")
                if charging:
                    col["charge"].set_text("CARGANDO")
                    col["charge"].add_css_class("charging")
                else:
                    col["charge"].set_text("")
                    col["charge"].remove_css_class("charging")

    def snapshot(self):
        return (
            bool(self.state.get("Connected")),
            self.state.get("BatteryLeft", -1),
            self.state.get("BatteryRight", -1),
            self.state.get("BatteryCase", -1),
            bool(self.state.get("ChargingLeft")),
            bool(self.state.get("ChargingRight")),
            bool(self.state.get("ChargingCase")),
            self.state.get("AncMode", "off"),
            bool(self.state.get("EarLeft")),
            bool(self.state.get("EarRight")),
        )

    # -------------------------------------------------------------- show/hide
    def reset_hide_timer(self):
        self.clear_hide_timer()
        self.hide_timer = GLib.timeout_add_seconds(7, self.hide_pop)

    def clear_hide_timer(self):
        if self.hide_timer:
            try:
                GLib.source_remove(self.hide_timer)
            except Exception:
                pass

    def show_pop(self):
        if not self.revealer:
            return
        self.clear_hide_timer()
        self.refresh_card()

        def do_show():
            self.revealer.set_reveal_child(True)
            self.win.present()
            self.reposition()
            self.last_snap = self.snapshot()
            self.hide_timer = GLib.timeout_add_seconds(7, self.hide_pop)
            if os.environ.get("APD_TRACE"):
                print("[popup] show", flush=True)
            return False

        GLib.idle_add(do_show)

    def hide_pop(self):
        self.clear_hide_timer()
        if self.revealer:
            self.revealer.set_reveal_child(False)
            if os.environ.get("APD_TRACE"):
                print("[popup] hide", flush=True)
        return False

    # ------------------------------------------------------------------ app
    def on_activate(self, app):
        if self.win is None:
            self.dbus_connect()
            self.build_window(app)
        self.refresh_card()
        if self.state.get("Connected") or "--force" in sys.argv:
            self.show_pop()
        else:
            self.show_pop()
        try:
            app.hold()
        except Exception:
            pass


def main():
    p = Popup()
    code = p.app.run(None)
    return code or 0


if __name__ == "__main__":
    sys.exit(main())