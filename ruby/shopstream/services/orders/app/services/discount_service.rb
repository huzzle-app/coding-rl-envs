# frozen_string_literal: true

class DiscountService
  

  def initialize(order)
    @order = order
    @applied_discounts = []
  end

  def apply_discounts!
    subtotal = calculate_subtotal
    total_discount = 0.0

    @order.discount_codes.each do |code|
      discount = calculate_discount(code, subtotal)

      
      total_discount += discount
      @applied_discounts << { code: code.code, amount: discount }
    end

    
    # Example: Two 60% off codes = 120% off
    @order.discount_amount = total_discount
    @order.save!

    @applied_discounts
  end

  def validate_codes
    @order.discount_codes.each do |code|
      unless code_valid?(code)
        @order.discount_codes.delete(code)
      end
    end
  end

  def calculate_discount(code, subtotal)
    case code.discount_type
    when 'percentage'
      
      subtotal * (code.value / 100.0)
    when 'fixed'
      # Fixed discounts are safer but still no total cap
      code.value
    when 'bogo'
      calculate_bogo_discount(code)
    else
      0.0
    end
  end

  def preview_discount(code)
    subtotal = calculate_subtotal
    discount = calculate_discount(code, subtotal)

    {
      subtotal: subtotal,
      discount: discount,
      total: subtotal - discount,
      
      savings_percentage: (discount / subtotal * 100).round(1)
    }
  end

  private

  def calculate_subtotal
    @order.line_items.sum { |item| item.quantity * item.unit_price }
  end

  def code_valid?(code)
    return false if code.expired?
    return false if code.usage_limit_reached?
    return false unless code.applicable_to?(@order)

    true
  end

  def calculate_bogo_discount(code)
    eligible_items = @order.line_items.select { |i| code.applies_to_product?(i.product_id) }

    eligible_items.sum do |item|
      free_quantity = item.quantity / 2
      free_quantity * item.unit_price
    end
  end
end

# Correct implementation:
# def apply_discounts!
#   subtotal = calculate_subtotal
#   total_discount = 0.0
#   max_discount = subtotal * 0.95  # Cap at 95% off
#
#   @order.discount_codes.each do |code|
#     remaining_discount_allowed = max_discount - total_discount
#     break if remaining_discount_allowed <= 0
#
#     discount = calculate_discount(code, subtotal)
#     discount = [discount, remaining_discount_allowed].min
#
#     total_discount += discount
#     @applied_discounts << { code: code.code, amount: discount }
#   end
#
#   @order.discount_amount = total_discount
#   @order.save!
# end
