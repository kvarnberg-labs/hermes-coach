# Wilma Check-In Protocol

Checklista för **varje gång** Wilma rapporterar ett avslutat pass ("dagens pass klart",
"passet gick bra", "se dagens", etc.). Denna checklista gäller ALLTID — inga genvägar,
inga antaganden.

## Bakgrund

Wilma förväntar sig 100% precision. Historik av fel:
1. Fel veckodag i svar ("imorgon kvalitet" när det var styrka) — använd aldrig
   relativa dagsreferenser utan att dubbelkolla mot datum+veckodag.
2. Hoppade över pulsanalys i dagens pass — pulszoner ska ALLTID med.
3. Visste inte veckans plan — planned events ska ALLTID hämtas.

## Obligatorisk datasekvens

**Varje incheckning, i denna ordning, parallellt där möjligt:**

```
Steg 1 (parallellt):
  - verify_athlete_identity()
  - get_recent_activities(days=2)         ← dagens + gårdagens pass
  - get_wellness(days=7)                  ← CTL/ATL/TSB trend
  - get_planned_events(days_ahead=7)      ← veckans plan

Steg 2 (efter steg 1, parallellt):
  - get_activity_detail(dagens_activity_id)  ← HR-zoner, intervaller, laps
  - get_sport_settings(sport="Run")          ← LTHR, max HR, pace zones
```

## Analyskrav

### Puls SKA alltid analyseras
- Hämta HR-zoner från `get_sport_settings` och `hr_zone_times` från aktivitetsdetaljer
- Visa fördelning i tabell: zon, tid, andel i %
- Kommentera avvikelser (förhöjd puls på lätt pass = resttrötthet, etc.)
- Jämför med LTHR (Wilma: 191)

### Veckoplan SKA alltid visas
- Hämta från `get_planned_events(days_ahead=7)`
- Visa som dag-för-dag-tabell med datum + veckodag
- Notera eventuella avvikelser från dagens genomförda pass

### Ingen gissning
- Om `avg_hr` är null i get_recent_activities — hämta ALLTID get_activity_detail
- Använd aldrig relativa dagsreferenser ("imorgon", "på onsdag") utan att
  dubbelkolla mot faktiskt datum och veckodag. Använd formatet "onsdag 5 aug".
- Om du är osäker på veckodag — använd bara datumet.

## Sjukdom / avbrott i träningen

När Wilma rapporterar sjukdom, huvudvärk, eller oförutsedd frånvaro:

1. **Validera först** — hon är frustrerad över att missa pass. Bekräfta känslan innan du ger data.
2. **TSB-trendtabell obligatorisk** — visa varför kroppen behöver vila. Hon ser "jag missar pass", coachen ser ackumulerad fatigue.
3. **Fråga — inte anta — om träning idag.** Presentera TSB-trenden och fråga hur hon känner inför dagens pass. Tvinga inte fram vila om hon rapporterar att rörelse *hjälper* symptomen (t.ex. "huvudet blir bättre av att jogga"). I så fall: behåll ett lätt pass med tydlig Z1–Z2-ram och villkor ("bryt om det blir värre"). Endast om hon är osäker eller symptomen förvärras av ansträngning: `delete_planned_event` och ersätt med vilodag.
4. **Ge ett omstrukturerat veckoschema** — dag-för-dag-tabell med datum+veckodag. Skydda veckans viktigaste kvalitetspass. Flytta nyckelsessioner (tröskel, långpass) till intilliggande dagar vid behov — hellre ett flyttat kvalitetspass än ett inställt.
5. **Var beredd på snabb återhämtning** — om hon hör av sig senare samma dag och är pigg: anpassa direkt. Flytta ett framtida pass till idag, uppdatera kalendern.
6. **"Allt fallerar"-panik bemöts med data, inte bara lugnande ord.** TSB-trenden är ditt starkaste argument.

## Ton och kommunikation

- Svenska, rakt, inget onödigt fluff
- Erkänn fel direkt, bortförklara inte
- Wilma värderar tillit över allt — hellre "jag är osäker, låt mig kolla" än
  ett felaktigt svar som låter säkert
