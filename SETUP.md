# Setup Guide — What's On Today on a Raspberry Pi Zero

This guide walks through setting up the **What's On Today** InkyPi plugin on a fresh
Raspberry Pi Zero (2) W, including a practical way to get the Pi online at a **care
facility or any network where you do not have administrator access**.

---

## 1. What you'll need

- **Raspberry Pi Zero 2 W** (or any Wi-Fi capable Raspberry Pi)
- A compatible **e-ink display** supported by [InkyPi](https://github.com/fatihak/InkyPi)
- **microSD card** (8 GB+) and a way to write to it
- Power supply for the Pi
- A computer to flash the SD card
- The Wi-Fi you intend to use (see [Section 5](#5-getting-online-without-network-admin-access))

---

## 2. Flash the operating system (headless-ready)

Use the official **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)**. It
lets you pre-configure everything so the Pi works "headless" (no monitor/keyboard).

1. Choose **Raspberry Pi OS Lite (32-bit)** — no desktop is needed.
2. Click the **gear / edit settings** icon before writing and set:
   - **Hostname** (e.g. `inkypi`)
   - **Enable SSH** (password or public-key authentication)
   - **Username and password**
   - **Wi-Fi SSID, password, and Wi-Fi country** (important — the correct country
     code is required for Wi-Fi to enable)
   - **Locale / timezone**
3. Write the image, then insert the SD card into the Pi and power it on.

> Tip: Pre-seeding the Wi-Fi here works for simple **WPA2-PSK** networks. Networks with
> a browser login page (captive portals) need the approach in
> [Section 5](#5-getting-online-without-network-admin-access).

Once booted, connect over SSH:

```bash
ssh <username>@inkypi.local
```

---

## 3. Install InkyPi

Follow the upstream instructions at <https://github.com/fatihak/InkyPi>. In brief:

```bash
sudo apt update && sudo apt full-upgrade -y
git clone https://github.com/fatihak/InkyPi.git
cd InkyPi
sudo bash install/install.sh
```

The installer sets up the display drivers, the web interface, and a systemd service.
When it finishes, open the InkyPi web UI in a browser at `http://inkypi.local` (or the
Pi's IP address).

---

## 4. Install the *What's On Today* plugin

From your computer, copy this repository's `whats_on_today` folder into the InkyPi
`src/plugins/` directory on the Pi:

```bash
# From the root of this repository, on your computer:
scp -r whats_on_today <username>@inkypi.local:~/InkyPi/src/plugins/
```

Then register the plugin in the InkyPi plugin configuration (see the JSON snippet in the
[README](README.md#installation)) and restart the InkyPi service:

```bash
sudo systemctl restart inkypi
```

### Configure it in the web UI

Open the InkyPi web interface, add the **What's On Today** plugin to a playlist, and set:

| Setting | Example |
|---|---|
| **Calendar URL** | your Google/Apple iCal `.ics` URL |
| **Weather Latitude** | `-33.87` |
| **Weather Longitude** | `151.21` |
| **Weather Display Mode** | `Current observations` or `Daily forecast (Low / High)` |

Set the playlist **refresh interval to 15 minutes** (see the README for why).

---

## 5. Getting online without network admin access

Care facilities, hotels, and offices often run Wi-Fi that you cannot administer. The
main obstacles for a headless device like the Pi Zero are:

- **Captive portals** — a web page you must accept/log in to before internet works. A
  headless Pi has no browser, so it cannot get past these on its own.
- **No access to register devices** — you can't ask IT to whitelist the Pi's MAC address.
- **Credentials may change** or you may not be given them at all.

Below are three approaches, best first.

### Option A (recommended): a small travel router

Use a pocket **travel router** such as a
[GL.iNet](https://www.gl-inet.com/) model (e.g. *GL-MT300N-V2 "Mango"* or *GL-AXT1800
"Slate AX"*). These act as a Wi-Fi **repeater/relay**:

1. Power the travel router near the Pi.
2. From your **phone or laptop**, open the router's admin page and connect it to the
   facility Wi-Fi. If there is a captive portal, the router presents it to you once and
   remembers the session.
3. Give the travel router its own **private SSID and password**.
4. Configure the **Pi to join the travel router's private SSID** (set this in Raspberry
   Pi Imager in [Section 2](#2-flash-the-operating-system-headless-ready)).

Why this is the best option:

- **No facility admin access needed** — you only interact with your own router.
- **Captive portal handled once**, by a device with a browser (your phone).
- **The Pi's Wi-Fi config never changes**, even if you move to another site — you only
  re-point the travel router.
- Many models also accept a **USB 4G/5G modem** or a phone tether as the upstream.

### Option B: a dedicated mobile hotspot / 4G

If the facility permits cellular and you have data allowance:

- Use a **MiFi / 4G dongle** or a **spare phone as a hotspot** with a fixed SSID and
  password, and point the Pi at it (via Raspberry Pi Imager).
- Simple and completely independent of facility Wi-Fi, but uses mobile data.

### Option C: pre-seed the facility Wi-Fi directly

Only reliable if the network is a **simple WPA2-PSK** Wi-Fi with **no captive portal**
and you have the SSID and password:

- Enter them in Raspberry Pi Imager ([Section 2](#2-flash-the-operating-system-headless-ready)), **or**
- Edit Wi-Fi settings on the Pi later:

  ```bash
  sudo raspi-config    # System Options → Wireless LAN
  ```

If you may need the Pi's **Wi-Fi MAC address** for IT to whitelist it:

```bash
cat /sys/class/net/wlan0/address
```

> Note: If Wi-Fi shows as connected but there is no internet, a captive portal is almost
> always the cause — switch to Option A or B.

---

## 6. Verifying the display

- Watch the InkyPi web UI logs, or on the Pi:

  ```bash
  journalctl -u inkypi -f
  ```

- The plugin logs how many events it found and whether weather was fetched. If weather
  is blank, check that latitude/longitude are set and the Pi has internet access.

---

## 7. Troubleshooting quick reference

| Symptom | Likely cause / fix |
|---|---|
| Pi never comes online | Wrong Wi-Fi country code, or captive portal — use a travel router (Option A). |
| Wi-Fi "connected" but no data | Captive portal not completed — use Option A/B. |
| No weather shown | Latitude/longitude missing, or no internet. |
| Events missing | Check the calendar URL is a direct `.ics` feed and is publicly reachable. |
| Can't reach `inkypi.local` | Use the Pi's IP address instead (check your router's client list). |
