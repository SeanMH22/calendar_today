import logging
import subprocess
import time
import requests
import icalendar
import recurring_ical_events
import pytz
import os
from datetime import datetime, date, timedelta
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

# Device-config keys used to persist the last successfully fetched calendar
# (so a later refresh that can't reach the internet can still show a real
# schedule instead of an error screen) and the current offline streak.
CACHE_KEY = "whats_on_today_cache"
OFFLINE_KEY = "whats_on_today_offline"

# How long a *network-level* failure (timeout/connection refused/DNS) has to
# persist before we try a self-recovery reboot. Generous enough to ride out
# a few refresh cycles first — a reboot is a last resort, not the first move.
REBOOT_AFTER_OFFLINE_MINUTES = 30


class CalendarNetworkError(Exception):
    """The calendar server couldn't be reached at all (timeout, connection
    refused, DNS failure) — the kind of failure a Wi-Fi reconnect/reboot
    might actually fix."""


class CalendarDataError(Exception):
    """The calendar server responded, but the content wasn't a parseable
    calendar (e.g. a captive-portal page instead of the real feed, or
    malformed ICS). A reboot can't fix that, only the far end can."""


class WhatsOnToday(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        calendar_url = settings.get("calendarURL", "").strip()
        if not calendar_url:
            raise RuntimeError("A calendar URL is required.")

        # device_config.get_resolution() always returns the panel's fixed native
        # resolution, regardless of orientation — InkyPi's display pipeline rotates
        # whatever image the plugin renders by 90° first, then resizes it to that
        # native resolution. So when the device is vertically mounted, we must
        # render at the *swapped* dimensions here — that way, after InkyPi's 90°
        # rotation, the image already exactly matches the native resolution with
        # no distorting resize. (See display_manager.py's display_image().)
        is_portrait = device_config.get_config("orientation") == "vertical"
        dimensions = device_config.get_resolution()
        if is_portrait:
            dimensions = dimensions[::-1]

        timezone = device_config.get_config("timezone", default="Australia/Sydney")
        time_format = device_config.get_config("time_format", default="12h")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        today = now.date()

        day_name = now.strftime("%A")
        # Landscape puts the date beside the (large) day name, so it needs the
        # shorter "%b" form to fit at a readable size; portrait stacks them
        # and has room for the full month name.
        long_date = now.strftime("%-d %b %Y") if not is_portrait else now.strftime("%-d %B %Y")
        # Determine if weekend (Saturday=5, Sunday=6)
        day_type = "weekend" if now.weekday() >= 5 else "weekday"

        logger.info(f"Generating display at {now.strftime('%Y-%m-%d %H:%M:%S')}")

        cache = device_config.get_config(CACHE_KEY, default=None)
        is_stale = False
        stale_message = None
        events = []
        weather = None

        try:
            ics_text = self._fetch_calendar_text(calendar_url)
            events = self._parse_events_for_today(ics_text, tz, today, time_format, now)
            logger.info(f"Found {len(events)} event(s) for today")

            weather = self._fetch_weather_for_settings(settings, timezone)
            if weather is None and settings.get("weatherLatitude", "").strip() and cache:
                # Weather API had its own blip even though the calendar came
                # through fine — fall back to the last good reading rather
                # than just dropping the weather section.
                weather = cache.get("weather")

            # Success — refresh the cache and clear any offline streak.
            device_config.update_value(CACHE_KEY, {
                "ics_text": ics_text,
                "fetched_at": now.isoformat(),
                "weather": weather,
            })
            device_config.update_value(
                OFFLINE_KEY, {"since": None, "stale_count": 0, "rebooted_for": None}, write=True
            )

        except (CalendarNetworkError, CalendarDataError) as exc:
            logger.error(f"Could not refresh today's information: {exc}")
            self._record_offline_attempt(device_config, now, is_network_error=isinstance(exc, CalendarNetworkError))

            if cache and cache.get("ics_text"):
                try:
                    events = self._parse_events_for_today(cache["ics_text"], tz, today, time_format, now)
                    weather = cache.get("weather")
                    is_stale = True
                    fetched_at = datetime.fromisoformat(cache["fetched_at"]).astimezone(tz)
                    stale_message = f"Showing saved info from {self._format_time(fetched_at, time_format)}"
                except Exception as cache_exc:
                    logger.warning(f"Cached calendar data unusable, falling back to error screen: {cache_exc}")
                    cache = None

            if not cache or not cache.get("ics_text"):
                # No usable cache yet (e.g. first run with no internet) —
                # this is the only case where we show the plain error tile.
                template_params = {
                    "day_name": day_name,
                    "long_date": long_date,
                    "day_type": day_type,
                    "is_portrait": is_portrait,
                    "connection_error": True,
                    "connection_message": self._connection_error_message(),
                }
                image = self.render_image(
                    dimensions, "whats_on_today.html", "whats_on_today.css", template_params
                )
                if not image:
                    raise RuntimeError("Failed to render calendar image, please check logs.")
                return image

        template_params = {
            "day_name": day_name,
            "long_date": long_date,
            "day_type": day_type,
            "is_portrait": is_portrait,
            "events": events,
            "weather": weather,
            "time_format": time_format,
            "plugin_settings": settings,
            "connection_error": False,
            "is_stale": is_stale,
            "stale_message": stale_message,
        }

        image = self.render_image(
            dimensions, "whats_on_today.html", "whats_on_today.css", template_params
        )
        if not image:
            raise RuntimeError("Failed to render calendar image, please check logs.")
        return image

    def _fetch_weather_for_settings(self, settings, timezone):
        latitude = settings.get("weatherLatitude", "").strip()
        longitude = settings.get("weatherLongitude", "").strip()
        weather_mode = settings.get("weatherMode", "current")
        if not (latitude and longitude):
            logger.info("No weather coordinates configured - skipping weather fetch")
            return None
        if weather_mode == "forecast":
            return self.fetch_daily_forecast(latitude, longitude, timezone)
        return self.fetch_weather(latitude, longitude, timezone)

    def _record_offline_attempt(self, device_config, now, is_network_error):
        """Track how long we've been failing to fetch fresh data and, once a
        genuine network failure has persisted past the threshold, trigger a
        one-shot recovery reboot. Never reboots for a merely-unparseable
        response (e.g. a server-side error) — that's not something a reboot
        can fix."""
        offline = device_config.get_config(OFFLINE_KEY, default={}) or {}
        offline_since = offline.get("since") or now.isoformat()
        stale_count = offline.get("stale_count", 0) + 1
        rebooted_for = offline.get("rebooted_for")

        should_reboot = False
        if is_network_error:
            minutes_offline = (now - datetime.fromisoformat(offline_since)).total_seconds() / 60
            should_reboot = minutes_offline >= REBOOT_AFTER_OFFLINE_MINUTES and rebooted_for != offline_since
            if should_reboot:
                logger.error(f"No internet for {minutes_offline:.0f} min — rebooting to try to recover Wi-Fi")
                rebooted_for = offline_since

        device_config.update_value(
            OFFLINE_KEY,
            {"since": offline_since, "stale_count": stale_count, "rebooted_for": rebooted_for},
            write=True,
        )

        if should_reboot:
            self._attempt_reboot()

    def _attempt_reboot(self):
        """Best-effort recovery reboot. Never let a failure here take down
        image generation — worst case, no reboot happens and we just keep
        showing the cached dashboard until the next attempt."""
        try:
            subprocess.run(["sudo", "reboot"], check=False, timeout=10)
        except Exception as exc:
            logger.error(f"Could not trigger recovery reboot: {exc}")

    def _connection_error_message(self):
        """Pick a message based on the captive-portal login script's last status,
        if it's installed (see ../captive-portal/). Falls back to a generic
        message when that status file isn't present."""
        status = None
        try:
            with open("/run/captive-portal-status") as f:
                status = f.read().strip()
        except OSError:
            pass

        if status == "failed":
            return "Wi-Fi login needed — reconnecting automatically"
        return "No internet connection"

    def _fetch_calendar_text(self, calendar_url):
        """Fetch the raw ICS text for *calendar_url*. Raises CalendarNetworkError
        if the server can't be reached at all (timeout/connection refused/DNS) —
        the cache-fallback and reboot logic in generate_image() only apply to
        this class of failure."""
        # Support webcal:// scheme
        if calendar_url.startswith("webcal://"):
            calendar_url = calendar_url.replace("webcal://", "https://")

        try:
            response = self._get_with_retry(calendar_url, params=None, timeout=30)
            return response.text
        except requests.exceptions.RequestException as exc:
            raise CalendarNetworkError(f"Could not reach calendar: {exc}") from exc

    def _parse_events_for_today(self, ics_text, tz, today, time_format, now):
        """Parse ICS text and return up to 2 events relevant to *today*. Used
        both for freshly fetched text and for cached text on a later refresh —
        recomputing against the live *today*/*now* either way, so a cached
        feed still renders correctly on a different day. Raises
        CalendarDataError if the content isn't a parseable calendar (e.g. a
        captive-portal page instead of the real feed)."""
        try:
            cal = icalendar.Calendar.from_ical(ics_text)
        except Exception as exc:
            raise CalendarDataError(f"Could not parse calendar: {exc}") from exc

        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)
        end_of_day = start_of_day + timedelta(days=1)

        try:
            raw_events = recurring_ical_events.of(cal).between(start_of_day, end_of_day)
        except Exception as exc:
            raise CalendarDataError(f"Could not expand recurring events: {exc}") from exc

        events = []
        for event in raw_events:
            try:
                summary = str(event.get("summary", "(No title)"))
                description = str(event.get("description", "") or "")
                note_lines = self._first_lines(description, max_lines=2)

                dtstart = event.decoded("dtstart") if "dtstart" in event else None
                dtend = event.decoded("dtend") if "dtend" in event else None

                # Skip events that have finished
                if self._is_event_finished(dtstart, dtend, now, tz):
                    continue
                
                # Check if event is currently in progress
                is_in_progress = self._is_event_in_progress(dtstart, dtend, now, tz)
                
                # Skip in-progress events that started more than 15 minutes ago
                if is_in_progress and dtstart and isinstance(dtstart, datetime):
                    minutes_since_start = (now - dtstart.astimezone(tz)).total_seconds() / 60
                    if minutes_since_start > 15:
                        continue
                
                # Determine urgency based on time until event
                urgency = self._calculate_urgency(dtstart, now, tz)

                if dtstart and isinstance(dtstart, datetime):
                    start_str = self._format_time(dtstart.astimezone(tz), time_format)
                else:
                    start_str = "All day"

                if dtend and isinstance(dtend, datetime):
                    end_str = self._format_time(dtend.astimezone(tz), time_format)
                elif isinstance(dtend, date):
                    end_str = ""
                else:
                    end_str = ""

                events.append({
                    "summary": summary,
                    "start": start_str,
                    "end": end_str,
                    "notes": note_lines,
                    "urgency": urgency,
                    "is_in_progress": is_in_progress,
                    "dtstart": dtstart,
                })
            except Exception as exc:
                logger.warning(f"Skipping malformed event: {exc}")
                continue

        # Sort chronologically: all-day events last, then by start time (early to late)
        events.sort(key=lambda e: (
            e["start"] == "All day",   # All-day events last
            e["dtstart"] if e["dtstart"] and isinstance(e["dtstart"], datetime) else datetime.max.replace(tzinfo=tz)
        ))
        
        # Remove the dtstart field (only needed for sorting)
        for event in events:
            event.pop("dtstart", None)
        
        # Limit to next 2 events
        return events[:2]

    def _is_event_finished(self, dtstart, dtend, now, tz):
        """Check if event has finished."""
        if not dtstart or not isinstance(dtstart, datetime):
            return False  # All-day events are not considered "finished"
        
        # If there's an end time, check if it has passed
        if dtend and isinstance(dtend, datetime):
            end_dt = dtend.astimezone(tz)
            return end_dt <= now
        
        # No end time - not considered finished
        return False
    
    def _is_event_in_progress(self, dtstart, dtend, now, tz):
        """Check if event is currently in progress."""
        if not dtstart or not isinstance(dtstart, datetime):
            return False  # All-day events are not considered "in progress"
        
        start_dt = dtstart.astimezone(tz)
        
        # If no end time, check if start time has passed
        if not dtend or not isinstance(dtend, datetime):
            return start_dt <= now
        
        end_dt = dtend.astimezone(tz)
        return start_dt <= now < end_dt
    
    def _calculate_urgency(self, dtstart, now, tz):
        """Calculate urgency level based on time until event.
        Returns: 'in_progress' (red), 'imminent' (orange), 'soon' (yellow), 'allday' (blue), or 'normal' (yellow)
        """
        if not dtstart or not isinstance(dtstart, datetime):
            return "allday"  # All-day events in blue
        
        time_until_minutes = (dtstart.astimezone(tz) - now).total_seconds() / 60
        
        # Event has already started (negative time means it's in the past/ongoing)
        if time_until_minutes < 0:
            return "imminent"  # Red for in-progress events
        elif 0 <= time_until_minutes <= 15:
            return "soon"  # Orange - starts within 15 minutes
        else:
            return "normal"  # Yellow - regular upcoming event

    def _format_time(self, dt, time_format):
        """Format datetime according to time_format (12h or 24h)."""
        if time_format == "24h":
            return dt.strftime("%H:%M")
        else:
            # Default to 12h format
            return dt.strftime("%I:%M %p").lstrip("0")

    def _first_lines(self, text, max_lines=2):
        """Return up to *max_lines* non-empty lines from *text*."""
        if not text:
            return []
        try:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return lines[:max_lines]
        except Exception:
            return []

    def _get_with_retry(self, url, params, timeout=10, retries=2, delay=3):
        """GET with a couple of short retries, so a single transient network
        blip doesn't silently drop weather for a whole refresh cycle."""
        last_exc = None
        for attempt in range(1, retries + 2):
            try:
                response = requests.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt <= retries:
                    logger.warning(f"Request to {url} failed (attempt {attempt}), retrying: {exc}")
                    time.sleep(delay)
        raise last_exc

    def fetch_weather(self, latitude, longitude, timezone):
        """Fetch weather forecast from Open Meteo API.
        
        Args:
            latitude: Location latitude (e.g., "-33.87" for Sydney)
            longitude: Location longitude (e.g., "151.21" for Sydney)
            timezone: Timezone string (e.g., "Australia/Sydney")
            
        Returns:
            Dictionary with weather data or None if fetch fails
        """
        try:
            # Open Meteo Forecast API endpoint (uses multiple weather models)
            url = "https://api.open-meteo.com/v1/forecast"
            
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,weather_code",
                "hourly": "precipitation_probability",
                "timezone": timezone,
                "forecast_days": 1
            }
            
            logger.info(f"Fetching weather from Open Meteo for lat={latitude}, lon={longitude}")
            response = self._get_with_retry(url, params)
            data = response.json()
            
            # Extract current observations (actual measured data)
            current = data.get("current", {})
            temperature = current.get("temperature_2m")
            humidity = current.get("relative_humidity_2m")
            weather_code = current.get("weather_code")
            
            # Get rain probability from hourly forecast (current hour)
            hourly = data.get("hourly", {})
            hourly_times = hourly.get("time", [])
            
            # Get current time in the specified timezone
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            current_hour_str = now.strftime("%Y-%m-%dT%H:00")
            
            rain_chance = None
            try:
                hour_index = hourly_times.index(current_hour_str)
                rain_chance = hourly.get("precipitation_probability", [None])[hour_index]
            except (ValueError, IndexError):
                logger.warning(f"Could not get rain probability for {current_hour_str}")
            
            # Get weather description and icon from WMO code
            description, icon_filename = self._get_weather_from_code(weather_code)
            
            # Build absolute path to icon file
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(plugin_dir, "render", "icons", icon_filename)
            
            # Determine temperature colour class
            temp_colour = self._get_temp_colour(temperature)
            
            logger.info(f"Successfully fetched weather: {temperature}°C (current) - {description}")
            logger.info(f"Weather icon path: {icon_path}")
            
            return {
                "type": "current",
                "temperature": temperature,
                "temp_colour": temp_colour,
                "description": description,
                "icon": icon_path,
                "rain_chance": rain_chance,
                "humidity": humidity,
            }
            
        except requests.exceptions.RequestException as exc:
            logger.error(f"Failed to fetch weather from Open Meteo: {exc}")
            return None
        except (KeyError, ValueError, IndexError) as exc:
            logger.error(f"Failed to parse weather data: {exc}")
            return None
    
    def fetch_daily_forecast(self, latitude, longitude, timezone):
        """Fetch today's daily forecast (min/max temperature) from Open Meteo.

        Args:
            latitude: Location latitude (e.g., "-33.87" for Sydney)
            longitude: Location longitude (e.g., "151.21" for Sydney)
            timezone: Timezone string (e.g., "Australia/Sydney")

        Returns:
            Dictionary with forecast data or None if fetch fails
        """
        try:
            url = "https://api.open-meteo.com/v1/forecast"

            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": timezone,
                "forecast_days": 1
            }

            logger.info(f"Fetching daily forecast from Open Meteo for lat={latitude}, lon={longitude}")
            response = self._get_with_retry(url, params)
            data = response.json()

            daily = data.get("daily", {})
            temp_max = daily.get("temperature_2m_max", [None])[0]
            temp_min = daily.get("temperature_2m_min", [None])[0]
            rain_chance = daily.get("precipitation_probability_max", [None])[0]

            # Current observed temperature and weather code (for the "Currently" tile)
            current = data.get("current", {})
            current_temp = current.get("temperature_2m")
            weather_code = current.get("weather_code")

            # Round temperatures to whole integers for display
            temp_max_int = round(temp_max) if temp_max is not None else None
            temp_min_int = round(temp_min) if temp_min is not None else None
            current_temp_int = round(current_temp) if current_temp is not None else None

            # Get weather description and icon from WMO code
            description, icon_filename = self._get_weather_from_code(weather_code)

            # Build absolute path to icon file
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(plugin_dir, "render", "icons", icon_filename)

            # Determine temperature colour class for each value (max drives the container)
            temp_max_colour = self._get_temp_colour(temp_max)
            temp_min_colour = self._get_temp_colour(temp_min)
            current_temp_colour = self._get_temp_colour(current_temp)

            logger.info(
                f"Successfully fetched forecast: low {temp_min_int}° / high {temp_max_int}° - {description}"
            )
            logger.info(f"Weather icon path: {icon_path}")

            return {
                "type": "forecast",
                "temp_min": temp_min_int,
                "temp_max": temp_max_int,
                "current_temp": current_temp_int,
                "temp_min_colour": temp_min_colour,
                "temp_max_colour": temp_max_colour,
                "current_temp_colour": current_temp_colour,
                "temp_colour": temp_max_colour,
                "description": description,
                "icon": icon_path,
                "rain_chance": rain_chance,
            }

        except requests.exceptions.RequestException as exc:
            logger.error(f"Failed to fetch forecast from Open Meteo: {exc}")
            return None
        except (KeyError, ValueError, IndexError) as exc:
            logger.error(f"Failed to parse forecast data: {exc}")
            return None
    
    def _get_weather_from_code(self, code):
        """Map WMO weather code to description and SVG icon filename.
        
        WMO Weather interpretation codes (WW):
        https://open-meteo.com/en/docs
        
        Returns:
            Tuple of (description, icon_filename)
        """
        if code is None:
            return ("Unknown", "unknown.svg")
        
        # WMO code mapping to SVG icons
        # Icons should be placed in whats_on_today/render/icons/
        code_map = {
            0: ("Clear sky", "clear-day.svg"),
            1: ("Mainly clear", "mostly-clear-day.svg"),
            2: ("Partly cloudy", "partly-cloudy-day.svg"),
            3: ("Overcast", "cloudy.svg"),
            45: ("Foggy", "fog.svg"),
            48: ("Fog", "fog.svg"),
            51: ("Light drizzle", "drizzle.svg"),
            53: ("Moderate drizzle", "moderate-drizzle.svg"),
            55: ("Dense drizzle", "rain.svg"),
            56: ("Freezing drizzle", "sleet.svg"),
            57: ("Freezing drizzle", "sleet.svg"),
            61: ("Slight rain", "rain.svg"),
            63: ("Moderate rain", "rain.svg"),
            65: ("Heavy rain", "heavy-rain.svg"),
            66: ("Freezing rain", "sleet.svg"),
            67: ("Freezing rain", "sleet.svg"),
            71: ("Slight snow", "snow.svg"),
            73: ("Moderate snow", "snow.svg"),
            75: ("Heavy snow", "heavy-snow.svg"),
            77: ("Snow grains", "snow.svg"),
            80: ("Slight showers", "showers.svg"),
            81: ("Moderate showers", "rain.svg"),
            82: ("Violent showers", "heavy-rain.svg"),
            85: ("Slight snow showers", "snow.svg"),
            86: ("Heavy snow showers", "heavy-snow.svg"),
            95: ("Thunderstorm", "thunderstorm.svg"),
            96: ("Thunderstorm + hail", "thunderstorm.svg"),
            99: ("Thunderstorm + hail", "thunderstorm.svg"),
        }
        
        return code_map.get(code, ("Unknown", "unknown.svg"))
    
    def _get_temp_colour(self, temp):
        """Determine colour class based on temperature.
        
        Args:
            temp: Temperature in Celsius
            
        Returns:
            Colour class name: 'temp-cold', 'temp-mild', 'temp-warm', or 'temp-hot'
        """
        if temp is None:
            return "temp-mild"
        
        if temp < 18:
            return "temp-cold"  # Blue
        elif temp <= 24:
            return "temp-mild"  # Green
        elif temp <= 28:
            return "temp-warm"  # Orange
        else:
            return "temp-hot"   # Red
