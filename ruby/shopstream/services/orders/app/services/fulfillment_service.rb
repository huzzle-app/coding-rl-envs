# frozen_string_literal: true

class FulfillmentService
  
  # If one service is down, entire fulfillment fails without proper fallback

  def initialize(order)
    @order = order
    @results = {}
  end

  def fulfill!
    
    # If inventory service is down, payment fails, shipping fails, etc.

    # Step 1: Verify inventory (calls Inventory service)
    inventory_result = verify_inventory
    return failure('Inventory verification failed') unless inventory_result[:success]

    # Step 2: Process payment (calls Payments service)
    payment_result = process_payment
    return failure('Payment processing failed') unless payment_result[:success]

    # Step 3: Create shipment (calls Shipping service)
    
    # No compensation or retry mechanism
    shipment_result = create_shipment
    return failure('Shipment creation failed') unless shipment_result[:success]

    # Step 4: Send notifications (calls Notifications service)
    
    # But payment and shipment are already done
    notification_result = send_notifications
    return failure('Notification failed') unless notification_result[:success]

    success
  end

  private

  def verify_inventory
    
    # If inventory service hangs, this hangs forever
    @order.line_items.each do |item|
      result = InventoryClient.check_stock(item.product_id)

      
      return { success: false, error: 'Service unavailable' } if result.nil?
      return { success: false, error: 'Insufficient stock' } if result[:stock] < item.quantity
    end

    { success: true }
  rescue => e
    
    { success: false, error: e.message }
  end

  def process_payment
    result = PaymentsClient.charge(
      order_id: @order.id,
      amount: @order.total_amount
    )

    @results[:payment] = result
    result
  rescue => e
    { success: false, error: e.message }
  end

  def create_shipment
    result = ShippingClient.create(
      order_id: @order.id,
      address: @order.shipping_address,
      items: @order.line_items.map(&:to_shipment_item)
    )

    @results[:shipment] = result
    result
  rescue => e
    
    # No automatic refund or retry
    { success: false, error: e.message }
  end

  def send_notifications
    NotificationsClient.send_order_confirmation(@order.id)
    { success: true }
  rescue => e
    
    # Returning failure makes it seem like order failed
    { success: false, error: e.message }
  end

  def success
    @order.update!(status: 'fulfilled')
    { success: true, results: @results }
  end

  def failure(message)
    @order.update!(status: 'failed', error_message: message)
    
    { success: false, error: message, results: @results }
  end
end

# Correct implementation:
# def fulfill!
#   with_circuit_breaker do
#     result = {}
#
#     result[:inventory] = with_retry { verify_inventory }
#     return compensate_and_fail('Inventory') unless result[:inventory][:success]
#
#     result[:payment] = with_retry { process_payment }
#     unless result[:payment][:success]
#       release_inventory
#       return failure('Payment failed')
#     end
#
#     result[:shipment] = with_retry { create_shipment }
#     unless result[:shipment][:success]
#       # Shipment can be retried later
#       schedule_shipment_retry(@order.id)
#     end
#
#     # Notifications are fire-and-forget
#     NotificationJob.perform_later(@order.id)
#
#     success
#   end
# end
