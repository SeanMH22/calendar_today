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

### Option A: `inkypi plugin install` (if available)

If your InkyPi install has the `inkypi` CLI with plugin support — for example via
[InkyPi-Plugin-PluginManager](https://github.com/RobinWts/InkyPi-Plugin-PluginManager),
either from its own GUI or over SSH on the Pi:

```bash
inkypi plugin install whats_on_today https://github.com/SeanMH22/calendar_today
```

This repo's `whats_on_today/` folder already matches the structure InkyPi expects for
a third-party plugin (a folder named after the plugin id, with `plugin-info.json`
inside), so it installs the same way any other third-party plugin would. It handles
copying the code into `src/plugins/` and restarting the InkyPi service for you — skip
the manual steps below and go straight to
[Configure it in the web UI](#configure-it-in-the-web-ui).

### Option B: manual copy

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

#### Editing `wpa_supplicant.conf` directly

> **Check which is actually in control first.** Modern Raspberry Pi OS (Bookworm and
> later) manages Wi-Fi through **NetworkManager** by default, not wpa_supplicant
> directly — in which case editing `wpa_supplicant.conf` does nothing at all, silently.
> Check with:
>
> ```bash
> systemctl status wpa_supplicant
> ```
>
> Look at the `ExecStart` line. If it has **no `-c /path/to/wpa_supplicant.conf`** flag
> (e.g. just `-u -s -O "DIR=/run/wpa_supplicant GROUP=netdev"`), it's being driven over
> D-Bus — almost always by NetworkManager — and the file below is inert. Confirm with
> `nmcli device status`: if `wlan0` shows `connected`/`connecting`, skip ahead to
> [Configuring Wi-Fi via NetworkManager](#configuring-wi-fi-via-networkmanager-nmcli)
> instead and don't bother editing this file.

For finer control — including multiple networks with fallback priority — edit the file
directly on the Pi:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

The file should begin with:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=AU
```

Replace `AU` with your two-letter country code if different.

**Standard WPA2-PSK network (password protected):**

```
network={
    ssid="YourNetworkName"
    psk="YourPassword"
    key_mgmt=WPA-PSK
    priority=10
}
```

**Open network with no password (e.g. a captive portal SSID):**

```
network={
    ssid="CareHomeWiFi"
    key_mgmt=NONE
    priority=20
}
```

**Multiple networks with fallback:**

Higher `priority` values are tried first. The Pi will fall back to lower-priority
networks if the preferred one is unavailable:

```
country=AU
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

# Home / trusted network — preferred
network={
    ssid="HomeNetwork"
    psk="HomePassword"
    key_mgmt=WPA-PSK
    priority=5
}

# Mobile hotspot — second choice
network={
    ssid="MyPhone"
    psk="HotspotPassword"
    key_mgmt=WPA-PSK
    priority=10
}

# Facility open Wi-Fi — fallback (captive portal)
network={
    ssid="CareHomeWiFi"
    key_mgmt=NONE
    priority=20
}
```

**Apply changes without rebooting:**

```bash
wpa_cli -i wlan0 reconfigure
```

Or force a full reconnect:

```bash
sudo systemctl restart dhcpcd
```

> **Captive portal caveat:** If the fallback network has a captive portal, the Pi will
> associate with it and get an IP address, but internet will be blocked until the portal
> is authenticated. See the notes in Section 5 about automating portal login with
> `curl`, or use Option A (travel router) to handle the portal once via a browser.

#### Configuring Wi-Fi via NetworkManager (`nmcli`)

If the check above showed NetworkManager is in control, configure networks through
`nmcli` instead — edits to `wpa_supplicant.conf` won't have any effect.

**Add an open network with a captive portal:**

```bash
sudo nmcli connection add type wifi con-name "CareHomeWiFi" ifname wlan0 ssid "CareHomeWiFi"
sudo nmcli connection up "CareHomeWiFi"
```

Two gotchas found the hard way:

- **Don't set `wifi-sec.key-mgmt none`** to mean "open network" — in NetworkManager
  that setting actually means **WEP**, and it will fail waiting for a WEP key you don't
  have. For a genuinely open network, create the profile with no security block at all
  (as above); NetworkManager detects it's open from the scan.
- **A stale saved profile for the same SSID can get contaminated** with leftover 802.1X
  (enterprise auth) settings, producing a misleading `802.1X supplicant took too long to
  authenticate` error even though the network is plain and open. If you see that error,
  don't chase it as a signal or auth problem — delete the profile and recreate it clean:

  ```bash
  sudo nmcli connection delete "CareHomeWiFi"
  sudo nmcli connection add type wifi con-name "CareHomeWiFi" ifname wlan0 ssid "CareHomeWiFi"
  sudo nmcli connection up "CareHomeWiFi"
  ```

A weak or marginal signal (roughly below -80 dBm) can also cause several
scanning → associating → disconnected retries before it lands — normal on a large
facility network with multiple access points, not a config problem. Give it 30–60
seconds before assuming it's failed.

**Check status:**

```bash
nmcli device status
ip addr show wlan0
```

You want `wlan0` as `connected` with a real `inet` address (not a `169.254.x.x`
link-local address, which means association succeeded but DHCP failed).

NetworkManager connections persist and auto-reconnect on boot by default
(`autoconnect=yes`). So once this profile is created and working, **Layer-2
association after a restart should already be automatic** — the only piece that still
needs handling headlessly is the captive-portal login itself, covered next.

#### Auto-completing a username/password captive portal login

Whichever layer is managing Wi-Fi *association* (Layer 2) — wpa_supplicant directly,
or NetworkManager as above — it will reconnect to the facility SSID on its own after a
reboot. What neither can do is the *portal login* (Layer 3):
the HTTP form a captive portal shows before it will route your traffic. If that form
needs a username and password, the Pi will be associated to Wi-Fi but stuck with no
internet until the form is submitted — normally requiring a screen and keyboard.

This repo includes a small headless script, in [`captive-portal/`](captive-portal/),
that automates that form submission — no browser, X server, or travel router required.
It runs on a timer: checks for internet, and if blocked, fetches the portal's login
page and POSTs your saved credentials into whatever form it finds.

**One-time setup on the Pi:**

Get the code onto the Pi first — over SSH, clone the repo directly on the Pi (same
approach as installing InkyPi itself in [Section 3](#3-install-inkypi)):

```bash
git clone https://github.com/SeanMH22/calendar_today.git
cd calendar_today
```

Then, still on the Pi, from inside that `calendar_today` directory:

```bash
sudo apt install -y python3-requests python3-bs4

sudo mkdir -p /opt/captive-portal /etc/captive-portal /var/log/captive-portal
sudo cp captive-portal/captive_login.py /opt/captive-portal/
sudo cp captive-portal/config.example.ini /etc/captive-portal/config.ini
sudo nano /etc/captive-portal/config.ini   # fill in username/password
sudo chmod 600 /etc/captive-portal/config.ini

sudo cp captive-portal/captive-portal-login.service /etc/systemd/system/
sudo cp captive-portal/captive-portal-login.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now captive-portal-login.timer
```

The timer runs 30 seconds after boot and every 5 minutes thereafter (a no-op if
already online), so a restart at the facility no longer needs a screen and keyboard.

**Getting the field names right:** the script guesses the login form's field names are
`username` and `password`. Real portals vary. If login keeps failing, check the saved
page in `/var/log/captive-portal/` (dumped automatically on a failed attempt) for the
actual `<input name="...">` values, and update `username_field` / `password_field` in
`config.ini` to match.

**Check it worked:**

```bash
sudo systemctl status captive-portal-login.service
journalctl -u captive-portal-login.service -f
cat /run/captive-portal-status   # "ok" or "failed"
```

---

## 6. Accessing the InkyPi admin UI

The InkyPi admin page is a **web server running on the Pi** — you do not need a browser
on the Pi itself. Open it from any phone or laptop on the same network:

```
http://inkypi.local
```

or by IP address if mDNS (`.local`) does not resolve on your network. Find the IP with:

```bash
hostname -I
```

> **Avoid using Raspberry Pi Connect's screen share + Chromium on the Pi Zero 2 W.**
> The Pi Zero 2 W has only 512 MB RAM; Chromium warns it is unsupported and the remote
> desktop session is very CPU-intensive. Use one of the options below instead.

> **Network security note:** Raspberry Pi Connect, like Tailscale, uses outbound-only
> encrypted tunnels to Raspberry Pi's relay servers. It does not open any inbound ports
> on the local network and is not visible to other devices on the facility Wi-Fi.

### Option A: same-network browser (simplest)

If your laptop or phone is on the same Wi-Fi as the Pi (or the travel router from
[Section 5](#5-getting-online-without-network-admin-access)), just open
`http://inkypi.local` in a browser. For terminal access use Raspberry Pi Connect's
**Remote shell** (SSH) rather than Screen share — it is lightweight.

### Option B: Tailscale — access from anywhere (recommended for ongoing remote admin)

[Tailscale](https://tailscale.com/) creates a private encrypted network between your
devices. No port forwarding or firewall changes are needed.

1. Install on the Pi:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

2. Install Tailscale on your laptop and/or phone from <https://tailscale.com/download>.
3. Browse to `http://<pi-tailscale-ip>` from any of your devices, anywhere.

The Tailscale IP for the Pi is shown after `sudo tailscale up`, or in the
[Tailscale admin console](https://login.tailscale.com/admin/machines). Tailscale is
free for personal use (up to 100 devices).

> **Network security note:** Tailscale operates as an outbound-only, encrypted
> tunnelling solution. The Pi initiates the connection to Tailscale's coordination
> servers — it does not open any ports or expose any services to the local facility
> network. From the perspective of the local network, it is indistinguishable from
> ordinary outbound HTTPS traffic.

### Option C: SSH tunnel (no extra software)

Forward the Pi's web UI to your local machine over SSH:

```bash
ssh -L 8080:localhost:80 <username>@inkypi.local
```

Then open `http://localhost:8080` in your browser. Much lighter than screen sharing
and requires no additional software beyond SSH.

---

## 8. Verifying the display

- Watch the InkyPi web UI logs, or on the Pi:

  ```bash
  journalctl -u inkypi -f
  ```

- The plugin logs how many events it found and whether weather was fetched. If weather
  is blank, check that latitude/longitude are set and the Pi has internet access.

---

## 9. Troubleshooting quick reference

| Symptom | Likely cause / fix |
|---|---|
| Pi never comes online | Wrong Wi-Fi country code, or captive portal — use a travel router (Option A). |
| Wi-Fi "connected" but no data | Captive portal not completed — use Option A/B. |
| No weather shown | Latitude/longitude missing, or no internet. |
| Events missing | Check the calendar URL is a direct `.ics` feed and is publicly reachable. |
| Can't reach `inkypi.local` | Use the Pi's IP address instead (check your router's client list). |

## 10. Captive Portal WiFi Setup — manual fallback

Some networks (aged care facilities, hotels, etc.) require you to load a login
page in a browser before the device gets real internet access. Since the Pi
usually runs headless with no desktop environment, this needs a one-off
graphical session.

> **This is a fallback, not the primary approach.** The headless script in
> [Section 5](#auto-completing-a-usernamepassword-captive-portal-login) handles
> routine re-logins automatically, with no screen or keyboard needed. Reach for the
> manual steps below only when:
>
> - You're setting up a new facility Wi-Fi for the first time and need to see the
>   portal's actual login page to fill in [`captive-portal/config.ini`](captive-portal/config.example.ini) correctly (field names, any extra required fields), or
> - The portal requires JavaScript, a CAPTCHA, or some other interactive step the
>   headless script's plain HTTP form submission can't handle.

### Requirements

- Direct-connected screen, keyboard, and mouse (temporary — not needed after setup)
- `matchbox-window-manager` and `netsurf-gtk` installed

```bash
sudo apt install -y matchbox-window-manager netsurf-gtk
```

### One-off graphical login session

1. Create `~/.xinitrc` so `startx` launches a minimal window manager plus the
   browser, full-screen, with nothing else running:

   ```bash
   cat > ~/.xinitrc <<'EOF'
   exec matchbox-window-manager &
   exec netsurf-gtk
   EOF
   ```

2. With the screen, keyboard, and mouse connected, start the graphical session from
   the console:

   ```bash
   startx
   ```

3. In NetSurf, browse to any plain HTTP address to trigger the portal redirect —
   for example:

   ```
   http://neverssl.com
   ```

   This should redirect to the facility's login page. Enter the username and
   password and submit the form.

4. Once the portal confirms you're logged in, close NetSurf (window close button,
   or `Ctrl+Alt+Backspace` if it's stuck) to exit back to the console — `startx`
   will return.

5. Confirm you actually have internet before disconnecting the screen:

   ```bash
   curl -sI http://neverssl.com
   ```

   A normal HTTP response (not another redirect to the portal) means you're
   through. You can now unplug the screen, keyboard, and mouse.

6. If you were here to capture the portal's form for the headless script, view
   NetSurf's page source on the login page (or check
   `/var/log/captive-portal/portal-*.html`, saved automatically the next time the
   script's own attempt fails) for the real `<input name="...">` values, and update
   `username_field` / `password_field` in `/etc/captive-portal/config.ini`
   accordingly.
