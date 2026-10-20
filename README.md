# Cricket Plus

Live, recent and upcoming cricket for [LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix):
international matches (Test / ODI / T20I) and the major domestic competitions
(Big Bash, IPL, Sheffield Shield, The Hundred, PSL, CPL, SA20, ...). Data comes
from ESPN's public cricket API (no API key).

This is ChuckBuilds' [Cricket Scoreboard](https://github.com/ChuckBuilds/ledmatrix-plugins/tree/main/plugins/cricket-scoreboard)
(1.3.3) with three changes:

- **Team logos download.** ESPN gives a team's logo as `logo`; the original
  read only `logos`, so no team ever got a logo. Failed downloads are retried
  after 30 minutes, and a logo shows as soon as it arrives, without a restart.
- **Country flags for national sides,** including A, women's and under-19
  sides, and associate nations (254 countries).
- **Small crests beside each team's score** ("[flag] AUS 391") instead of in
  the card's top corners.

It has its own plugin id (`cricket-plus`) and display modes, so it can be
installed alongside the original. Enable one or the other.

## Install

1. In the LEDMatrix web interface, open **Plugin Manager**.
2. Under **Install from GitHub**, choose **Install Single Plugin** and paste
   `https://github.com/StevenFay/ledmatrix-cricket-plus`.
3. Accept the unverified-plugin warning, then restart the display.
4. Open **Cricket Plus**, set favourite teams and competitions, and save.
   If the original Cricket Scoreboard is installed, disable it.

## Display modes

| Mode | Shows |
|------|-------|
| `cricketplus_live` | In-progress matches. Limited-overs matches show `runs/wickets (overs/max ov)`, current run rate, and — when a side is chasing — the target, runs still needed, and required run rate. Test matches show the day + session (Stumps / Lunch / Tea …) and both innings, with no clock. |
| `cricketplus_recent` | Completed matches: final scores + ESPN's result summary (e.g. `"RCB won by 5 wkts (12b rem)"`). |
| `cricketplus_upcoming` | Scheduled matches: date/time, teams, venue, and a format badge. |

Live matches take priority in the rotation when `live_priority` is on.

### Scroll or switch

`display_style` sets how each mode is shown:

- **`scroll`** (default): every match in the mode scrolls across the panel,
  right to left, as one strip of match cards, like the other sports boards.
  The strip runs once per slot and is rebuilt with the latest scores before
  it runs again.
- **`switch`**: one match at a time, each for its game duration.

`scroll_settings` tunes the ticker:

| Setting | Default | |
|---|---|---|
| `scroll_speed` | 100 | Pixels per second. Whole multiples of the panel refresh (100 on a 100Hz panel) scroll the smoothest. |
| `card_width` | 128 | Width of each match card, capped at the panel width. Vegas mode uses the same cards. |
| `gap_between_cards` | 24 | Blank pixels between cards. |

## How series discovery works

Unlike most sports, cricket has **no single stable league id** on ESPN — it is
organised as dozens of concurrent, per-tour / per-season numeric *series* ids
(e.g. a given season of the IPL might be `8048`, Major League Cricket `21266`,
the Vitality Blast `8053`). Those ids change every season.

So instead of hardcoding ids, the plugin **discovers them periodically**:

1. It reads a curated seed list, [`competitions.json`](competitions.json), that
   maps human competition keys (`ipl`, `bbl`, `the-hundred`, …) to stable
   **search terms** (competition *names* are far more stable than their ids).
2. Every `series_discovery_interval` seconds (default 24h) it queries ESPN's
   cricket header endpoint, lists every active series, and resolves them:
   - **domestic** competitions are matched by name against your
     `favorite_competitions` search terms;
   - **international** series are matched by your `favorite_teams` national-team
     names appearing in the series/event names (e.g. *"India tour of England
     2026"*).
3. Each resolved numeric id's `/scoreboard` is then fetched and parsed.

Resolved ids are cached (via the host `cache_manager`) so discovery is cheap.

## Overs math (base-6)

Cricket overs are **base-6 in the fractional part**: `18.4` overs means 18
completed overs **plus 4 balls** = `18 + 4/6 = 18.667` decimal overs, *not*
18.4. The plugin converts `overs → decimal overs` before any run-rate division:

- current run rate = `runs / decimal_overs`
- required run rate = `runs_needed / (balls_remaining / 6)`

This conversion is unit-tested (`test_cricket_plugin.py::TestOversMath`).

## Configuration

Configured under the `cricket-plus` key in `config/config.json`. See
[`config_schema.json`](config_schema.json) for the full schema; key fields:

| Key | Default | Purpose |
|-----|---------|---------|
| `enabled` | `false` | Master on/off |
| `favorite_teams` | `[]` | National teams (name or abbr, e.g. `"India"`, `"IND"`) whose international series are followed |
| `favorite_competitions` | `["international","ipl","bbl"]` | Domestic competition keys from `competitions.json` (`international` follows Test/ODI/T20I tours for your favorite teams) |
| `exclude_teams` | `[]` | Teams to always hide (spoiler protection) |
| `show_favorite_teams_only` | `false` | Restrict *international* matches to those featuring a favorite team |
| `live_game_duration` / `recent_game_duration` / `upcoming_game_duration` | 20 / 15 / 15 | Per-match on-screen seconds |
| `non_favorite_live_game_duration` | `0` | Shorter turn for live matches without a favorite (0 = same as `live_game_duration`) |
| `update_interval_seconds` / `live_update_interval` | 3600 / 30 | Data refresh cadence (the live cadence also applies once an upcoming match's start time has passed, so a match that has just started is picked up within seconds) |
| `series_discovery_interval` | `86400` | How often numeric series ids are re-resolved |
| `recent_games_to_show` / `upcoming_games_to_show` | 5 / 5 | Match counts per mode |
| `live_priority` | `true` | Live matches interrupt the normal rotation |
| `display_modes` | all on | Toggle live / recent / upcoming |
| `dynamic_duration`, `mode_durations` | off / null | Auto-size or cap each mode's total time |
| `background_service.request_timeout` | 30 | HTTP request timeout (seconds) |
| `customization` | — | Fonts + colors for score / team / status / detail text |

### Every setting

The table above groups the ones you are most likely to touch. This is the
complete list, at the exact paths the schema expects — the schema sets
`additionalProperties: false`, so a key at the wrong depth is rejected.

| Key | Default | Notes |
|---|---|---|
| `enabled` | `false` | Enable or disable the cricket scoreboard plugin. |
| `favorite_teams` | *(empty)* | Favorite national teams. Any international series (tour, World Cup, bilateral) featuring one of these teams is discovered and shown. Matches on team name appearing in the series/match name. |
| `favorite_competitions` | `["international", "ipl", "bbl"]` | Domestic competitions (keys from competitions.json) to follow. Include 'international' to follow Test/ODI/T20I tours for your favorite_teams. |
| `exclude_teams` | *(empty)* | Teams to always hide from live rotation and recent/final scores (spoiler protection). Takes precedence over favorite_teams. |
| `show_favorite_teams_only` | `false` | Only show matches involving a favorite national team. Domestic-league matches are always governed by favorite_competitions. |
| `display_duration` | `15` | Seconds a mode stays on screen when it has no matches to time by (5–60). Per-match time comes from the three durations below. |
| `live_game_duration` | `20` | Duration in seconds to display each live match before rotating to the next (10–120). |
| `non_favorite_live_game_duration` | `0` | Duration in seconds for live matches that do NOT involve a favorite team. 0 (default) = use live_game_duration for every live match (0–120). |
| `recent_game_duration` | `15` | Duration in seconds to display each recent match (5–60). |
| `upcoming_game_duration` | `15` | Duration in seconds to display each upcoming match (5–60). |
| `update_interval_seconds` | `3600` | How often to fetch new match data (seconds) (30–86400). |
| `live_update_interval` | `30` | Update interval for live matches (seconds) (10–300). |
| `series_discovery_interval` | `86400` | How often to re-resolve numeric ESPN series IDs from the header endpoint (seconds). Series IDs change per tour/season, so they are re-discovered periodically rather than hardcoded. Default 24h (3600–604800). |
| `recent_games_to_show` | `5` | Maximum number of recent (completed) matches to show (1–20). |
| `upcoming_games_to_show` | `5` | Maximum number of upcoming (scheduled) matches to show (1–20). |
| `live_priority` | `true` | Give live matches priority over other modes. Live matches interrupt normal rotation and are displayed immediately when available. |
| `show_venue` | `true` | Show the venue/ground on upcoming match cards. |
| `show_country_flags` | `true` | Show national sides (also A, women's and under-19 sides) with their country's flag. Off shows the coloured team-code badges. |
| `crest_layout` | `inline` | `inline`: a small flag or logo right before each team's code on the score line. `edges`: larger crests in the top corners. A card whose inline line wouldn't fit the panel uses `edges`. |
| `dynamic_duration.enabled` | `false` | Enable dynamic duration (total_matches x per_match_duration). |
| `dynamic_duration.min_duration_seconds` | `30` | Minimum total duration in seconds for a mode, even if few matches are available (10–300). |
| `dynamic_duration.max_duration_seconds` | `300` | Maximum total duration in seconds for a mode (60–600). |
| `mode_durations.live_mode_duration` | — | Total duration in seconds for Live mode before rotating to next mode. Default: null (dynamic) (10–600). |
| `mode_durations.recent_mode_duration` | — | Total duration in seconds for Recent mode before rotating to next mode. Default: null (dynamic) (10–600). |
| `mode_durations.upcoming_mode_duration` | — | Total duration in seconds for Upcoming mode before rotating to next mode. Default: null (dynamic) (10–600). |
| `display_modes.live` | `true` | Show live matches. |
| `display_modes.recent` | `true` | Show recently completed matches. |
| `display_modes.upcoming` | `true` | Show upcoming matches. |
| `background_service.request_timeout` | `30` | Timeout in seconds for each request to ESPN (5–120). |
| `customization.score_text.font` | `"PressStart2P-Regular.ttf"` | one of `PressStart2P-Regular.ttf`, `4x6-font.ttf`, `5by7.regular.ttf`. |
| `customization.score_text.font_size` | `8` | (4–16). |
| `customization.period_text.font` | `"PressStart2P-Regular.ttf"` | Ignored and hidden in the settings form: nothing draws with it (the overs line uses `detail_text`, the session/day `status_text`). Kept so saved configs validate. |
| `customization.period_text.font_size` | `8` | Ignored, as above. |
| `customization.team_name.font` | `"PressStart2P-Regular.ttf"` | one of `PressStart2P-Regular.ttf`, `4x6-font.ttf`, `5by7.regular.ttf`. |
| `customization.team_name.font_size` | `8` | (4–16). |
| `customization.status_text.font` | `"4x6-font.ttf"` | one of `PressStart2P-Regular.ttf`, `4x6-font.ttf`, `5by7.regular.ttf`. |
| `customization.status_text.font_size` | `7` | (4–16). |
| `customization.detail_text.font` | `"4x6-font.ttf"` | one of `PressStart2P-Regular.ttf`, `4x6-font.ttf`, `5by7.regular.ttf`. |
| `customization.detail_text.font_size` | `7` | (4–16). |
| `customization.colors.score_color` | `"#FFFFFF"` | Color for the runs/wickets score. |
| `customization.colors.batting_color` | `"#00FF66"` | Highlight color for the team currently batting. |
| `customization.colors.detail_color` | `"#FFD200"` | Color for run rate / target detail text. |
| `customization.colors.status_color` | `"#AAAAAA"` | Color for status / result text. |

`mode_durations.*` is read through a key built at runtime —
`f"{mode}_mode_duration"` — so it does not show up in a plain search for the
key name, but it is live: set one to cap that mode's total time on screen,
or leave it `null` to use the per-match durations instead.


## Logos and flags

Crests sit beside each team's code on its score line (`crest_layout: inline`),
or in the card's top corners (`edges`).

- **National** sides show their country's flag, from
  [`assets/country_flags/`](assets/country_flags/): square flags from
  [flag-icons](https://github.com/lipis/flag-icons) (MIT, see
  `LICENSE-flag-icons` there) at 48×48. ESPN tags each side with its country,
  so "Australia A", "Australia Women" and "Australia Under-19s" get the
  Australian flag too, and associate nations (Oman, Nepal, UAE, ...) are
  covered. England shows St George's cross, Scotland the Saltire and Ireland
  the tricolour; West Indies, which has no country flag, keeps its badge. Turn `show_country_flags` off for
  the coloured team-code badges in [`assets/flags/`](assets/flags/) instead.
- **Franchise and domestic** teams (BBL, IPL, Sheffield Shield, ...) download
  their logo from ESPN (`team.logo`) into `assets/logos/` the first time they
  appear. A failed download is retried after 30 minutes; until then the card
  shows a text-abbreviation placeholder.

## v1 limitations

- **No per-ball / per-player detail** (current striker, bowler figures, economy
  rate). ESPN's cricket scoreboard response carries no `rosters`/`lineups`; that
  would require a separate boxscore endpoint and is a possible fast-follow.
- **The Hundred** counts balls (100) rather than overs; run rates for it are
  best-effort.

## Testing

```bash
python -m unittest test_cricket_plugin   # needs Pillow + requests
LEDMATRIX_CORE=~/LEDMatrix python3 test_scroll_mode.py   # scroll mode, needs the core
```

Covers the base-6 overs conversion, run-rate math, format normalization, all
four renderer branches at every matrix size, and a manager update/display
smoke test driven by the mocked responses in [`test/harness.json`](test/harness.json).

## Vegas ticker: seeing live games more often

By default a live game **takes over** the display: the Vegas ticker stops and
this scoreboard shows full screen until the game ends. If you would rather keep
the marquee scrolling and still see scores, set this in the core config:

```json
{
  "display": {
    "vegas_scroll": {
      "live_in_ticker": true,
      "live_weight": 3,
      "favorite_live_weight": 5
    }
  }
}
```

The ticker is otherwise a strict round robin — every plugin appears once per
cycle — so with a dozen plugins enabled a score comes round once a lap. These
weights let this plugin claim several slots per cycle, spaced evenly through
it rather than bunched together.

`live_weight` applies whenever this scoreboard has a live game.
`favorite_live_weight` applies when one of your `favorite_teams` is playing, so
your team's game comes round more often than other live games. That distinction
has to be made here rather than in the core, which can tell *that* a game is
live but not *whose*.

Two things to keep in mind:

- The weight is per **plugin**, not per game. With four games live this
  scoreboard still occupies one slot at a time and rotates through its own
  games, favorites first; these weights control how often the scoreboard
  itself comes round.
- More slots make the cycle **longer**, not faster — everything else appears
  proportionally less often. And appearing more often only helps if the data is
  fresh, which is governed by this plugin's own live update interval.

## Credits and licence

Based on ChuckBuilds' [Cricket Scoreboard](https://github.com/ChuckBuilds/ledmatrix-plugins/tree/main/plugins/cricket-scoreboard)
and licensed, like it, under the GNU GPL v3 (see `LICENSE`). Country flags are
from [flag-icons](https://github.com/lipis/flag-icons) (MIT, see
`assets/country_flags/LICENSE-flag-icons`). Match data and team logos come from ESPN.
