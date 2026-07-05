# InkyPiProjects

Custom plugins for [InkyPi](https://github.com/fatihak/InkyPi) — an e-ink display project for Raspberry Pi.

## Plugins

### `whats_on_today` — What's On Today

Displays today's schedule and weather at a glance in **landscape orientation**.

The display is divided into three horizontal bands:

- **Top (25%)** — Header: day name + long date
- **Middle (50%)** — Today's events (up to two)
- **Bottom (25%)** — Weather

When there are **no more upcoming events** for the day, the weather expands to fill
the middle and bottom bands (75%).

#### Header

- **Day name** rendered as a large H1 heading (e.g. *Sunday*), coloured blue on
  weekdays and green at weekends
- **Long date** subtitle in *day month year* format (e.g. *5 July 2026*)

#### Events

Today's events are read from any iCal / `.ics` feed, with intelligent filtering:

- Shows up to **2 upcoming events** in chronological order (early to late)
- **Filters out finished events** automatically
- In-progress events are only displayed during their **first 15 minutes**
- Each event displays:
  - Event title (large text, truncated with ellipsis if longer than 2 lines)
  - Start time – end time (or "All day")
  - First two lines of any notes / description
- **Colour-coded urgency indicators:**
  - 🔴 **Red** — In-progress / imminent events (starting now or overdue)
  - 🟠 **Orange** — Events starting within 15 minutes
  - 🟡 **Yellow** — Regular upcoming events
  - 🌸 **Pink** — All-day events

#### Weather

Weather is fetched from the free [Open-Meteo](https://open-meteo.com/) API (no API
key required) whenever latitude and longitude are configured. Two display modes are
available:

1. **Current observations** — the temperature right now, with a condition icon,
   description, humidity and rain chance.
2. **Daily forecast (Low / High)** — today's forecast **Low** and **High**
   temperatures shown as whole integers, plus a square **Currently** tile showing the
   current temperature. The tile's background follows the temperature colour band.

Temperature colouring (applied to each value):

- 🔵 **Blue** — Cold (< 18 °C)
- 🟢 **Green** — Mild (18–24 °C)
- 🟠 **Orange** — Warm (25–28 °C)
- 🔴 **Red** — Hot (> 28 °C)

#### Installation

Copy the `whats_on_today` directory into the `src/plugins/` folder of your InkyPi
installation, then add the following entry to your InkyPi plugin configuration:

```json
{
    "display_name": "What's On Today",
    "id": "whats_on_today",
    "class": "WhatsOnToday",
    "version": "2.4.0"
}
```

> New to InkyPi or setting this up at a care facility (or any network you don't
> administer)? See the step-by-step **[Setup Guide](SETUP.md)**.

#### Configuration

| Setting | Description |
|---|---|
| **Calendar URL** | Full URL to an iCal feed (`.ics`). Google Calendar, Apple Calendar, and any standard iCal source are supported. `webcal://` URLs are automatically converted to `https://`. |
| **Weather Latitude** *(optional)* | Your location's latitude, e.g. `-33.87` (Sydney). |
| **Weather Longitude** *(optional)* | Your location's longitude, e.g. `151.21` (Sydney). |
| **Weather Display Mode** | `Current observations` (the weather now) or `Daily forecast (Low / High)` (today's forecast with a Currently tile). |

The device timezone and time format (12 h / 24 h) are inherited from the InkyPi
device settings.

#### Recommended Refresh Rate

For optimal display behaviour, configure InkyPi to refresh every **15 minutes**:

- Events appear as they start
- In-progress events automatically disappear after 15 minutes
- Finished events are filtered out on the next refresh
- Minimal impact on e-ink display lifespan (~35,000 refreshes/year = 28+ years at 1M refresh rating)

#### Dependencies

The plugin relies on libraries already used by the InkyPi calendar plugin:

- `icalendar`
- `recurring-ical-events`
- `requests`
- `pytz`