# Routine Calendar

A Home Assistant custom integration that tracks recurring routines (watering
plants, cleaning the filter, …) in a shared calendar.

Multiple calendar instances are supported — add one per person or household area.

For every routine you configure:

- a name (e.g. `Water the plants`)
- an optional icon (e.g. `mdi:flower`)
- a first due date
- a recurrence (e.g. every `1 week`)

…the integration provides:

- one entry on the calendar entity for the next due date (read-only — manual
  event creation is disabled)
- a **date entity** per routine that shows the **last completion date**
  (editable to fix a forgotten completion)
- a **sensor entity** per routine showing **days until due** as an integer
  (`0` = today, `1` = tomorrow, `-1` = overdue by 1 day)
- a service `routine_calendar.complete` to tick the routine off

## How completion works

When a routine is completed the next due date is recomputed as
`last_completed + interval` — independent of the previous due date.
So if a weekly chore is due Saturday but ticked off on Sunday, the next
occurrence is the following Sunday.

The same recomputation happens when the date entity is edited directly in the
UI, so you can fix a forgotten completion after the fact.

## Entity IDs

For a calendar named **Household** and a routine named **Filter clean**:

| Entity | ID |
|---|---|
| Calendar | `calendar.household` |
| Last completed | `date.filter_clean_last_completed` |
| Days until due | `sensor.filter_clean_days_until_due` |

Use the sensor in a template or Lovelace card to build labels like "Today",
"Tomorrow", "In 2 days", or "Overdue by 3 days".

## Installation

### HACS (recommended)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Big-Gremlin&repository=ha-routine-calendar&category=integration)

1. HACS → Integrations → ⋮ → *Custom repositories*
2. Add the repository URL, category *Integration*
3. Install *Routine Calendar* and restart Home Assistant

### Manual

Copy `custom_components/routine_calendar` into the `config/custom_components/`
folder of your Home Assistant instance and restart HA.

## Configuration

Add **Routine Calendar** via *Settings → Devices & Services → Add integration*.
Enter a name for the calendar (e.g. `Household` or `Max`). You can add multiple
instances — one per person or area.

Then open the integration's options to manage routines:

- **Add routine** — name, first due date, interval, optional icon
- **Edit routine** — change any field including the icon
- **Remove routine** — deletes the routine and its entities

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This project uses the MIT License, for more details see the [license document](LICENSE).

---

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/biggremlin)
