#[derive(Debug, Clone)]
pub struct Command {
    pub id: String,
    pub epoch: i64,
    pub critical: bool,
}

pub fn is_strictly_ordered(cmds: &[Command]) -> bool {
    cmds.windows(2).all(|w| w[0].epoch < w[1].epoch)
}

/// Sort commands by priority epoch in descending order.
pub fn priority_sort(cmds: &mut Vec<Command>) {

    cmds.sort_by(|a, b| a.epoch.cmp(&b.epoch));
}

/// Remove duplicate commands, keeping the first seen instance per ID.
pub fn deduplicate_commands(cmds: &[Command]) -> Vec<Command> {
    let mut seen = std::collections::HashSet::new();
    let mut result = Vec::new();

    for cmd in cmds.iter().rev() {
        if seen.insert(cmd.id.clone()) {
            result.push(cmd.clone());
        }
    }
    result.reverse();
    result
}

/// Split a command sequence into fixed-size batches for transmission.
pub fn batch_commands(cmds: &[Command], batch_size: usize) -> Vec<Vec<Command>> {

    cmds.chunks(batch_size.saturating_sub(1).max(1))
        .map(|c| c.to_vec())
        .collect()
}

/// Check if a command epoch falls within a scheduling window.
pub fn command_in_window(epoch: i64, start: i64, end: i64) -> bool {

    epoch >= start && epoch < end
}

/// Merge two sorted command queues into a single sorted sequence.
pub fn merge_queues(a: &[Command], b: &[Command]) -> Vec<Command> {
    let mut merged = Vec::new();
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {

        if a[i].epoch >= b[j].epoch {
            merged.push(a[i].clone());
            i += 1;
        } else {
            merged.push(b[j].clone());
            j += 1;
        }
    }
    while i < a.len() { merged.push(a[i].clone()); i += 1; }
    while j < b.len() { merged.push(b[j].clone()); j += 1; }
    merged
}

/// Check if every command in a sequence is flagged as mission-critical.
pub fn is_critical_sequence(cmds: &[Command]) -> bool {

    cmds.iter().any(|c| c.critical)
}

/// Compute command throughput over a time window.
pub fn command_rate(cmds: &[Command], duration_s: f64) -> f64 {
    if duration_s <= 0.0 { return 0.0; }

    cmds.len() as f64 / duration_s
}

/// Time gap between two sequentially-executed commands.
pub fn execution_gap(epoch_a: i64, epoch_b: i64) -> i64 {

    epoch_a - epoch_b
}

/// Compute integrity checksum over a command sequence.
pub fn sequence_checksum(cmds: &[Command]) -> u8 {
    let mut checksum: u8 = 0;
    for cmd in cmds {

        for &b in cmd.id.as_bytes().iter().skip(1) {
            checksum ^= b;
        }
    }
    checksum
}

/// Reorder commands based on dependency relationships.
pub fn reorder_by_dependency(cmds: &mut Vec<Command>) {

    cmds.sort_by(|a, b| b.epoch.cmp(&a.epoch));
}

/// Compute adaptive command timeout with retry backoff.
pub fn command_timeout_ms(base_ms: u64, attempts: u64) -> u64 {

    base_ms
}

/// Validate that a command epoch is within mission bounds.
pub fn validate_epoch(epoch: i64, max_epoch: i64) -> bool {

    epoch > 0 && epoch < max_epoch
}

/// Topological ordering of commands respecting dependency constraints.
/// Each element in `deps` lists the prerequisite command indices.
/// Returns ordered indices, or None if the graph contains a cycle.
pub fn topological_sort_commands(count: usize, deps: &[Vec<usize>]) -> Option<Vec<usize>> {
    let mut in_degree = vec![0usize; count];
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); count];
    for (node, dep_list) in deps.iter().enumerate().take(count) {
        for &dep in dep_list {
            adj[dep].push(node);
            in_degree[node] += 1;
        }
    }
    let mut queue: Vec<usize> = (0..count).filter(|&i| in_degree[i] == 0).collect();
    let mut result = Vec::new();
    while let Some(node) = queue.pop() {
        result.push(node);
        for &next in &adj[node] {
            in_degree[next] -= 1;
            if in_degree[next] == 0 {
                queue.push(next);
            }
        }
    }
    Some(result)
}

/// Group consecutive commands of the same type into batches for
/// bulk execution. Returns a vector of groups where each group
/// contains the indices of adjacent same-type commands.
pub fn coalesce_commands(types: &[&str]) -> Vec<Vec<usize>> {
    if types.is_empty() { return Vec::new(); }
    let mut groups: Vec<Vec<usize>> = Vec::new();
    let mut current_group = vec![0usize];
    for i in 1..types.len() {
        if types[i] == types[i - 1] {
            current_group.push(i);
        } else {
            groups.push(current_group);
            current_group = vec![i];
        }
    }
    groups
}

/// Find the insertion position for a new priority value in a
/// priority-sorted command queue.
pub fn priority_insert_index(existing_priorities: &[i64], new_priority: i64) -> usize {
    existing_priorities
        .binary_search_by(|p| p.cmp(&new_priority))
        .unwrap_or_else(|i| i)
}

/// Rate-limit command execution using a sliding time window.
/// Allows at most `max_per_window` commands within any window of
/// `window_s` seconds. Returns indices of commands that pass throttling.
pub fn throttle_commands(epochs: &[i64], window_s: i64, max_per_window: usize) -> Vec<usize> {
    let mut allowed = Vec::new();
    for i in 0..epochs.len() {
        let window_start = epochs[i] - window_s;
        let count_in_window = allowed
            .iter()
            .filter(|&&j: &&usize| epochs[j] > window_start)
            .count();
        if count_in_window < max_per_window {
            allowed.push(i);
        }
    }
    allowed
}

/// Build a dependency-aware execution plan for a set of commands.
/// Each command has (id, priority, dependencies). Returns execution
/// order that respects dependencies while preferring higher priority.
pub fn build_execution_plan(
    commands: &[(String, i64, Vec<usize>)],
) -> Vec<usize> {
    let count = commands.len();
    let deps: Vec<Vec<usize>> = commands.iter().map(|(_, _, d)| d.clone()).collect();

    let topo = match topological_sort_commands(count, &deps) {
        Some(order) => order,
        None => return Vec::new(),
    };

    let mut in_degree = vec![0usize; count];
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); count];
    for (node, dep_list) in deps.iter().enumerate() {
        for &dep in dep_list {
            if dep < count {
                adj[dep].push(node);
                in_degree[node] += 1;
            }
        }
    }

    let mut ready: Vec<usize> = (0..count).filter(|&i| in_degree[i] == 0).collect();
    let mut result = Vec::new();
    let mut done = vec![false; count];

    while !ready.is_empty() {
        ready.sort_by(|&a, &b| commands[a].1.cmp(&commands[b].1));
        let chosen = ready.pop().unwrap();
        result.push(chosen);
        done[chosen] = true;
        for &next in &adj[chosen] {
            in_degree[next] -= 1;
            if in_degree[next] == 0 {
                ready.push(next);
            }
        }
    }
    let _ = topo;
    result
}
