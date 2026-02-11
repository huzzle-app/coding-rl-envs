# frozen_string_literal: true

class EventReplayService
  

  def initialize(product_id)
    @product_id = product_id
    @product = Product.find(product_id)
  end

  def replay_from(from_version:)
    events = EventStore.read("product-#{@product_id}", from_version: from_version)

    events.each do |event|
      apply_event(event)
    end
  end

  def rebuild_state
    # Reset to initial state
    @product.update!(
      stock: 0,
      reserved_stock: 0,
      total_sold: 0
    )

    
    # If some events were already applied, they get applied again
    events = EventStore.read("product-#{@product_id}")

    events.each do |event|
      
      apply_event(event)
    end
  end

  private

  def apply_event(event)
    data = JSON.parse(event['data'])

    case event['event_type']
    when 'stock_received'
      
      @product.increment!(:stock, data['quantity'])

    when 'stock_sold'
      
      @product.decrement!(:stock, data['quantity'])
      @product.increment!(:total_sold, data['quantity'])

    when 'stock_reserved'
      
      @product.increment!(:reserved_stock, data['quantity'])

    when 'stock_reservation_released'
      @product.decrement!(:reserved_stock, data['quantity'])

    when 'stock_adjusted'
      
      @product.increment!(:stock, data['adjustment'])
    end
  end
end

# Correct implementation using event versioning and idempotency:
# def rebuild_state
#   @product.update!(
#     stock: 0,
#     reserved_stock: 0,
#     total_sold: 0,
#     last_processed_event_version: 0
#   )
#
#   events = EventStore.read("product-#{@product_id}")
#
#   events.each do |event|
#     next if event['version'] <= @product.last_processed_event_version
#
#     apply_event(event)
#     @product.update!(last_processed_event_version: event['version'])
#   end
# end
#
# Or use snapshots:
# def rebuild_state
#   snapshot = ProductSnapshot.latest_for(@product_id)
#
#   if snapshot
#     @product.update!(snapshot.attributes)
#     from_version = snapshot.event_version
#   else
#     @product.reset_to_initial_state!
#     from_version = 0
#   end
#
#   events = EventStore.read("product-#{@product_id}", from_version: from_version)
#
#   events.each do |event|
#     apply_event(event)
#   end
#
#   ProductSnapshot.create_from(@product)
# end
