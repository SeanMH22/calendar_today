#!/usr/bin/env python3
"""Detect a captive Wi-Fi portal and auto-submit saved login credentials.

Runs headlessly (no browser, no X server) — intended to be triggered by
captive-portal-login.timer on boot and periodically thereafter. See
../SETUP.md for deployment instructions.
"""

import configparser
import logging
import os
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

CONFIG_PATH = os.environ.get("CAPTIVE_PORTAL_CONFIG", "/etc/captive-portal/config.ini")
STATUS_PATH = "/run/captive-portal-status"
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("captive-portal-login")


def write_status(status):
    try:
        with open(STATUS_PATH, "w") as f:
            f.write(status + "\n")
    except OSError as exc:
        logger.warning(f"Could not write status file: {exc}")


def has_internet(session):
    """A direct GET to the probe URL returns 204 with no redirect only when
    there is no captive portal intercepting traffic."""
    try:
        resp = session.get(PROBE_URL, timeout=10, allow_redirects=False)
        return resp.status_code == 204
    except requests.exceptions.RequestException:
        return False


def fetch_portal_page(session, portal_url=None):
    """Land on the actual portal login page.

    Some routers don't reliably intercept/redirect the generate_204 probe
    (it just times out or returns the real Google response), even though
    navigating straight to the portal's own hostname always works. If
    portal_url is configured, hit it directly instead of relying on the
    probe redirect."""
    if portal_url:
        return session.get(portal_url, timeout=10, allow_redirects=True)
    return session.get(PROBE_URL, timeout=10, allow_redirects=True)


def save_debug_html(debug_dir, html):
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"portal-{int(time.time())}.html")
    with open(path, "w") as f:
        f.write(html)
    logger.info(f"Saved captive portal page to {path} for inspection")


def submit_login(session, page_response, username, password, username_field, password_field, debug_dir):
    soup = BeautifulSoup(page_response.text, "html.parser")
    form = soup.find("form")
    if form is None:
        save_debug_html(debug_dir, page_response.text)
        raise RuntimeError("No <form> found on captive portal page")

    action_url = urljoin(page_response.url, form.get("action") or page_response.url)
    method = (form.get("method") or "get").lower()

    data = {}
    for field in form.find_all(["input", "select", "textarea"]):
        name = field.get("name")
        if name:
            data[name] = field.get("value", "")

    if username_field not in data or password_field not in data:
        save_debug_html(debug_dir, page_response.text)
        logger.warning(
            f"Configured field names ({username_field!r}/{password_field!r}) "
            f"not found in form fields {list(data.keys())} — check the saved "
            "debug HTML and update config.ini"
        )

    data[username_field] = username
    data[password_field] = password

    logger.info(f"Submitting portal login to {action_url} (method={method})")
    if method == "post":
        resp = session.post(action_url, data=data, timeout=15)
    else:
        resp = session.get(action_url, params=data, timeout=15)
    resp.raise_for_status()
    return resp


def main():
    config = configparser.ConfigParser()
    if not config.read(CONFIG_PATH):
        logger.error(f"Could not read config file at {CONFIG_PATH}")
        sys.exit(1)

    cfg = config["captive_portal"]
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    portal_url = cfg.get("portal_url", "")
    username_field = cfg.get("username_field", "username")
    password_field = cfg.get("password_field", "password")
    debug_dir = cfg.get("debug_dir", "/var/log/captive-portal")
    retries = cfg.getint("retries", 3)
    retry_delay = cfg.getfloat("retry_delay_seconds", 5)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; captive-portal-login/1.0)"})

    if has_internet(session):
        logger.info("Already have internet access, nothing to do")
        write_status("ok")
        return

    logger.info("No internet detected, attempting captive portal login")
    for attempt in range(1, retries + 1):
        try:
            page = fetch_portal_page(session, portal_url)
            submit_login(session, page, username, password, username_field, password_field, debug_dir)
            time.sleep(2)
            if has_internet(session):
                logger.info("Captive portal login succeeded")
                write_status("ok")
                return
            logger.warning(f"Attempt {attempt}/{retries}: login submitted but still no internet")
        except Exception as exc:
            logger.warning(f"Attempt {attempt}/{retries} failed: {exc}")
        time.sleep(retry_delay)

    logger.error("Failed to complete captive portal login after all retries")
    write_status("failed")
    sys.exit(1)


if __name__ == "__main__":
    main()
