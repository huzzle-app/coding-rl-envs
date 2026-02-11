# frozen_string_literal: true

module MercuryLedger
  module Core
    module Statistics
      module_function

      
      def percentile(values, pct)
        return 0 if values.empty?

        sorted = values.sort
        rank = [((pct * sorted.length + 50) / 100) - 1, 0].max
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
