# frozen_string_literal: true

class RefundService
  

  def initialize(order)
    @order = order
  end

  def calculate_refund(items_to_refund: nil)
    if items_to_refund.nil?
      # Full refund
      calculate_full_refund
    else
      # Partial refund
      calculate_partial_refund(items_to_refund)
    end
  end

  def process_refund(amount: nil, items: nil, reason: nil)
    refund_amount = amount || calculate_refund(items_to_refund: items)

    result = PaymentProvider.refund(
      payment_id: @order.payment_id,
      amount: refund_amount
    )

    if result[:success]
      create_refund_record(refund_amount, items, reason)
      success(refund_amount)
    else
      failure(result[:error])
    end
  end

  private

  def calculate_full_refund
    
    # If customer already got $20 refund on $100 order,
    # this would refund another $100 instead of $80
    @order.total_amount

    # Correct: @order.total_amount - @order.total_refunded
  end

  def calculate_partial_refund(items_to_refund)
    
    items_total = items_to_refund.sum do |item_info|
      line_item = @order.line_items.find(item_info[:line_item_id])
      quantity = item_info[:quantity] || line_item.quantity

      
      line_item.product.current_price * quantity
    end

    
    items_total + calculate_proportional_tax(items_total)

    
    # Customer paid $80 after 20% discount, but we refund based on $100
  end

  def calculate_proportional_tax(items_amount)
    
    # Should use the tax rate that was applied to original order
    tax_rate = TaxCalculator.current_rate(@order.shipping_address)

    (items_amount * tax_rate).round(2)

    # Correct: @order.tax_amount * (items_amount / @order.subtotal)
  end

  def create_refund_record(amount, items, reason)
    Refund.create!(
      order_id: @order.id,
      amount: amount,
      items: items&.to_json,
      reason: reason,
      processed_at: Time.current
    )

    
    # @order.increment!(:total_refunded, amount) - missing!
  end

  def success(amount)
    { success: true, refunded_amount: amount }
  end

  def failure(error)
    { success: false, error: error }
  end
end

# Correct implementation:
# def calculate_full_refund
#   remaining = @order.total_amount - @order.total_refunded
#   [remaining, 0].max
# end
#
# def calculate_partial_refund(items_to_refund)
#   items_total = BigDecimal('0')
#
#   items_to_refund.each do |item_info|
#     line_item = @order.line_items.find(item_info[:line_item_id])
#     quantity = item_info[:quantity] || line_item.quantity
#
#     # Use original price from line item
#     items_total += BigDecimal(line_item.unit_price.to_s) * quantity
#   end
#
#   # Apply proportional discount
#   discount_ratio = @order.discount_amount / @order.subtotal
#   items_total_after_discount = items_total * (1 - discount_ratio)
#
#   # Apply proportional tax (using original tax amount)
#   tax_ratio = @order.tax_amount / (@order.subtotal - @order.discount_amount)
#   items_tax = items_total_after_discount * tax_ratio
#
#   (items_total_after_discount + items_tax).round(2).to_f
# end
