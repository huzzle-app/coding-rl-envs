# frozen_string_literal: true

class OrderSaga
  
  # If payment fails after inventory reserved, inventory isn't released

  STEPS = %i[reserve_inventory process_payment create_shipment send_confirmation].freeze

  def initialize(order)
    @order = order
    @completed_steps = []
    @compensation_actions = {
      reserve_inventory: :release_inventory,
      process_payment: :refund_payment,
      create_shipment: :cancel_shipment,
      send_confirmation: :send_cancellation
    }
  end

  def execute!
    STEPS.each do |step|
      result = send(step)

      if result[:success]
        @completed_steps << step
      else
        
        # Should call compensate! here
        @order.update!(
          status: 'failed',
          error_message: result[:error]
        )

        
        # Inventory remains reserved, payment may be partially processed
        return false
      end
    end

    @order.update!(status: 'completed')
    true
  end

  def compensate!
    
    @completed_steps.reverse.each do |step|
      compensation = @compensation_actions[step]
      send(compensation) if compensation
    end
  end

  private

  def reserve_inventory
    results = @order.line_items.map do |item|
      InventoryClient.reserve(item.product_id, item.quantity)
    end

    if results.all? { |r| r[:success] }
      { success: true }
    else
      { success: false, error: 'Inventory reservation failed' }
    end
  end

  def release_inventory
    @order.line_items.each do |item|
      InventoryClient.release(item.product_id, item.quantity)
    end
  end

  def process_payment
    result = PaymentsClient.charge(
      order_id: @order.id,
      amount: @order.total_amount,
      payment_method: @order.payment_method_id
    )

    if result[:success]
      @order.update!(payment_id: result[:payment_id])
      { success: true }
    else
      { success: false, error: result[:error] }
    end
  end

  def refund_payment
    PaymentsClient.refund(@order.payment_id) if @order.payment_id
  end

  def create_shipment
    result = ShippingClient.create_shipment(
      order_id: @order.id,
      address: @order.shipping_address
    )

    if result[:success]
      @order.update!(shipment_id: result[:shipment_id])
      { success: true }
    else
      { success: false, error: result[:error] }
    end
  end

  def cancel_shipment
    ShippingClient.cancel(@order.shipment_id) if @order.shipment_id
  end

  def send_confirmation
    OrderNotificationJob.perform_later(@order.id, :confirmed)
    { success: true }
  end

  def send_cancellation
    OrderNotificationJob.perform_later(@order.id, :cancelled)
  end
end

# Correct implementation:
# def execute!
#   STEPS.each do |step|
#     result = send(step)
#
#     if result[:success]
#       @completed_steps << step
#     else
#       compensate!  # Call compensation on failure
#       @order.update!(status: 'failed', error_message: result[:error])
#       return false
#     end
#   end
#
#   @order.update!(status: 'completed')
#   true
# rescue StandardError => e
#   compensate!  # Also compensate on exceptions
#   raise
# end
