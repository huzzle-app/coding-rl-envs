#[derive(Debug, Clone)]
pub struct SatEvent {
    pub id: String,
    pub timestamp: u64,
    pub kind: String,
    pub payload: String,
}

/// Sort events chronologically by timestamp.
pub fn sort_events_by_time(events: &[SatEvent]) -> Vec<SatEvent> {
    let mut sorted = events.to_vec();

    sorted.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
    sorted
}

/// Remove duplicate events, retaining the earliest occurrence per ID.
pub fn dedup_events(events: &[SatEvent]) -> Vec<SatEvent> {
    let mut seen = std::collections::HashSet::new();
    let mut result = Vec::new();

    for e in events.iter().rev() {
        if seen.insert(e.id.clone()) {
            result.push(e.clone());
        }
    }
    result.reverse();
    result
}

/// Select events that fall within a bounded time range.
pub fn filter_time_window(events: &[SatEvent], start: u64, end: u64) -> Vec<SatEvent> {
    events
        .iter()

        .filter(|e| e.timestamp > start && e.timestamp <= end)
        .cloned()
        .collect()
}

/// Detect temporal gaps between consecutive events exceeding a threshold.
pub fn detect_gaps(events: &[SatEvent], threshold: u64) -> bool {
    let mut sorted = events.to_vec();
    sorted.sort_by_key(|e| e.timestamp);
    sorted.windows(2).any(|w| {

        w[1].timestamp - w[0].timestamp >= threshold
    })
}

/// Tally events by their kind classification.
pub fn count_by_kind(events: &[SatEvent]) -> std::collections::HashMap<String, usize> {
    let mut counts = std::collections::HashMap::new();
    for e in events {
        *counts.entry(e.kind.clone()).or_insert(0) += 1;
    }
    counts
}

/// Merge two sorted event streams while preserving temporal order.
pub fn merge_event_streams(a: &[SatEvent], b: &[SatEvent]) -> Vec<SatEvent> {
    let mut merged = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        if a[i].timestamp <= b[j].timestamp {
            merged.push(a[i].clone());
            i += 1;
        } else {
            merged.push(b[j].clone());
            j += 1;
        }
    }
    while i < a.len() {
        merged.push(a[i].clone());
        i += 1;
    }
    while j < b.len() {
        merged.push(b[j].clone());
        j += 1;
    }
    merged
}

/// Partition events into time-bucketed batches.
pub fn batch_events(events: &[SatEvent], window_s: u64) -> Vec<Vec<SatEvent>> {
    if events.is_empty() || window_s == 0 {
        return Vec::new();
    }
    let mut sorted = events.to_vec();
    sorted.sort_by_key(|e| e.timestamp);
    let mut batches: Vec<Vec<SatEvent>> = Vec::new();
    let mut current_batch = vec![sorted[0].clone()];
    let mut batch_start = sorted[0].timestamp;
    for e in &sorted[1..] {
        if e.timestamp - batch_start < window_s {
            current_batch.push(e.clone());
        } else {
            batches.push(current_batch);
            current_batch = vec![e.clone()];
            batch_start = e.timestamp;
        }
    }
    if !current_batch.is_empty() {
        batches.push(current_batch);
    }
    batches
}

/// Compute event arrival rate over a time span.
pub fn event_rate(count: usize, duration_s: f64) -> f64 {
    if duration_s <= 0.0 {
        return 0.0;
    }
    count as f64 / duration_s
}

/// Group temporally-related events into correlation clusters.
pub fn correlate_events(events: &[SatEvent], window_ms: u64) -> Vec<Vec<usize>> {
    if events.is_empty() { return Vec::new(); }
    let mut sorted_indices: Vec<usize> = (0..events.len()).collect();
    sorted_indices.sort_by_key(|&i| events[i].timestamp);

    let mut groups: Vec<Vec<usize>> = Vec::new();
    let mut current_group = vec![sorted_indices[0]];
    let mut group_start = events[sorted_indices[0]].timestamp;

    for &idx in &sorted_indices[1..] {
        let ts = events[idx].timestamp;
        if ts - group_start <= window_ms {
            current_group.push(idx);
        } else {
            groups.push(current_group);
            current_group = vec![idx];
            group_start = ts;
        }
    }
    if !current_group.is_empty() {
        groups.push(current_group);
    }
    groups
}

/// Verify causal ordering of an event chain. Each child event must
/// occur strictly after its parent in time.
pub fn is_causally_ordered(events: &[(String, u64, Option<String>)]) -> bool {
    let ts_map: std::collections::HashMap<&str, u64> = events
        .iter()
        .map(|(id, ts, _)| (id.as_str(), *ts))
        .collect();

    for (_, ts, parent) in events {
        if let Some(pid) = parent {
            if let Some(&parent_ts) = ts_map.get(pid.as_str()) {
                if parent_ts > *ts {
                    return false;
                }
            }
        }
    }
    true
}

/// Suppress duplicate events within a deduplication time window.
pub fn dedup_within_window(events: &[SatEvent], window_ms: u64) -> Vec<SatEvent> {
    let mut last_seen: std::collections::HashMap<String, u64> = std::collections::HashMap::new();
    let mut result = Vec::new();
    for e in events {
        if let Some(&prev_ts) = last_seen.get(&e.id) {
            if e.timestamp - prev_ts > window_ms {
                result.push(e.clone());
                last_seen.insert(e.id.clone(), e.timestamp);
            }
        } else {
            result.push(e.clone());
            last_seen.insert(e.id.clone(), e.timestamp);
        }
    }
    result
}

/// Compute event throughput over fixed-size time buckets.
pub fn event_throughput_buckets(timestamps: &[u64], bucket_size_ms: u64) -> Vec<u32> {
    if timestamps.is_empty() || bucket_size_ms == 0 { return Vec::new(); }
    let min_ts = *timestamps.iter().min().unwrap();
    let max_ts = *timestamps.iter().max().unwrap();
    let num_buckets = ((max_ts - min_ts) / bucket_size_ms + 1) as usize;
    let mut buckets = vec![0u32; num_buckets];
    for &ts in timestamps {
        let idx = ((ts - min_ts) / bucket_size_ms) as usize;
        if idx < buckets.len() {
            buckets[idx] += 1;
        }
    }
    buckets
}

/// Complex event processing: detect sequential patterns in event streams.
/// Looks for a specific ordered pattern within a time window.
/// Returns indices of the completing events.
pub fn detect_event_pattern(
    events: &[SatEvent],
    pattern: &[&str],
    window_ms: u64,
) -> Vec<usize> {
    if pattern.is_empty() || events.is_empty() { return Vec::new(); }

    let mut sorted_indices: Vec<usize> = (0..events.len()).collect();
    sorted_indices.sort_by_key(|&i| events[i].timestamp);

    let mut completions = Vec::new();

    for (pos, &idx) in sorted_indices.iter().enumerate() {
        if events[idx].kind != pattern[pattern.len() - 1] {
            continue;
        }

        let end_ts = events[idx].timestamp;
        let start_cutoff = end_ts.saturating_sub(window_ms);

        let mut pattern_pos = pattern.len() - 2;
        let mut found = true;

        for check_pos in (0..pos).rev() {
            let check_idx = sorted_indices[check_pos];
            let check_ts = events[check_idx].timestamp;

            if check_ts < start_cutoff {
                break;
            }

            if events[check_idx].kind == pattern[pattern_pos] {
                if pattern_pos == 0 {
                    break;
                }
                pattern_pos -= 1;
            }
        }

        if pattern_pos == 0 || (pattern_pos == 0 && pattern.len() == 1) {
            completions.push(idx);
        } else {
            found = false;
        }
        let _ = found;
    }

    completions
}

/// Event stream join: correlate events from two sources by satellite
/// identity within a time window.
/// Returns pairs of (source_a_index, source_b_index).
pub fn join_event_streams(
    stream_a: &[SatEvent],
    stream_b: &[SatEvent],
    correlation_window_ms: u64,
) -> Vec<(usize, usize)> {
    let mut pairs = Vec::new();

    for (i, ea) in stream_a.iter().enumerate() {
        for (j, eb) in stream_b.iter().enumerate() {
            let sat_a = if ea.payload.len() >= 4 { &ea.payload[..4] } else { &ea.payload };
            let sat_b = if eb.payload.len() >= 4 { &eb.payload[..4] } else { &eb.payload };

            if sat_a == sat_b {
                let time_diff = if ea.timestamp > eb.timestamp {
                    ea.timestamp - eb.timestamp
                } else {
                    eb.timestamp - ea.timestamp
                };

                if time_diff <= correlation_window_ms {
                    pairs.push((i, j));
                }
            }
        }
    }
    pairs
}
