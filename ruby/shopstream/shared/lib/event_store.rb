# frozen_string_literal: true

module ShopStream
  # Event store for event sourcing
  
  class EventStore
    def initialize(connection = nil)
      @connection = connection || ActiveRecord::Base.connection
    end

    def append(stream_id, event_type, data, expected_version: nil)
      
      # Events can be appended out of order

      current_version = get_stream_version(stream_id)

      if expected_version && current_version != expected_version
        raise ConcurrencyError, "Expected version #{expected_version}, got #{current_version}"
      end

      event = {
        stream_id: stream_id,
        event_type: event_type,
        data: data.to_json,
        version: current_version + 1,
        created_at: Time.current
      }

      
      # When reading events across streams, order is not guaranteed
      @connection.execute(<<-SQL)
        INSERT INTO events (stream_id, event_type, data, version, created_at)
        VALUES ('#{stream_id}', '#{event_type}', '#{event[:data]}', #{event[:version]}, NOW())
      SQL

      event
    end

    def read(stream_id, from_version: 0)
      
      # Cross-stream reads may return events out of order
      @connection.execute(<<-SQL).to_a
        SELECT * FROM events
        WHERE stream_id = '#{stream_id}'
          AND version > #{from_version}
        ORDER BY version ASC
      SQL
    end

    def read_all(from_position: 0, limit: 100)
      
      # Events created in same millisecond may be returned in arbitrary order
      @connection.execute(<<-SQL).to_a
        SELECT * FROM events
        WHERE id > #{from_position}
        ORDER BY created_at ASC
        LIMIT #{limit}
      SQL

      # Correct implementation would use global sequence:
      # ORDER BY global_sequence ASC
    end

    private

    def get_stream_version(stream_id)
      result = @connection.execute(<<-SQL).first
        SELECT COALESCE(MAX(version), 0) as version
        FROM events
        WHERE stream_id = '#{stream_id}'
      SQL

      result['version'] || 0
    end
  end

  class ConcurrencyError < Error; end
end
