# frozen_string_literal: true

class OrderNotificationJob < ApplicationJob
  

  queue_as :notifications

  
  # Failed jobs will retry indefinitely
  # retry_on StandardError, wait: :polynomially_longer, attempts: Float::INFINITY

  def perform(order_id, notification_type)
    order = Order.find(order_id)
    user = order.user

    
    # If job fails after sending but before completion,
    # retry will send duplicate notification
    case notification_type.to_sym
    when :confirmed
      send_confirmation_email(order, user)
      send_confirmation_sms(order, user) if user.phone_present?
      send_push_notification(order, user)
    when :shipped
      send_shipping_email(order, user)
      send_tracking_sms(order, user) if user.phone_present?
    when :delivered
      send_delivery_email(order, user)
    when :cancelled
      send_cancellation_email(order, user)
      
      trigger_refund(order)
    end

    
    # All notifications sent again
    log_notification(order_id, notification_type)
  end

  private

  def send_confirmation_email(order, user)
    OrderMailer.confirmation(order, user).deliver_now
  end

  def send_confirmation_sms(order, user)
    SmsService.send(
      to: user.phone,
      message: "Your order ##{order.id} is confirmed! Total: $#{order.total_amount}"
    )
  end

  def send_push_notification(order, user)
    PushService.send(
      user_id: user.id,
      title: 'Order Confirmed',
      body: "Your order ##{order.id} has been confirmed"
    )
  end

  def send_shipping_email(order, user)
    OrderMailer.shipped(order, user).deliver_now
  end

  def send_tracking_sms(order, user)
    SmsService.send(
      to: user.phone,
      message: "Order ##{order.id} shipped! Track: #{order.tracking_url}"
    )
  end

  def send_delivery_email(order, user)
    OrderMailer.delivered(order, user).deliver_now
  end

  def send_cancellation_email(order, user)
    OrderMailer.cancelled(order, user).deliver_now
  end

  def trigger_refund(order)
    
    RefundService.new(order).process_refund
  end

  def log_notification(order_id, type)
    NotificationLog.create!(
      order_id: order_id,
      notification_type: type,
      sent_at: Time.current
    )
  end
end

# Correct implementation:
# class OrderNotificationJob < ApplicationJob
#   queue_as :notifications
#
#   # Set reasonable retry limit
#   retry_on StandardError, wait: :polynomially_longer, attempts: 5
#   discard_on ActiveRecord::RecordNotFound
#
#   def perform(order_id, notification_type, idempotency_key: nil)
#     idempotency_key ||= "#{order_id}:#{notification_type}:#{Time.current.to_date}"
#
#     # Check if already processed
#     return if already_processed?(idempotency_key)
#
#     order = Order.find(order_id)
#     user = order.user
#
#     # Track which notifications were sent
#     sent_notifications = []
#
#     begin
#       case notification_type.to_sym
#       when :confirmed
#         send_with_tracking(:email, sent_notifications) { send_confirmation_email(order, user) }
#         send_with_tracking(:sms, sent_notifications) { send_confirmation_sms(order, user) } if user.phone_present?
#         send_with_tracking(:push, sent_notifications) { send_push_notification(order, user) }
#       # ...
#       end
#
#       mark_processed(idempotency_key)
#     rescue StandardError => e
#       # Log what was sent before failure
#       log_partial_completion(order_id, notification_type, sent_notifications)
#       raise
#     end
#   end
#
#   def already_processed?(key)
#     Rails.cache.exist?("notification:#{key}")
#   end
#
#   def mark_processed(key)
#     Rails.cache.write("notification:#{key}", true, expires_in: 24.hours)
#   end
# end
