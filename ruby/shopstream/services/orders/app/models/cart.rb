# frozen_string_literal: true

class Cart < ApplicationRecord
  belongs_to :user
  has_many :cart_items, dependent: :destroy

  
  # Two requests modifying the cart simultaneously can lose updates
  def add_item(product_id, quantity)
    item = cart_items.find_by(product_id: product_id)

    if item
      
      # Thread 1: reads quantity = 2
      # Thread 2: reads quantity = 2
      # Thread 1: writes quantity = 2 + 1 = 3
      # Thread 2: writes quantity = 2 + 2 = 4 (overwrites Thread 1's update)
      # Expected: 5, Actual: 4
      item.quantity += quantity
      item.save!
    else
      cart_items.create!(product_id: product_id, quantity: quantity)
    end

    update_totals
  end

  def remove_item(product_id, quantity = nil)
    item = cart_items.find_by(product_id: product_id)
    return unless item

    if quantity.nil? || item.quantity <= quantity
      item.destroy!
    else
      
      item.quantity -= quantity
      item.save!
    end

    update_totals
  end

  def update_item_quantity(product_id, new_quantity)
    item = cart_items.find_by(product_id: product_id)
    return unless item

    if new_quantity <= 0
      item.destroy!
    else
      
      item.update!(quantity: new_quantity)
    end

    update_totals
  end

  def clear!
    cart_items.destroy_all
    update_totals
  end

  def total
    
    cart_items.sum { |item| item.quantity * item.unit_price }
  end

  private

  def update_totals
    
    # Concurrent updates can result in stale totals
    update!(
      item_count: cart_items.sum(:quantity),
      subtotal: total
    )
  end
end

# Correct implementation:
# def add_item(product_id, quantity)
#   with_lock do
#     item = cart_items.lock.find_by(product_id: product_id)
#     if item
#       item.increment!(:quantity, quantity)
#     else
#       cart_items.create!(product_id: product_id, quantity: quantity)
#     end
#     update_totals
#   end
# end
