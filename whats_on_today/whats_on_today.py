import logging
import requests
import icalendar
import recurring_ical_events
import pytz
from datetime import datetime, date, timedelta
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class WhatsOnToday(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        calendar_url = settings.get("calendarURL", "").strip()
        if not calendar_url:
            raise RuntimeError("A calendar URL is required.")

        # Always use landscape dimensions
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            # Swap to landscape
            dimensions = dimensions[::-1]

        timezone = device_config.get_config("timezone", default="America/New_York")
        time_format = device_config.get_config("time_format", default="12h")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        today = now.date()

        events = self.fetch_todays_events(calendar_url, tz, today, time_format, now)

        # Fetch weather data if no events
        weather = None
        if not events:
            latitude = settings.get("weatherLatitude", "").strip()
            longitude = settings.get("weatherLongitude", "").strip()
            if latitude and longitude:
                weather = self.fetch_weather(latitude, longitude, timezone)

        day_name = now.strftime("%A")
        long_date = now.strftime("%-d %B %Y")

        template_params = {
            "day_name": day_name,
            "long_date": long_date,
            "events": events,
            "weather": weather,
            "time_format": time_format,
            "plugin_settings": settings,
        }

        image = self.render_image(
            dimensions, "whats_on_today.html", "whats_on_today.css", template_params
        )
        if not image:
            raise RuntimeError("Failed to render calendar image, please check logs.")
        return image

    def fetch_todays_events(self, calendar_url, tz, today, time_format="12h", now=None):
        """Fetch and return events occurring on *today* from the given ICS URL."""
        if now is None:
            now = datetime.now(tz)
        # Support webcal:// scheme
        if calendar_url.startswith("webcal://"):
            calendar_url = calendar_url.replace("webcal://", "https://")

        try:
            response = requests.get(calendar_url, timeout=30)
            response.raise_for_status()
            cal = icalendar.Calendar.from_ical(response.text)
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch calendar: {exc}") from exc

        start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)
        end_of_day = start_of_day + timedelta(days=1)

        raw_events = recurring_ical_events.of(cal).between(start_of_day, end_of_day)

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
        
        # Limit to next 3 events
        return events[:3]

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
                "current": "temperature_2m,apparent_temperature,precipitation,weather_code,relative_humidity_2m,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": timezone,
                "forecast_days": 1
            }
            
            logger.info(f"Fetching weather from Open Meteo for lat={latitude}, lon={longitude}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract current weather
            current = data.get("current", {})
            daily = data.get("daily", {})
            
            temp_current = current.get("temperature_2m")
            apparent_temp = current.get("apparent_temperature")
            weather_code = current.get("weather_code")
            humidity = current.get("relative_humidity_2m")
            wind_speed = current.get("wind_speed_10m")
            
            # Extract daily forecast
            temp_max = daily.get("temperature_2m_max", [None])[0]
            temp_min = daily.get("temperature_2m_min", [None])[0]
            rain_chance = daily.get("precipitation_probability_max", [None])[0]
            daily_weather_code = daily.get("weather_code", [None])[0]
            
            # Use daily weather code if available, otherwise current
            primary_code = daily_weather_code if daily_weather_code is not None else weather_code
            
            # Get weather description and icon from WMO code
            description, icon = self._get_weather_from_code(primary_code)
            
            logger.info(f"Successfully fetched weather: {temp_max}°C (max) - {description}")
            
            return {
                "type": "forecast",
                "temperature": temp_current,
                "apparent_temp": apparent_temp,
                "min_temp": temp_min,
                "max_temp": temp_max,
                "description": description,
                "icon": icon,
                "rain_chance": rain_chance,
                "humidity": humidity,
                "wind_speed": wind_speed,
            }
            
        except requests.exceptions.RequestException as exc:
            logger.error(f"Failed to fetch weather from Open Meteo: {exc}")
            return None
        except (KeyError, ValueError, IndexError) as exc:
            logger.error(f"Failed to parse weather data: {exc}")
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
            53: ("Moderate drizzle", "drizzle.svg"),
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
            96: ("Thunderstorm with hail", "thunderstorm.svg"),
            99: ("Thunderstorm with hail", "thunderstorm.svg"),
        }
        
        return code_map.get(code, ("Unknown", "unknown.svg"))
