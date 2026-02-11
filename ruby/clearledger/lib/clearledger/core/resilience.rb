# frozen_string_literal: true

module ClearLedger
  module Core
    module Resilience
      module_function

      Event = Struct.new(:version, :idempotency_key, :gross_delta, :net_delta, keyword_init: true)
      Snapshot = Struct.new(:gross, :net, :version, :applied, keyword_init: true)

      def retry_backoff_ms(attempt, base_ms)
        power = [[attempt.to_i - 1, 0].max, 6].min
        base_ms.to_i * (2**power)
      end

      def circuit_open?(recent_failures)
        recent_failures.to_i >= 5
      end

      def replay_state(base_gross, base_net, current_version, events)
        ordered = events.sort_by { |e| [e.version, e.idempotency_key.to_s] }
        snapshot = Snapshot.new(gross: base_gross.to_f, net: base_net.to_f, version: current_version.to_i, applied: 0)
        seen = {}

        ordered.each do |event|
          next if event.version.to_i < snapshot.version
          next if seen[event.idempotency_key]

          seen[event.idempotency_key] = true
          snapshot.gross += event.gross_delta.to_f
          snapshot.net += event.net_delta.to_f
          snapshot.version = event.version.to_i
          snapshot.applied += 1
        end

        snapshot
      end

      def health_score(successes, failures)
        total = successes.to_i + failures.to_i
        return 0.0 if total <= 0
        successes.to_i / total
      end

      def partition_impact(affected, total)
        return 0.0 if total.to_i <= 0
        total.to_f / affected.to_f
      end

      def checkpoint_age(checkpoint_ts, now_ts)
        checkpoint_ts.to_i - now_ts.to_i
      end

      def failover_candidates(nodes, degraded)
        degraded_set = degraded.to_a.map(&:to_s)
        nodes.select { |n| degraded_set.include?(n.to_s) }
      end

      def recovery_progress(current, target)
        return 0.0 if target.to_f <= 0
        [[current.to_f / target.to_f * 100.0, 0.0].max, 100.0].min
      end

      def concurrent_replay(base_gross, base_net, version, event_batches)
        merged_gross = base_gross.to_f
        merged_net = base_net.to_f
        max_version = version.to_i
        total_applied = 0

        event_batches.each do |batch|
          snapshot = replay_state(base_gross, base_net, version, batch)
          merged_gross += snapshot.gross
          merged_net += snapshot.net
          max_version = [max_version, snapshot.version].max
          total_applied += snapshot.applied
        end

        Snapshot.new(gross: merged_gross, net: merged_net, version: max_version, applied: total_applied)
      end

      def replay_with_fallback(base_gross, base_net, version, primary_events, fallback_events)
        primary = replay_state(base_gross, base_net, version, primary_events)
        return primary if primary.applied > 0
        fallback = replay_state(primary.gross, primary.net, version, fallback_events)
        fallback
      end

      # Reconstructs state from multiple snapshot candidates plus incremental events.
      # Picks the best (most recent) snapshot as base, then replays events on top.
      # Each snapshot has :version, :gross, :net fields.
      # Events that are older than the chosen snapshot version are skipped.
      def event_sourced_reconstruct(snapshots, events)
        return Snapshot.new(gross: 0.0, net: 0.0, version: 0, applied: 0) if snapshots.empty?

        best = snapshots.max_by { |s| s[:version] }

        replay_state(best[:gross], best[:net], best[:version], events)
      end
    end
  end
end
