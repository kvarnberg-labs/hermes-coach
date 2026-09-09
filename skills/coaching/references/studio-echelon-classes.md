# Studio Echelon — Indoor Cycling Classes

Reference for coaching athletes who are members of Studio l'Echelon
cycling studio (Nybrogatan 74, Östermalm, Stockholm).

## When to Use

- Athlete is a Studio Echelon member and asks about indoor training options
- Planning winter training when athlete is in Stockholm on weekdays
- Recommending a structured class that aligns with a training goal
- Athlete mentions bad weather and needs an indoor alternative

## Class Types

| Class | Duration | Training Zone | Best For |
|-------|----------|---------------|----------|
| Thin Red Line (Lactate Threshold Training) | 60 min | Threshold / Z4 | Threshold development, sweet spot substitute |
| Coffee with a dash of lactate (VO2max) | 45 min | VO2max / Z5+ | VO2max stimulus, short and sharp |
| Cadence Swings (Cadence variations, high and low) | 60 min | Technique | Cadence drills, neuromuscular activation |
| Own Training Endurancezone | 90 min or 3.25 h | Endurance / Z2 | Base building, long aerobic sessions |
| Tour de France - Own Training | varies | Self-paced | Event rides with TdF on big screen |
| Eget bibliotek (Own Training) | open | Varies | Sufferfest, Zwift, or custom — self-directed |

## Seasonal Schedule

- **Winter (Sep–Mar):** Full schedule, base training focus. Most classes
  available weekdays.
- **Spring (Apr–May):** Strength and race prep focus. Schedule shifts
  toward intensity.
- **Summer (Jun–Aug):** Reduced schedule. Summer hours weeks 28–31
  ("Closed for Holidays" on many slots). Limited classes.
- Synchronous with cycling season: base → strength → race.

## Class-to-Training-Goal Mapping

When prescribing a training session and the athlete is at Echelon,
match the class to the day's goal:

| Training Goal | Recommended Echelon Class |
|---------------|---------------------------|
| Threshold day | Thin Red Line 60min |
| VO2max day | Coffee with a dash of lactate 45min |
| Endurance / base day | Own Training Endurancezone 90min |
| Long endurance (weekend) | Own Training Endurancezone 3.25h |
| Recovery / technique | Cadence Swings 60min |
| Self-directed workout | Own Training (Sufferfest / Zwift library) |

## Key Details

- All classes are **watt-based** (power data shown on large screens)
- Classes are **individually adapted** — athlete trains at their own
  zones regardless of class level
- Coaches/instructors are cyclists themselves and provide individual
  guidance during class
- Echelon also offers Zwift and Sufferfest sessions in their library
- Booking: via website (studiolechelon.com) or app

## Checking the Live Schedule Online

When an athlete asks "kan du kolla Echelons pass?" or you need to see the
actual weekly schedule:

1. Navigate to `https://studiolechelon.com/schema` directly — the
   homepage "BOKA KLASS | SCHEMA" button does NOT reliably navigate
   to the schedule page.
2. The schedule page has tabs: "KLASSER INOMHUS", "KLASSER UTOMHUS",
   "PÅ DISTANS (ONLINE)". Default is indoors.
3. The page shows a weekly grid with day headers (idag, imorgon,
   lördag, etc.) and class entries containing: time, duration, class
   name, instructor, booking status, and spots available.
4. Use `browser_snapshot(full=true)` to extract the full schedule
   content — the compact snapshot truncates after ~20 entries.
5. Filter to the athlete's time windows BEFORE presenting options.
   Do NOT list all classes with ❌ markers for unavailable times —
   only show the classes that fit the athlete's schedule.
6. Note any "Closed for Holidays" or "Closed for maintenance" slots
   so you don't recommend a class that's actually cancelled.
7. If no classes match the athlete's time windows, say so clearly
   and recommend outdoor/self-directed training instead.

## Pitfalls

- **Summer schedule is limited.** During weeks 28–31 many slots show
  "Closed for Holidays." Don't recommend Echelon classes in summer
  without checking the current schedule first.
- **Athlete's time windows — filter BEFORE presenting.** Millberg can
  ride at 07:00 and 18:00+ on weekdays. When checking the live
  schedule, filter class recommendations to these windows and ONLY
  present matching options. Do NOT show all classes with ❌ markers
  for midday slots — that's noise the athlete has to scan through.
  If nothing matches, say so and recommend alternatives.
- **Class intensity must match the planned session.** Don't recommend
  a threshold class (Thin Red Line) when the plan calls for Z2
  endurance, or vice versa. Always cross-reference the day's planned
  workout type against the class type before suggesting it.
- **Echelon classes are complementary, not a replacement** for outdoor
  rides when weather is good. Use them for structured quality sessions
  (threshold, VO2max) or when weather forces indoor.

## Headless schedule check (Zoezi API — no browser needed)

The live schedule also has a plain-JSON API on the Zoezi platform that
backs both studiolechelon.com/schema and echelon.zoezi.se/schema (both
are JS apps that render nothing over plain HTTP — do not scrape them):

```
GET https://echelon.zoezi.se/api/public/workout/get/all?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
Headers: User-Agent + Accept (public endpoint, no auth)
Response: {"workouts": [...]}
```

Verified live 2026-09-09 (25 workouts returned). Field mapping:

| Field | Meaning |
|-------|---------|
| `startTime` / `endTime` | Local Stockholm time, `YYYY-MM-DD HH:MM:SS` — duration = end − start |
| `workoutType.name` | Class name (e.g. "Thin Red Line (Lactate Threshold Training) 60min"); `name` on the workout object itself is null |
| `numBooked` / `space` | Booking fill; `numQueue` exists for waitlists |
| `bookable` / `bookableForCustomer` | Whether the slot can be booked |
| `description` | HTML blob from the class type |

Use this endpoint for cron/headless sessions and quick checks; keep the
browser walkthrough above for interactive sessions. Verify classes and
class types against the live response before recommending — the schedule
rotates and evening classes fill fast.

## Class-data logging note

Coach-led classes run in resistance mode (not ERG) — watts are
self-selected and the class forces nothing. Analyze a class session as
self-selected power/capacity, not as the class "pushing" the athlete
past prescription; remind the athlete to hold their own watt target
regardless of the room. Class apps may display percentages against the
bike's locally configured FTP, which can differ from intervals.icu FTP —
class power data logs physical watts either way, so post-ride analysis
is unaffected.