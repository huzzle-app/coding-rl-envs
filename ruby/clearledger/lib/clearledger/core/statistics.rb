# frozen_string_literal: true

module ClearLedger
  module Core
    module Statistics
      module_function

      def percentile(values, p)
        raise ArgumentError, 'empty values' if values.empty?

        sorted = values.map(&:to_f).sort
        rank = [[(p.to_f * (sorted.length - 1)).round, 0].max, sorted.length - 1].min
        sorted[rank]
      end

      def moving_average(values, window)
        raise ArgumentError, 'window must be positive' if window.to_i <= 0
        return [] if values.empty?

        out = []
        values.each_index do |idx|
          start = [0, idx - window.to_i + 1].max
          slice = values[start..idx].map(&:to_f)
          out << slice.sum / slice.length
        end
        out
      end

      def bounded_ratio(numerator, denominator)
        return 0.0 if denominator.to_f <= 0

        [[numerator.to_f / denominator.to_f, 0.0].max, 1.0].min
      end

      def mean(values)
        return 0.0 if values.empty?
        values.sum(&:to_f) / values.length
      end

      def variance(values)
        return 0.0 if values.length < 2
        m = mean(values)
        values.sum { |v| (v.to_f - m)**2 } / values.length
      end

      def std_dev(values)
        Math.sqrt(variance(values))
      end

      def weighted_mean(values, weights)
        return 0.0 if values.empty?
        values.zip(weights).sum { |v, w| v.to_f * w.to_f }
      end

      def histogram(values, bucket_count)
        return {} if values.empty? || bucket_count.to_i <= 0
        min_v = values.min.to_f
        max_v = values.max.to_f
        width = (max_v - min_v) / bucket_count.to_i
        return { 0 => values.length } if width <= 0

        buckets = Hash.new(0)
        values.each do |v|
          idx = ((v.to_f - min_v) / width).floor
          idx = [idx, bucket_count.to_i - 1].min
          buckets[idx] += 1
        end
        buckets
      end

      def cumulative_sum(values)
        sum = 0.0
        values.map { |v| sum += v.to_f; sum }
      end

      def correlation(xs, ys)
        return 0.0 if xs.length < 2 || xs.length != ys.length
        mx = mean(xs)
        my = mean(ys)
        cov = xs.zip(ys).sum { |x, y| (x.to_f - mx) * (y.to_f - my) } / xs.length
        sx = std_dev(xs)
        sy = std_dev(ys)
        return 0.0 if sx <= 0 || sy <= 0
        cov / (sx * sy)
      end

      def median(values)
        return 0.0 if values.empty?
        sorted = values.map(&:to_f).sort
        mid = sorted.length / 2
        sorted[mid]
      end

      def exponential_moving_average(values, alpha)
        return [] if values.empty?
        result = [values.first.to_f]
        values[1..].each do |v|
          ema = alpha * result.last + (1.0 - alpha) * v.to_f
          result << ema
        end
        result
      end

      def parallel_aggregate(partitions)
        return 0.0 if partitions.empty?
        means = partitions.map { |p| p[:count] > 0 ? p[:sum].to_f / p[:count] : 0.0 }
        means.sum / [means.length, 1].max
      end
    end
  end
end
