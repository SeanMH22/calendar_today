# InkyPiProjects

Custom plugins for [InkyPi](https://github.com/fatihak/InkyPi) — an e-ink display project for Raspberry Pi.

## Plugins

### `calendar_today` — Today's Calendar

Displays today's schedule at a glance in **landscape orientation**:

- **Day name** rendered as a large H1 heading (e.g. *Saturday*)
- **Long date** subtitle in *day month year* format (e.g. *21 June 2026*)
- **Today's events** from any iCal / `.ics` feed, each showing:
  - Event title (large text)
  - Start time – end time (or "All day")
  - First two lines of any notes / description

#### Installation

Copy the `src/plugins/calendar_today` directory into the `src/plugins/` folder of your InkyPi installation, then add the following entry to your InkyPi plugin configuration:

```json
{
    "display_name": "Today's Calendar",
    "id": "calendar_today",
    "class": "CalendarToday"
}
```

#### Configuration

| Setting | Description |
|---|---|
| **Calendar URL** | Full URL to an iCal feed (`.ics`). Google Calendar, Apple Calendar, and any standard iCal source are supported. `webcal://` URLs are automatically converted to `https://`. |

The device timezone and time format (12 h / 24 h) are inherited from the InkyPi device settings.

#### Dependencies

The plugin relies on libraries already used by the InkyPi calendar plugin:

- `icalendar`
- `recurring-ical-events`
- `requests`
- `pytz`