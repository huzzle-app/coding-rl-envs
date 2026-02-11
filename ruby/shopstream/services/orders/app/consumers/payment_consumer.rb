# frozen_string_literal: true

class PaymentConsumer
  
  # Reprocessed events cause duplicate state changes

  def initialize
    @consumer = ShopStream::KafkaConsumer.new(
      topics: ['payment.processed', 'payment.failed', 'payment.refunded'],
      group_id: 'orders-payment-consumer'
    )

    setup_handlers
  end

  def start
    @consumer.start
  end

  def stop
    @consumer.stop
  end

  private

  def setup_handlers
    @consumer.subscribe('payment.processed') do |event|
      handle_payment_processed(event)
    end

    @consumer.subscribe('payment.failed') do |event|
      handle_payment_failed(event)
    end

    @consumer.subscribe('payment.refunded') do |event|
      handle_payment_refunded(event)
    end
  end

  def handle_payment_processed(event)
    
    order_id = event[:order_id] || event['order_id']
    payment_id = event[:payment_id] || event['payment_id']

    order = Order.find(order_id)

    
    # If this event is reprocessed, order gets processed again
    # Could trigger duplicate shipment creation, duplicate notifications
    order.update!(
      payment_status: 'paid',
      payment_id: payment_id,
      paid_at: Time.current
    )

    
    # Replay of event creates duplicate shipment
    ShipmentService.create_shipment(order)

    
    OrderNotificationJob.perform_later(order.id, :confirmed)

    
    publish_order_paid(order)
  end

  def handle_payment_failed(event)
    order_id = event['order_id']
    error = event['error']

    order = Order.find(order_id)

    
    # Reprocessing sets failed status again, might override other status
    order.update!(
      payment_status: 'failed',
      payment_error: error
    )

    
    # Could double-release inventory
    order.line_items.each do |item|
      InventoryClient.release(item.product_id, item.quantity)
    end

    OrderNotificationJob.perform_later(order.id, :payment_failed)
  end

  def handle_payment_refunded(event)
    order_id = event['order_id']
    refund_amount = event['amount']

    order = Order.find(order_id)

    
    order.increment!(:total_refunded, refund_amount)

    if order.total_refunded >= order.total_amount
      order.update!(status: 'refunded')
    end

    OrderNotificationJob.perform_later(order.id, :refunded)
  end

  def publish_order_paid(order)
    ShopStream::KafkaProducer.publish('order.paid', {
      order_id: order.id,
      user_id: order.user_id,
      total: order.total_amount
    })
  end
end

# Correct implementation:
# class PaymentConsumer
#   def handle_payment_processed(event)
#     event_id = event['metadata']['event_id']
#
#     # Idempotency check using event ID
#     return if already_processed?(event_id)
#
#     order_id = event['order_id']
#     payment_id = event['payment_id']
#
#     Order.transaction do
#       order = Order.lock.find(order_id)
#
#       # Check current state - don't reprocess if already paid
#       return if order.payment_status == 'paid'
#
#       order.update!(
#         payment_status: 'paid',
#         payment_id: payment_id,
#         paid_at: Time.current
#       )
#
#       # Create shipment only if not exists
#       unless order.shipment.present?
#         ShipmentService.create_shipment(order)
#       end
#
#       # Mark event as processed before publishing
#       mark_processed(event_id)
#
#       # Notification job has its own idempotency
#       OrderNotificationJob.perform_later(
#         order.id,
#         :confirmed,
#         idempotency_key: "payment_confirmed_#{event_id}"
#       )
#     end
#   end
#
#   def already_processed?(event_id)
#     Redis.current.sismember('processed_events', event_id)
#   end
#
#   def mark_processed(event_id)
#     Redis.current.sadd('processed_events', event_id)
#     Redis.current.expire('processed_events', 7.days.to_i)
#   end
# end
