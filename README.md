# airpods-helper-linux

Apple-style popup + Waybar module to show your AirPods battery on Linux
(Hyprland/Wayland), backed by the [airpods-helper](https://github.com/superninjv/airpods-helper)
daemon.

<div align="center">

![Popup](./docs/popup.png)

</div>

The daemon publishes its state over D-Bus (`org.costa.AirPods`) and these
scripts render it:

- **`airpods-helper-popup.py`**: a macOS-style floating card that appears when
  the AirPods connect (or on demand) and fades out after 7 s.
- **`airpods-helper-bar.py`**: a Waybar module with percentages and state
  classes (`high` / `low` / `critical` / `disconnected`).

## Requirements

- [airpods-helper](https://github.com/superninjv/airpods-helper) installed and
  running (`airpods-daemon` exposing `org.costa.AirPods` over D-Bus).
- `python-gobject` (pygobject) and `gtk4`.

## Installation

Copy both scripts into your `PATH`, e.g.:

```bash
install -m 755 airpods-helper-popup.py ~/.local/bin/
install -m 755 airpods-helper-bar.py   ~/.local/bin/
```

### Hyprland

In `~/.config/hypr/hyprland.conf`:

```conf
exec-once = ~/.local/bin/airpods-helper-popup.py
bind = SUPER, A, exec, ~/.local/bin/airpods-helper-popup.py
windowrulev2 = float, title:^(AirPods)$
windowrulev2 = noborder, title:^(AirPods)$
windowrulev2 = noresize, title:^(AirPods)$
windowrulev2 = noinitialfocus, title:^(AirPods)$
windowrulev2 = move 50% 16%, title:^(AirPods)$
```

### Waybar

Example module (`config.jsonc`):

```jsonc
"custom/airpods": {
    "exec": "~/.local/bin/airpods-helper-bar.py --json",
    "return-type": "json",
    "interval": 5,
    "tooltip": true,
    "format": "{}"
}
```

Available CSS classes: `high`, `low`, `critical`, `disconnected`.

## Usage

```bash
airpods-helper-bar.py           # plain text:  L 100%  R 90%  C 47%
airpods-helper-bar.py --json    # for waybar (return-type: json)
airpods-helper-popup.py         # start/activate the popup (single instance)
```

The popup uses `Gio.Application` with `application_id = org.costa.AirPodsPopup`:
if an instance is already running, invoking it again simply re-activates it
(great for a keyboard binding). It auto-hides after 7 s and only stays visible
while the battery values change.

## airpods-helper config

If your AirPods keep connecting/disconnecting repeatedly while in the case,
disable auto-reconnect in `~/.config/airpods-helper/config.toml`:

```toml
auto_reconnect = false
```

## Troubleshooting

- **`br-connection-key-missing` when connecting**: re-pair the AirPods and
  confirm the device is trusted with `bluetoothctl`.
- **The popup does not appear**: make sure the daemon is active
  (`systemctl --user status airpods-daemon`) and that the Hyprland `float` /
  `noborder` rules are applied.