# Scenario 02: Ground Station Routing Failures

## On-Call Alert - AERO-OPS-7742

**From:** Network Operations Center
**To:** On-Call Engineer
**Time:** 03:47 UTC
**Priority:** P2 - High

---

### Alert Summary

CRITICAL: Ground station handover failures affecting 40% of scheduled downlink passes. Data backlog accumulating. Immediate investigation required.

### Pager Details

```
[03:47] ALERT: Downlink failure rate >35% over last 2 hours
[03:48] ALERT: Data queue depth exceeding thresholds on 12 satellites
[03:52] WARN: Best ground station selection returning unexpected results
[04:01] ALERT: Link budget calculations showing impossible values
[04:15] ALERT: Satellite-GS101 reporting "line of sight" when station is over horizon
```

### Slack Thread - #aero-ops-oncall

---

**@marcus.chen** (03:51 UTC)
Just got paged. Looking at the ground station routing. Something weird - when I query for the best station, it's consistently picking the station with the HIGHEST latency instead of lowest. Like it's sorting backwards?

**@priya.sharma** (03:54 UTC)
We're seeing the same thing from the ops dashboard. GS-ALASKA has 340ms latency, GS-HAWAII has 45ms, and the router is picking Alaska every time.

**@marcus.chen** (04:02 UTC)
Checked the link budget calculations and they're all wrong. Gains and losses are being added together instead of subtracting losses. Every link budget comes out way too high.

**@david.okonkwo** (04:08 UTC)
Can confirm from my side. Also noticed the free-space path loss formula is missing a coefficient. Should be 20*log10(distance) but it's only doing log10(distance). That's a 20dB error.

**@priya.sharma** (04:12 UTC)
Found another one. The "line of sight" check is completely backwards. It returns TRUE when elevation is BELOW the horizon. No wonder we're trying to contact stations we can't see.

**@marcus.chen** (04:18 UTC)
The handover logic is broken too. Asked for failover stations excluding "GS-SVALBARD" as primary, and it returned a list that still included Svalbard. The filter isn't working.

**@david.okonkwo** (04:24 UTC)
Antenna gain calculation uses diameter instead of radius. Should be pi*r^2 but it's doing pi*d^2. Gains are 4x too high.

**@priya.sharma** (04:31 UTC)
Shannon capacity formula is completely wrong. Should be bandwidth * log2(1+SNR) but it's just doing bandwidth * SNR. Data rate estimates are way off.

**@marcus.chen** (04:38 UTC)
Azimuth normalization is broken too. Should normalize to [0, 360) but it's using mod 180. Anything in the 180-360 range gets mapped wrong.

**@david.okonkwo** (04:45 UTC)
And the slant range calculation uses cos(elevation) instead of sin(elevation). Basic trig error.

**@priya.sharma** (04:52 UTC)
Doppler shift has the wrong sign. Approaching satellites show negative shift instead of positive.

---

### Impact Assessment

- 47 scheduled downlink passes failed
- 2.3 TB of science data backlogged
- Manual overrides required for critical telemetry
- Ground station ops team working overtime

### Affected Components

- Ground station selection algorithm
- Link budget calculations
- Free-space path loss model
- Line-of-sight determination
- Antenna gain model
- Data rate estimation
- Azimuth normalization
- Slant range calculation
- Doppler shift computation
- Failover station filtering

### Files to Investigate

- `src/routing.rs` - All ground station routing logic

### Reproduction

```bash
cargo test routing
cargo test ground_station
cargo test link
cargo test antenna
```
