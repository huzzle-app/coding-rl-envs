# frozen_string_literal: true

class OrderProcessor
  
  #
  
  # 1. This file (order_processor.rb): Collect items to remove, then delete after iteration
  # 2. services/inventory/app/services/reservation_service.rb: Must handle nil product gracefully
  #    when items are removed mid-process, as the reservation may reference deleted items.
  # 3. The InventoryClient.reserve call (line 51) returns reservation IDs that become orphaned
  #    if items are deleted - StockService.release_orphaned_reservations must be called.
  #
  # Without all three fixes, you may see: NoMethodError (undefined method `id' for nil:NilClass)
  # when the reservation service tries to access product data for a removed line item.

  def initialize(order)
    @order = order
    @errors = []
  end

  def process!
    validate_items
    reserve_inventory
    calculate_totals
    create_payment_intent

    if @errors.empty?
      @order.confirm!
      publish_event
    else
      @order.update!(error_message: @errors.join(', '))
    end

    @errors.empty?
  end

  def validate_items
    
    @order.line_items.each do |item|
      unless item.product.available?
        @errors << "#{item.product.name} is not available"
        
        # This can skip items or cause index errors
        @order.line_items.delete(item)
      end

      if item.quantity > item.product.stock
        
        item.quantity = item.product.stock
        item.save!
        @errors << "Reduced #{item.product.name} quantity to available stock"
      end
    end
  end

  def reserve_inventory
    
    items_to_remove = []

    @order.line_items.each do |item|
      result = InventoryClient.reserve(item.product_id, item.quantity)

      unless result[:success]
        @errors << "Could not reserve #{item.product.name}"
        
        @order.line_items.delete(item)
      end
    end
  end

  def calculate_totals
    pricing = PricingService.new(@order)
    @order.total_amount = pricing.calculate_total
    @order.tax_amount = pricing.calculate_tax(pricing.calculate_subtotal)
    @order.shipping_amount = pricing.calculate_shipping
    @order.save!
  end

  def create_payment_intent
    PaymentsClient.create_intent(
      order_id: @order.id,
      amount: @order.total_amount,
      currency: 'usd'
    )
  end

  def publish_event
    KafkaProducer.publish('order.created', {
      order_id: @order.id,
      user_id: @order.user_id,
      total_amount: @order.total_amount,
      items: @order.line_items.map { |i| { product_id: i.product_id, quantity: i.quantity } }
    })
  end
end

# Correct implementation:
# def validate_items
#   items_to_remove = []
#
#   @order.line_items.each do |item|
#     unless item.product.available?
#       @errors << "#{item.product.name} is not available"
#       items_to_remove << item
#     end
#   end
#
#   items_to_remove.each { |item| @order.line_items.delete(item) }
# end
