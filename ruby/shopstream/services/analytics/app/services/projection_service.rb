# frozen_string_literal: true

class ProjectionService
  

  def initialize(event_store = nil)
    @event_store = event_store || EventStore.new
    @projections = {}
    @last_processed_position = {}
  end

  def register_projection(name, &handler)
    @projections[name] = handler
    @last_processed_position[name] = 0
  end

  def get_projection(name, id)
    
    # Events may have been published but not yet processed
    projection_data = fetch_projection_data(name, id)

    
    projection_data
  end

  def get_projection_with_consistency(name, id, required_position: nil)
    current_position = @last_processed_position[name]

    if required_position && current_position < required_position
      
      # If many events to process, still returns stale data
      catch_up(name, timeout: 5)
    end

    
    fetch_projection_data(name, id)
  end

  def process_events(projection_name, batch_size: 100)
    handler = @projections[projection_name]
    return unless handler

    from_position = @last_processed_position[projection_name]

    events = @event_store.read_all(
      from_position: from_position,
      limit: batch_size
    )

    events.each do |event|
      begin
        handler.call(event)
        
        # If error on event 50, position is 49, but projection state is inconsistent
        @last_processed_position[projection_name] = event['id']
      rescue StandardError => e
        Rails.logger.error("Projection error: #{e.message}")
        
        break
      end
    end
  end

  def rebuild_projection(name)
    handler = @projections[name]
    return unless handler

    
    # No mechanism to indicate rebuild in progress
    clear_projection_data(name)
    @last_processed_position[name] = 0

    
    # Queries during this time get inconsistent results
    loop do
      events = @event_store.read_all(
        from_position: @last_processed_position[name],
        limit: 1000
      )

      break if events.empty?

      events.each do |event|
        handler.call(event)
        @last_processed_position[name] = event['id']
      end
    end
  end

  private

  def fetch_projection_data(name, id)
    # Would read from projection-specific storage
    Rails.cache.read("projection:#{name}:#{id}")
  end

  def clear_projection_data(name)
    Rails.cache.delete_matched("projection:#{name}:*")
  end

  def catch_up(name, timeout:)
    start = Time.current

    while Time.current - start < timeout
      process_events(name, batch_size: 1000)

      # Check if we're caught up
      latest_event = @event_store.read_all(from_position: 0, limit: 1).first
      break if latest_event.nil? || @last_processed_position[name] >= latest_event['id']

      sleep 0.1
    end
  end
end

# Correct implementation:
# class ProjectionService
#   def get_projection(name, id, consistency: :eventual)
#     case consistency
#     when :eventual
#       fetch_projection_data(name, id)
#     when :strong
#       # Wait for projection to be fully caught up
#       ensure_caught_up(name)
#       fetch_projection_data(name, id)
#     when :read_your_writes
#       # Require specific position (e.g., from command that wrote)
#       raise "required_position needed" unless block_given?
#       required_position = yield
#       wait_for_position(name, required_position)
#       fetch_projection_data(name, id)
#     end
#   end
#
#   def get_projection_status(name)
#     {
#       last_processed_position: @last_processed_position[name],
#       latest_event_position: get_latest_event_position,
#       lag: get_latest_event_position - @last_processed_position[name],
#       is_rebuilding: rebuilding?(name),
#       health: projection_healthy?(name) ? 'healthy' : 'lagging'
#     }
#   end
#
#   def rebuild_projection(name)
#     # Mark as rebuilding
#     set_rebuilding_flag(name)
#
#     begin
#       # ... rebuild logic
#     ensure
#       clear_rebuilding_flag(name)
#     end
#   end
#
#   def fetch_projection_data(name, id)
#     data = Rails.cache.read("projection:#{name}:#{id}")
#
#     # Include staleness information
#     {
#       data: data,
#       position: @last_processed_position[name],
#       lag: get_lag(name),
#       stale: get_lag(name) > acceptable_lag_threshold
#     }
#   end
# end
