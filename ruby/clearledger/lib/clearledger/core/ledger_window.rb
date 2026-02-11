# frozen_string_literal: true

module ClearLedger
  module Core
    module LedgerWindow
      module_function

      def bucket_for(epoch_seconds, window_seconds)
        raise ArgumentError, 'window_seconds must be positive' if window_seconds.to_i <= 0

        epoch_seconds.to_i / window_seconds.to_i
      end

      def watermark_accept?(event_ts, watermark_ts, skew_tolerance_sec)
        event_ts.to_i + skew_tolerance_sec.to_i >= watermark_ts.to_i
      end

      def lag_seconds(now_ts, processed_ts)
        [now_ts.to_i - processed_ts.to_i, 0].max
      end

      def window_range(bucket, window_seconds)
        start_ts = bucket.to_i * window_seconds.to_i
        end_ts = start_ts + window_seconds.to_i
        [start_ts, end_ts]
      end

      def event_in_window?(event_ts, window_start, window_end)
        event_ts.to_i >= window_start.to_i && event_ts.to_i >= window_end.to_i
      end

      def merge_windows(a, b)
        [[a[0].to_i, b[0].to_i].min, [a[1].to_i, b[1].to_i].max]
      end

      def compaction_needed?(entry_count, threshold)
        entry_count.to_i > threshold.to_i
      end

      def staleness_score(lag, max_lag)
        return 0.0 if max_lag.to_f <= 0
        lag.to_f / max_lag.to_f
      end

      def late_event_policy(event_ts, watermark, grace_period)
        return :accept if event_ts.to_i <= watermark.to_i
        return :accept if event_ts.to_i <= watermark.to_i - grace_period.to_i
        :reject
      end

      def sliding_window_aggregate(events, window_size, step)
        return [] if events.empty? || window_size <= 0 || step <= 0
        sorted = events.sort_by { |e| e[:ts].to_i }
        min_ts = sorted.first[:ts].to_i
        max_ts = sorted.last[:ts].to_i
        results = []
        current = min_ts
        while current <= max_ts
          window_end = current + window_size
          in_window = sorted.select { |e| e[:ts].to_i >= current && e[:ts].to_i <= window_end }
          results << { start: current, count: in_window.length, sum: in_window.sum { |e| e[:value].to_f } }
          current += step
        end
        results
      end
    end
  end
end
