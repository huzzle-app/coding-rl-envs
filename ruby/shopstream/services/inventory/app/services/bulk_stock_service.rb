# frozen_string_literal: true

class BulkStockService
  
  # Long-running updates lock rows for too long, causing timeouts

  def bulk_adjust(adjustments)
    
    # If many adjustments, later ones timeout waiting for locks

    Product.transaction do
      adjustments.each do |adjustment|
        product = Product.lock.find(adjustment[:product_id])

        
        # With 1000 adjustments, early locks held for entire batch
        product.stock += adjustment[:quantity]
        product.save!

        StockMovement.create!(
          product_id: adjustment[:product_id],
          quantity: adjustment[:quantity],
          movement_type: 'adjustment',
          reason: adjustment[:reason]
        )
      end
    end
  end

  def sync_all_warehouses(product_id)
    product = Product.find(product_id)

    
    Product.transaction do
      product.warehouse_locations.lock.each do |location|
        # Long operation while holding lock
        actual_count = count_physical_stock(location)
        difference = actual_count - location.quantity

        if difference != 0
          location.update!(quantity: actual_count)
          record_adjustment(location, difference)
        end
      end
    end
  end

  def transfer_between_warehouses(product_id, from_warehouse_id, to_warehouse_id, quantity)
    Product.transaction do
      
      # If another process transfers to_warehouse -> from_warehouse,
      # deadlock can occur
      from_location = WarehouseLocation.lock.find_by!(
        product_id: product_id,
        warehouse_id: from_warehouse_id
      )

      to_location = WarehouseLocation.lock.find_or_create_by!(
        product_id: product_id,
        warehouse_id: to_warehouse_id
      )

      raise 'Insufficient stock' if from_location.quantity < quantity

      from_location.decrement!(:quantity, quantity)
      to_location.increment!(:quantity, quantity)
    end
  end

  private

  def count_physical_stock(location)
    # Simulated physical count
    location.quantity + rand(-5..5)
  end

  def record_adjustment(location, difference)
    StockMovement.create!(
      product_id: location.product_id,
      warehouse_id: location.warehouse_id,
      quantity: difference,
      movement_type: 'adjustment',
      reason: 'Inventory sync'
    )
  end
end

# Correct implementation:
# def bulk_adjust(adjustments)
#   # Batch updates without long-held locks
#   adjustments.each_slice(100) do |batch|
#     Product.transaction do
#       product_ids = batch.map { |a| a[:product_id] }
#
#       # Lock all needed products at once
#       products = Product.where(id: product_ids).lock.index_by(&:id)
#
#       batch.each do |adjustment|
#         product = products[adjustment[:product_id]]
#         product.stock += adjustment[:quantity]
#       end
#
#       # Bulk save
#       Product.import(products.values, on_duplicate_key_update: [:stock])
#     end
#   end
# end
#
# def transfer_between_warehouses(product_id, from_warehouse_id, to_warehouse_id, quantity)
#   # Consistent lock ordering prevents deadlock
#   ids = [from_warehouse_id, to_warehouse_id].sort
#
#   Product.transaction do
#     locations = WarehouseLocation.where(
#       product_id: product_id,
#       warehouse_id: ids
#     ).lock.order(:warehouse_id)
#
#     # Process in consistent order
#     # ...
#   end
# end
