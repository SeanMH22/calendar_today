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

        day_name = now.strftime("%A")
        long_date = now.strftime("%-d %B %Y")
        current_time = self._format_time(now, time_format)

        template_params = {
            "day_name": day_name,
            "long_date": long_date,
            "current_time": current_time,
            "events": events,
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
                })
            except Exception as exc:
                logger.warning(f"Skipping malformed event: {exc}")
                continue

        # Sort chronologically: all-day events first, then by start time
        events.sort(key=lambda e: (e["start"] != "All day", e["start"]))
        return events

    def _calculate_urgency(self, dtstart, now, tz):
        """Calculate urgency level based on time until event.
        Returns: 'imminent' (red), 'soon' (orange), 'allday' (blue), or 'normal' (black)
        """
        if not dtstart or not isinstance(dtstart, datetime):
            return "allday"  # All-day events in blue
        
        time_until_minutes = (dtstart.astimezone(tz) - now).total_seconds() / 60
        
        if 0 <= time_until_minutes <= 15:
            return "imminent"  # Red - starts within 15 minutes
        elif 15 < time_until_minutes <= 30:
            return "soon"  # Orange - starts within 30 minutes
        else:
            return "normal"  # Black - regular event

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
