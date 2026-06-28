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
            bom_url = settings.get("bomUrl", "").strip()
            if bom_url:
                weather = self.fetch_bom_weather(bom_url)

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

    def fetch_bom_weather(self, bom_url):
        """Fetch current weather from Australian Bureau of Meteorology.
        
        Args:
            bom_url: Full URL to BOM observation JSON
                    Example: 'https://www.bom.gov.au/fwo/IDN60801/IDN60801.95757.json'
                    Find your URL at http://www.bom.gov.au/nsw/observations/map.shtml
            
        Returns:
            Dictionary with weather data or None if fetch fails
        """
        try:
            url = bom_url.strip()
            
            # BOM requires a User-Agent header to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; InkyPi Calendar Display)'
            }
            
            logger.info(f"Fetching BOM weather from: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract observation data
            observations = data.get("observations", {}).get("data", [])
            if not observations:
                logger.warning("No observation data found in BOM response")
                return None
            
            # Get the most recent observation
            obs = observations[0]
            
            # Extract relevant fields
            temp = obs.get("air_temp")
            apparent_temp = obs.get("apparent_t")
            weather_desc = obs.get("weather", "")
            humidity = obs.get("rel_hum")
            wind_speed_kmh = obs.get("wind_spd_kmh")
            wind_dir = obs.get("wind_dir", "")
            
            # Get location name from header
            location = data.get("observations", {}).get("header", [{}])[0].get("name", "Unknown")
            
            # Clean up weather description - BOM uses "-" for "not reported"
            if weather_desc and weather_desc != "-":
                weather_desc = weather_desc.strip()
            else:
                weather_desc = None
            
            logger.info(f"Successfully fetched weather for {location}: {temp}°C")
            
            return {
                "temperature": temp,
                "apparent_temp": apparent_temp,
                "description": weather_desc,
                "humidity": humidity,
                "wind_speed": wind_speed_kmh,
                "wind_direction": wind_dir,
                "location": location,
            }
            
        except requests.exceptions.HTTPError as exc:
            logger.error(f"BOM HTTP error: {exc}. Check that the URL is correct.")
            return None
        except requests.exceptions.RequestException as exc:
            logger.error(f"Failed to fetch BOM weather: {exc}")
            return None
        except (KeyError, ValueError, IndexError) as exc:
            logger.error(f"Failed to parse BOM weather data: {exc}")
            return None
