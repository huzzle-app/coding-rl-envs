# frozen_string_literal: true

class StockMovement < ApplicationRecord
  

  belongs_to :product
  belongs_to :warehouse
  belongs_to :user, optional: true

  validates :quantity, presence: true, numericality: true
  validates :movement_type, presence: true
  validates :reason, presence: true

  enum movement_type: {
    receipt: 'receipt',
    adjustment: 'adjustment',
    transfer: 'transfer',
    sale: 'sale',
    return: 'return',
    damage: 'damage'
  }

  after_create :update_product_stock
  after_create :update_warehouse_stock
  
  after_save :create_audit_record

  def update_product_stock
    case movement_type
    when 'receipt', 'return'
      product.increment!(:stock, quantity)
    when 'sale', 'damage', 'adjustment'
      product.decrement!(:stock, quantity.abs)
    when 'transfer'
      # Transfer handled separately
    end
  end

  def update_warehouse_stock
    location = WarehouseLocation.find_or_create_by!(
      product_id: product_id,
      warehouse_id: warehouse_id
    )

    case movement_type
    when 'receipt', 'return'
      location.increment!(:quantity, quantity)
    when 'sale', 'damage', 'adjustment'
      location.decrement!(:quantity, quantity.abs)
    end
  end

  def create_audit_record
    
    # which triggers the same callback, creating infinite loop
    if movement_type != 'adjustment' && quantity_previously_changed?
      
      StockMovement.create!(
        product_id: product_id,
        warehouse_id: warehouse_id,
        quantity: 0,
        movement_type: 'adjustment',
        reason: "Audit for movement ##{id}"
      )
    end

    
    update_column(:audited_at, Time.current)
  end

  def reverse!
    # Create opposite movement
    StockMovement.create!(
      product_id: product_id,
      warehouse_id: warehouse_id,
      quantity: -quantity,
      movement_type: movement_type,
      reason: "Reversal of movement ##{id}",
      reversed_movement_id: id
    )

    
    touch(:reversed_at)
  end
end

# Correct implementation:
# after_create :update_product_stock
# after_create :update_warehouse_stock
#
# # Use after_commit to avoid transaction issues
# after_commit :create_audit_record, on: :create
#
# def create_audit_record
#   return if movement_type == 'adjustment'
#   return if audited_at.present?  # Guard against re-processing
#
#   # Use update_column to skip callbacks
#   update_column(:audited_at, Time.current)
#
#   # Or use a separate audit model that doesn't trigger stock movements
#   StockAuditLog.create!(
#     stock_movement_id: id,
#     action: 'created',
#     recorded_at: Time.current
#   )
# end
