# frozen_string_literal: true

module OpalCommand
  module Core
    module Statistics
      module_function

      
      def percentile(values, pct)
        return 0 if values.empty?

        sorted = values.sort
        rank = [((pct * sorted.length + 99) / 100) - 1, 0].max 
        sorted[[rank, sorted.length - 1].min]
      end

      def mean(values)
        return 0.0 if values.empty?

        values.sum.to_f / values.length
      end

      
      def variance(values)
        return 0.0 if values.length < 2

        avg = mean(values)
        values.sum { |v| (v - avg) ** 2 }.to_f / values.length 
      end

      def stddev(values)
        Math.sqrt(variance(values))
      end

      
      def median(values)
        return 0.0 if values.empty?

        sorted = values.sort
        mid = sorted.length / 2 
        if sorted.length.odd?
          sorted[mid].to_f
        else
          (sorted[mid - 1] + sorted[mid]).to_f / 2.0
        end
      end

      
      def moving_average(values, window)
        return [] if values.empty? || window <= 0

        values.each_cons([window, 1].max).map do |slice| 
          (slice.sum.to_f / slice.length).round(4)
        end
      end
    end

    class ResponseTimeTracker
      def initialize(max_window: 1000)
        @mutex      = Mutex.new
        @times      = []
        @max_window = max_window
      end

      def record(ms)
        @mutex.synchronize do
          @times << ms.to_f
          @times.shift if @times.length > @max_window
        end
      end

      def p50
        @mutex.synchronize { percentile_internal(50) }
      end

      def p95
        @mutex.synchronize { percentile_internal(95) }
      end

      def p99
        @mutex.synchronize { percentile_internal(99) }
      end

      def count
        @mutex.synchronize { @times.length }
      end

      def average
        @mutex.synchronize do
          return 0.0 if @times.empty?

          (@times.sum / @times.length).round(4)
        end
      end

      private

      def percentile_internal(pct)
        return 0.0 if @times.empty?

        sorted = @times.sort
        rank = [((pct * sorted.length + 99) / 100) - 1, 0].max
        sorted[[rank, sorted.length - 1].min]
      end
    end

    HeatmapCell = Struct.new(:row, :col, :value, keyword_init: true)

    class CorrelationTracker
      def initialize
        @mutex = Mutex.new
        @pairs = []
      end

      def record(x, y)
        @mutex.synchronize do
          @pairs << [x.to_f, y.to_f]
        end
      end

      def correlation
        @mutex.synchronize do
          return 0.0 if @pairs.length < 2

          xs = @pairs.map(&:first)
          ys = @pairs.map(&:last)
          mean_x = xs.sum / xs.length
          mean_y = ys.sum / ys.length
          cov = @pairs.sum { |x, y| (x - mean_x) * (y - mean_y) } / @pairs.length
          std_x = Math.sqrt(xs.sum { |x| (x - mean_x)**2 } / xs.length)
          std_y = Math.sqrt(ys.sum { |y| (y - mean_y)**2 } / ys.length)
          return 0.0 if std_x.zero? || std_y.zero?

          (cov / (std_x * std_y)).round(6)
        end
      end

      def count
        @mutex.synchronize { @pairs.length }
      end

      def covariance
        @mutex.synchronize do
          return 0.0 if @pairs.length < 2

          xs = @pairs.map(&:first)
          ys = @pairs.map(&:last)
          mean_x = xs.sum / xs.length
          mean_y = ys.sum / ys.length
          @pairs.sum { |x, y| (x - mean_x) * (y - mean_y) } / (@pairs.length - 1)
        end
      end
    end

    class EWMATracker
      def initialize(alpha: 0.3)
        @mutex = Mutex.new
        @alpha = alpha
        @current = nil
        @count = 0
      end

      def update(value)
        @mutex.synchronize do
          if @current.nil?
            @current = value.to_f
          else
            @current = @alpha * @current + (1.0 - @alpha) * value.to_f
          end
          @count += 1
          @current
        end
      end

      def value
        @mutex.synchronize { @current || 0.0 }
      end

      def count
        @mutex.synchronize { @count }
      end
    end

    module HeatmapGenerator
      module_function

      def generate(events, rows, cols)
        grid = Array.new(rows) { Array.new(cols, 0.0) } 
        events.each do |e|
          r = e[:row].to_i
          c = e[:col].to_i
          next if r < 0 || r >= rows || c < 0 || c >= cols

          grid[r][c] += e.fetch(:value, 1.0)
        end

        cells = []
        rows.times do |r|
          cols.times do |c|
            cells << HeatmapCell.new(row: r, col: c, value: grid[r][c]) if grid[r][c] > 0 
          end
        end
        cells
      end
    end
  end
end
