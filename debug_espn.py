"""Debug soccer enrichment — why aren't soccer teams getting real data?"""
import requests, json

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
base = 'https://site.web.api.espn.com/apis/site/v2/sports'

# Try multiple soccer leagues
for league_key, league_name in [('soccer/fra.1', 'Ligue 1'), ('soccer/esp.1', 'La Liga'), ('soccer/usa.1', 'MLS'), ('soccer/tur.1', 'Turkish')]:
    print(f"\n{'='*50}")
    print(f"Testing: {league_name} ({league_key})")
    
    r = s.get(f'{base}/{league_key}/scoreboard')
    data = r.json()
    events = data.get('events', [])
    
    if not events:
        print("  No events today")
        continue
    
    ev = events[0]
    comp = ev['competitions'][0]
    team = comp['competitors'][0]
    tid = team['id']
    tname = team['team']['displayName']
    print(f"  Team: {tname} (ID: {tid})")
    
    # Test team detail
    r2 = s.get(f'{base}/{league_key}/teams/{tid}')
    td = r2.json().get('team', {})
    rec = td.get('record', {})
    items = rec.get('items', [])
    print(f"  Record items: {len(items)}")
    for item in items:
        stats_dict = {}
        for st in item.get('stats', []):
            stats_dict[st['name']] = st['value']
        itype = item.get('type', '?')
        summary = item.get('summary', '?')
        avg_for = stats_dict.get('avgPointsFor', 'N/A')
        avg_against = stats_dict.get('avgPointsAgainst', 'N/A')
        win_pct = stats_dict.get('winPercent', 'N/A')
        print(f"    {itype}: {summary} | avgFor={avg_for} | avgAgainst={avg_against} | winPct={win_pct}")
    
    # Test schedule for game scores
    r3 = s.get(f'{base}/{league_key}/teams/{tid}/schedule')
    sched = r3.json()
    sched_events = sched.get('events', [])
    print(f"  Schedule events: {len(sched_events)}")
    
    # Look at last 3 completed games
    count = 0
    for ev2 in reversed(sched_events):
        if count >= 3:
            break
        comps = ev2.get('competitions', [])
        if not comps:
            continue
        c = comps[0]
        state = c.get('status', {}).get('type', {}).get('state', '?')
        if state != 'post':
            continue
        count += 1
        competitors = c.get('competitors', [])
        parts = []
        for cc in competitors:
            score = cc.get('score', 'MISSING')
            name = cc.get('team', {}).get('abbreviation', '?')
            parts.append(f"{name}:{score}(type={type(score).__name__})")
        print(f"    Game: {' vs '.join(parts)}")

print("\nDone!")
