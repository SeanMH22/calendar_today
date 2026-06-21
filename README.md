# InkyPiProjects

Custom plugins for [InkyPi](https://github.com/fatihak/InkyPi) — an e-ink display project for Raspberry Pi.

## Plugins

### `whats_on_today` — What's On Today

Displays today's schedule at a glance in **landscape orientation**:

- **Day name** rendered as a large H1 heading (e.g. *Saturday*)
- **Long date** subtitle in *day month year* format (e.g. *21 June 2026*)
- **Today's events** from any iCal / `.ics` feed, with intelligent filtering:
  - Shows up to **3 upcoming events** in chronological order (early to late)
  - **Filters out finished events** automatically
  - In-progress events only displayed during the **first 15 minutes**
  - Each event displays:
    - Event title (large text, truncated with ellipsis if longer than 2 lines)
    - Start time – end time (or "All day")
    - First two lines of any notes / description (truncated with ellipsis if too long)
  - **Color-coded urgency indicators**:
    - 🔴 **Red** — Events starting within 15 minutes (imminent)
    - 🟠 **Orange** — Events starting soon
    - 🟡 **Yellow** — Regular upcoming events
    - 🔵 **Blue** — All-day events

#### Installation

Copy the `whats_on_today` directory into the `src/plugins/` folder of your InkyPi installation, then add the following entry to your InkyPi plugin configuration:

```json
{
    "display_name": "What's On Today",
    "id": "whats_on_today",
    "class": "WhatsOnToday"
}
```

#### Configuration

| Setting | Description |
|---|---|
| **Calendar URL** | Full URL to an iCal feed (`.ics`). Google Calendar, Apple Calendar, and any standard iCal source are supported. `webcal://` URLs are automatically converted to `https://`. |

The device timezone and time format (12 h / 24 h) are inherited from the InkyPi device settings.

#### Recommended Refresh Rate

For optimal display behavior, configure InkyPi to refresh every **15 minutes**:

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