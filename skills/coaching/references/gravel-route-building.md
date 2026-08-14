# Gravel Route Building for Cycling Training Plans

When an athlete asks for routes from their home address, with a preference for
gravel/unpaved roads, use this workflow.

## Workflow

1. **Geocode the athlete's home address** using the maps skill:
   ```bash
   MAPS=/opt/data/skills/productivity/maps/scripts/maps_client.py
   python3 $MAPS search "Address, City, Sweden"
   ```

2. **Look at the athlete's recent activity names** — they reveal local
   landmarks and commonly ridden roads. Use `get_recent_activities(days=90)` and
   scan the `name` field for place names.

3. **Geocode key local landmarks** found in activity names to build a distance
   matrix:
   ```bash
   python3 $MAPS search "Landmark, Sweden"
   ```

4. **Compute cycling distances** between home and each landmark:
   ```bash
   python3 $MAPS distance "lat,lon" --to "Landmark" --mode cycling
   ```

5. **Get turn-by-turn directions** for the main corridors:
   ```bash
   python3 $MAPS directions "home_coords" --to "Landmark" --mode cycling
   ```
   Parse the `steps` array for road names. The OSRM cycling profile includes
   paved and unpaved roads — it doesn't distinguish surface type, but in rural
   Sweden many minor roads are gravel.

6. **Build routes** by chaining landmarks into loops. Target distance = duration
   × estimated gravel speed. For Z2 gravel riding, estimate 22–26 km/h.

7. **For gravel-specific surface data**, query Overpass API:
   ```bash
   curl -s 'https://overpass-api.de/api/interpreter' \
     --data-urlencode 'data=[out:json];way(BBOX)[highway][surface~"gravel|unpaved|dirt|compacted"];out geom;'
   ```
   Replace BBOX with south,west,north,east coordinates. Note: Swedish rural
   roads often lack `surface` tags in OSM — empty results are common even in
   gravel-rich areas. Fall back to local knowledge from activity names.

## Route presentation

Present routes as:
- **Name** (memorable, uses local landmarks)
- **Distance estimate** (from OSRM cycling distances)
- **Turn-by-turn summary** using road names from OSRM directions
- **Character notes**: gravel quality, elevation, shade, water stops
- **Pulse/effort target** per the training plan

## Yngsjö / Österlen gravel network (reference)

Home: Frisebodavägen, Yngsjö (~55.88, 14.23)

| Segment | Cycling dist | Character |
|---------|-------------|-----------|
| Yngsjö → Furuboda/Nyehusen | 5 km | Coastal gravel, pine forest |
| Yngsjö → Åhus | 6.5 km | Mixed surface |
| Yngsjö → Degeberga | 15 km | Farm gravel |
| Yngsjö → Maglehem | 16 km | Classic gravel roads |
| Yngsjö → Brösarp | 20 km | Brösarps backar, gravel paradise |
| Yngsjö → Kivik | 31 km | Coast + rolling hills |
| Furuboda → Maglehem | 14 km | Inland gravel |
| Maglehem → Brösarp | 5 km | Brösarps backar |
| Brösarp → Degeberga | 14 km | Farm gravel |

Classic loop (~53 km): Yngsjö → Furuboda → Maglehem → Brösarp → Degeberga → home
