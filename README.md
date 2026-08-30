# What's on Today

Custom plugin for [InkyPi](https://github.com/fatihak/InkyPi) — an e-ink display project for Raspberry Pi. This was inspired by RobinWts [InkyPi-Plugin-seniorDashboard_allDay](https://github.com/RobinWts/InkyPi-Plugin-seniorDashboard_allDay#inkypi-plugin-seniordashboard_allday), we have a family member who gets a bit confused so I wanted something obvious and specific to the current day only, with no need to see past events or a long list of events and descriptions. 

It's very basic and not likely to have any features added by me. It's here to use as-is or make your own version.

## Plugin

### `whats_on_today` — What's On Today

Displays today's schedule and weather at a glance. The layout automatically follows
your device's configured **landscape or portrait** orientation — no plugin setting
needed, it just adapts.

**In portrait**, or in landscape when only one of events/weather is available, the
display is divided into three vertically stacked bands:

- **Top (25%)** — Header: day name + long date
- **Middle (50%)** — Today's events (up to two)
- **Bottom (25%)** — Weather

When there are **no upcoming events** for the day, weather expands to fill the middle
and bottom bands (75%).

**In landscape, when both events and weather are available**, the layout instead
splits into two columns below the header: weather fills a full-height column on the
left, and today's events fill the remaining column on the right — rather than
squeezing weather into a small strip.

If the plugin can't reach the internet (calendar or weather fetch fails), an orange
warning tile replaces the normal content instead of the display silently going stale
— the header still shows the correct day and date, computed locally with no network
needed.

#### Header

- **Day name** rendered as a large H1 heading (e.g. *Sunday*), coloured blue on
  weekdays and green at weekends
- **Long date** — in landscape, sits beside the day name on the same line in an
  abbreviated format (e.g. *5 Sep 2026*) so it fits at a large, readable size; in
  portrait, where there's less width but more height to spare, it stacks below the
  day name in full format (e.g. *5 September 2026*)

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
   temperatures shown as whole integers, with a square **Currently** tile showing
   the current observed temperature.

   - **With events present, in portrait** (bottom 25%): weather icon, Low/High and
     the Currently tile are displayed compactly side by side. The tile is
     right-justified and square.
   - **With events present, in landscape**: weather fills its own full-height left
     column instead of a compact strip — icon and Currently tile on top, Low/High,
     description and rain chance below, all sized to use the column's height. Events
     fill the right column, starting from the top.
   - **No upcoming events** (middle + bottom, 75%, either orientation): the icon and
     Currently tile share a top row; Low/High, the condition description and rain
     chance fill the full width below. The tile's background colour follows the
     temperature band.

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
    "version": "2.5.0"
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

<img width="493" height="812" alt="image" src="https://github.com/user-attachments/assets/a19661e2-d303-42cb-a379-8f1f1bf4118b" />

<img width="485" height="805" alt="image" src="https://github.com/user-attachments/assets/9ebcef05-06a8-4d48-bc9b-44398b21b285" />
