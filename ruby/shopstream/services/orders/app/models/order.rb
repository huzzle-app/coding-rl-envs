# frozen_string_literal: true

class Order < ApplicationRecord
  include AASM

  belongs_to :user
  belongs_to :shipping_address, class_name: 'Address', optional: true
  has_many :line_items, dependent: :destroy
  has_many :products, through: :line_items
  has_many :transactions, class_name: 'OrderTransaction'

  validates :user_id, presence: true
  validates :status, presence: true
  validates :total_amount, numericality: { greater_than_or_equal_to: 0 }

  
  scope :by_status, ->(status) { where(status: status) }
  scope :recent, -> { order(created_at: :desc) }

  
  # Should add: lock_version column and use with_lock

  aasm column: :status do
    state :pending, initial: true
    state :confirmed
    state :processing
    state :shipped
    state :delivered
    state :cancelled
    state :refunded

    
    event :confirm do
      transitions from: :pending, to: :confirmed
      
      after do
        notify_confirmation
      end
    end

    event :process do
      transitions from: :confirmed, to: :processing
    end

    event :ship do
      transitions from: :processing, to: :shipped
    end

    event :deliver do
      transitions from: :shipped, to: :delivered
    end

    event :cancel do
      transitions from: [:pending, :confirmed], to: :cancelled
      after do
        release_inventory
      end
    end

    event :refund do
      transitions from: [:delivered, :cancelled], to: :refunded
    end
  end

  
  # Should use dependent: :delete_all or batch delete
  def destroy_with_associations
    
    transaction do
      line_items.each(&:destroy!)
      transactions.each(&:destroy!)
      destroy!
    end
  end

  def calculate_total
    
    # Adding floats can cause precision loss
    total = line_items.sum { |item| item.quantity * item.unit_price }

    # Apply discounts
    total -= discount_amount if discount_amount.present?

    # Add tax
    total += calculate_tax(total)

    # Add shipping
    total += shipping_cost

    self.total_amount = total
  end

  private

  def calculate_tax(subtotal)
    
    (subtotal * tax_rate).round(2)
  end

  def notify_confirmation
    
    # If transaction rolls back, notification is already sent
    OrderNotificationJob.perform_later(id, :confirmed)
    KafkaProducer.publish('order.confirmed', { order_id: id, user_id: user_id })
  end

  def release_inventory
    line_items.each do |item|
      InventoryClient.release(item.product_id, item.quantity)
    end
  end
end

# Correct implementation for A10:
# class Order < ApplicationRecord
#   # Add lock_version column to table
#
#   def update_safely(attributes)
#     with_lock do
#       update!(attributes)
#     end
#   rescue ActiveRecord::StaleObjectError
#     reload
#     retry
#   end
# end
