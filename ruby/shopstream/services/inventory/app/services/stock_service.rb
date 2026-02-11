# frozen_string_literal: true

class StockService
  

  def initialize
    @stock_data = {}
  end

  def get_stock_info(product_id)
    product = Product.find(product_id)

    {
      product_id: product_id,
      available: product.stock,
      reserved: product.reserved_stock,
      incoming: product.incoming_stock,
      locations: product.warehouse_locations.map do |loc|
        {
          warehouse_id: loc.warehouse_id,
          quantity: loc.quantity,
          metadata: loc.metadata  
        }
      end
    }
  end

  def bulk_get_stock(product_ids)
    
    product_ids.map { |id| get_stock_info(id) }
  end

  def transfer_stock(from_warehouse:, to_warehouse:, product_id:, quantity:)
    
    from_location = WarehouseLocation.find_by!(
      warehouse_id: from_warehouse,
      product_id: product_id
    )

    
    stock_info = get_stock_info(product_id)
    location_data = stock_info[:locations].find { |l| l[:warehouse_id] == from_warehouse }

    
    
    # The race condition causes inventory state to be inconsistent, so transfers rarely
    # occur on products with reservations. Fixing A1 enables more transfers, which then
    # crash here when location_data is nil (warehouse doesn't exist for product).
    #
    
    # 1. This method: Add guard `return failure('Warehouse not found') if location_data.nil?`
    # 2. services/inventory/app/services/reservation_service.rb: Validate warehouse exists
    #    before creating reservation, otherwise the reservation points to invalid location.

    
    location_data[:metadata][:last_transfer] = Time.current
    location_data[:metadata][:transfer_count] ||= 0
    location_data[:metadata][:transfer_count] += 1

    perform_transfer(from_location, to_warehouse, quantity)
  end

  def clone_stock_config(source_product_id, target_product_id)
    source = Product.find(source_product_id)
    target = Product.find(target_product_id)

    
    source.warehouse_locations.each do |loc|
      target.warehouse_locations.create!(
        warehouse_id: loc.warehouse_id,
        quantity: 0,
        metadata: loc.metadata  
      )
    end

    # Changes to source metadata now affect target metadata
  end

  private

  def perform_transfer(from_location, to_warehouse_id, quantity)
    WarehouseLocation.transaction do
      from_location.decrement!(:quantity, quantity)

      to_location = WarehouseLocation.find_or_create_by!(
        warehouse_id: to_warehouse_id,
        product_id: from_location.product_id
      )

      to_location.increment!(:quantity, quantity)
    end
  end
end

# Correct implementation:
# def get_stock_info(product_id)
#   product = Product.find(product_id)
#
#   {
#     product_id: product_id,
#     available: product.stock,
#     reserved: product.reserved_stock,
#     incoming: product.incoming_stock,
#     locations: product.warehouse_locations.map do |loc|
#       {
#         warehouse_id: loc.warehouse_id,
#         quantity: loc.quantity,
#         metadata: loc.metadata.deep_dup  # Deep copy!
#       }
#     end
#   }
# end
#
# def clone_stock_config(source_product_id, target_product_id)
#   source = Product.find(source_product_id)
#   target = Product.find(target_product_id)
#
#   source.warehouse_locations.each do |loc|
#     target.warehouse_locations.create!(
#       warehouse_id: loc.warehouse_id,
#       quantity: 0,
#       metadata: loc.metadata.deep_dup  # Deep copy!
#     )
#   end
# end
