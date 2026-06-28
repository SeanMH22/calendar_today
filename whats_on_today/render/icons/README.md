# Weather Icons

Place your SVG weather icons in this directory. The plugin will load them based on WMO weather codes.

## Required Icons

### Core Weather Conditions
- **clear-day.svg** - Clear sky (WMO code 0)
- **mostly-clear-day.svg** - Mainly clear (WMO code 1)
- **partly-cloudy-day.svg** - Partly cloudy (WMO code 2)
- **cloudy.svg** - Overcast (WMO code 3)
- **fog.svg** - Fog/Foggy (WMO codes 45, 48)

### Rain
- **drizzle.svg** - Light/moderate drizzle (WMO codes 51, 53)
- **rain.svg** - Rain, dense drizzle, moderate showers (WMO codes 55, 61, 63, 81)
- **heavy-rain.svg** - Heavy rain, violent showers (WMO codes 65, 82)
- **showers.svg** - Slight showers (WMO code 80)
- **sleet.svg** - Freezing drizzle/rain (WMO codes 56, 57, 66, 67)

### Snow
- **snow.svg** - Snow, slight/moderate snow, snow grains (WMO codes 71, 73, 77, 85)
- **heavy-snow.svg** - Heavy snow (WMO codes 75, 86)

### Severe Weather
- **thunderstorm.svg** - Thunderstorm (WMO codes 95, 96, 99)

### Fallback
- **unknown.svg** - Unknown/error state

## Icon Specifications

- **Format**: SVG (vector graphics)
- **Dimensions**: Square aspect ratio recommended (e.g., 100×100, 200×200)
- **Display size**: Icons will be displayed at `min(35dvw, 25dvh)` (viewport-relative)
- **Colors**: Designed for e-paper display (black/white/grayscale)
- **Simplicity**: Keep designs simple and high-contrast for e-paper clarity

## Testing

After adding icons, test with different weather codes:
- Lucas Heights coordinates: latitude="-34.05", longitude="150.98"
- Configure in plugin settings
- Weather will display when no calendar events are scheduled
