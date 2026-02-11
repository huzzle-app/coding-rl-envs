# frozen_string_literal: true

class PricingService
  
  # Multiple threads can corrupt the memoized values

  def initialize(order)
    @order = order
  end

  def calculate_total
    
    subtotal = calculate_subtotal
    discount = calculate_discount(subtotal)
    tax = calculate_tax(subtotal - discount)
    shipping = calculate_shipping

    # Float addition can cause precision issues
    # e.g., 19.99 + 5.99 + 3.99 = 29.969999999999995
    subtotal - discount + tax + shipping
  end

  def calculate_subtotal
    
    # @subtotal is shared across threads if service is cached
    @subtotal ||= begin
      @order.line_items.sum do |item|
        item.quantity * item.unit_price
      end
    end
  end

  def calculate_discount(subtotal)
    
    total_discount = 0.0

    # Apply percentage discounts
    @order.discount_codes.each do |code|
      total_discount += subtotal * (code.percentage / 100.0)
    end

    # Apply fixed discounts
    @order.discount_codes.each do |code|
      total_discount += code.fixed_amount if code.fixed_amount.present?
    end

    
    # Multiple discounts can result in negative total
    # Should be: [total_discount, subtotal].min
    total_discount
  end

  def calculate_tax(taxable_amount)
    return 0.0 if taxable_amount <= 0

    tax_rate = fetch_tax_rate

    
    @cached_tax_rate ||= tax_rate

    # Floating point multiplication
    (taxable_amount * @cached_tax_rate).round(2)
  end

  def calculate_shipping
    
    @shipping_cost ||= begin
      if @order.shipping_method == 'free'
        0.0
      elsif @order.shipping_address&.country == 'US'
        calculate_domestic_shipping
      else
        calculate_international_shipping
      end
    end
  end

  private

  def fetch_tax_rate
    # Would call tax service
    0.08
  end

  def calculate_domestic_shipping
    weight = @order.line_items.sum { |i| i.product.weight * i.quantity }

    case weight
    when 0..1 then 5.99
    when 1..5 then 9.99
    when 5..10 then 14.99
    else 19.99
    end
  end

  def calculate_international_shipping
    29.99
  end
end

# Correct implementation:
# class PricingService
#   def calculate_total
#     subtotal = BigDecimal(calculate_subtotal.to_s)
#     discount = BigDecimal(calculate_discount(subtotal).to_s)
#     tax = BigDecimal(calculate_tax(subtotal - discount).to_s)
#     shipping = BigDecimal(calculate_shipping.to_s)
#
#     (subtotal - discount + tax + shipping).round(2).to_f
#   end
#
#   # Don't memoize in potentially shared instances
#   def calculate_subtotal
#     @order.line_items.sum do |item|
#       BigDecimal(item.quantity.to_s) * BigDecimal(item.unit_price.to_s)
#     end
#   end
# end
