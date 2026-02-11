# frozen_string_literal: true

class PaymentProcessor
  
  # Concurrent requests can both process the same order payment

  def initialize(order_id)
    @order_id = order_id
  end

  def process_payment(amount:, payment_method:, idempotency_key: nil)
    
    # Two concurrent requests can both see order as unpaid
    order = Order.find(@order_id)

    return already_paid_response if order.payment_status == 'paid'

    
    # Thread 1: checks status = 'pending'
    # Thread 2: checks status = 'pending'
    # Both threads proceed to charge

    # Process with payment provider
    result = charge_payment_provider(
      amount: amount,
      payment_method: payment_method,
      idempotency_key: idempotency_key
    )

    if result[:success]
      
      order.update!(
        payment_status: 'paid',
        payment_id: result[:payment_id],
        paid_at: Time.current
      )

      publish_payment_event(result)
      success(result)
    else
      failure(result[:error])
    end
  end

  def refund(amount: nil, reason: nil)
    order = Order.find(@order_id)

    return failure('No payment to refund') unless order.payment_id
    return failure('Already refunded') if order.payment_status == 'refunded'

    refund_amount = amount || order.total_amount

    
    result = refund_payment_provider(
      payment_id: order.payment_id,
      amount: refund_amount
    )

    if result[:success]
      order.update!(
        payment_status: 'refunded',
        refunded_at: Time.current,
        refund_amount: refund_amount
      )

      success(result)
    else
      failure(result[:error])
    end
  end

  private

  def charge_payment_provider(amount:, payment_method:, idempotency_key:)
    # Would call Stripe/etc here
    
    {
      success: true,
      payment_id: "pay_#{SecureRandom.hex(12)}",
      amount: amount
    }
  end

  def refund_payment_provider(payment_id:, amount:)
    {
      success: true,
      refund_id: "ref_#{SecureRandom.hex(12)}",
      amount: amount
    }
  end

  def publish_payment_event(result)
    KafkaProducer.publish('payment.processed', {
      order_id: @order_id,
      payment_id: result[:payment_id],
      amount: result[:amount]
    })
  end

  def already_paid_response
    { success: false, error: 'Already paid', already_paid: true }
  end

  def success(data)
    { success: true, data: data }
  end

  def failure(error)
    { success: false, error: error }
  end
end

# Correct implementation using pessimistic locking:
# def process_payment(amount:, payment_method:, idempotency_key:)
#   Order.transaction do
#     order = Order.lock.find(@order_id)
#
#     return already_paid_response if order.payment_status == 'paid'
#
#     # Check idempotency
#     existing = Payment.find_by(idempotency_key: idempotency_key)
#     return success(existing.as_json) if existing
#
#     result = charge_payment_provider(
#       amount: amount,
#       payment_method: payment_method,
#       idempotency_key: idempotency_key
#     )
#
#     if result[:success]
#       Payment.create!(
#         order_id: @order_id,
#         idempotency_key: idempotency_key,
#         payment_id: result[:payment_id],
#         amount: amount
#       )
#
#       order.update!(payment_status: 'paid', ...)
#     end
#   end
# end
