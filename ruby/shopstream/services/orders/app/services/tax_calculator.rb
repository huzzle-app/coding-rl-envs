# frozen_string_literal: true

class TaxCalculator
  

  TAX_RATES = {
    'US' => {
      'CA' => 0.0725,
      'NY' => 0.08,
      'TX' => 0.0625,
      'WA' => 0.065,
      'default' => 0.05
    },
    'CA' => { 'default' => 0.05 },
    'UK' => { 'default' => 0.20 },
    'default' => 0.0
  }.freeze

  def initialize(order)
    @order = order
  end

  def calculate
    
    # Line-by-line rounding vs. total rounding

    # Method 1: Round each line item (causes compounding errors)
    line_item_tax = calculate_per_line_item

    # Method 2: Round only the final total (correct)
    # total_tax = calculate_on_total

    
    line_item_tax
  end

  def calculate_per_line_item
    
    # Example: 3 items at $9.99 with 8% tax
    # Per-line: round(9.99 * 0.08) * 3 = 0.80 * 3 = $2.40
    # On total: round(29.97 * 0.08) = round(2.3976) = $2.40
    # But with certain values, they diverge

    @order.line_items.sum do |item|
      line_subtotal = item.quantity * item.unit_price
      tax_rate = get_tax_rate(item)

      
      (line_subtotal * tax_rate).round(2)
    end
  end

  def calculate_on_total
    subtotal = @order.line_items.sum { |item| item.quantity * item.unit_price }
    tax_rate = get_tax_rate(@order.line_items.first)

    # Correct: round only the final amount
    (subtotal * tax_rate).round(2)
  end

  def tax_breakdown
    breakdown = {}

    @order.line_items.each do |item|
      rate_key = get_rate_key(item)
      rate = get_tax_rate(item)

      breakdown[rate_key] ||= { rate: rate, amount: 0.0 }

      
      line_tax = (item.quantity * item.unit_price * rate).round(2)
      breakdown[rate_key][:amount] += line_tax
    end

    breakdown
  end

  private

  def get_tax_rate(item)
    country = @order.shipping_address&.country || 'default'
    state = @order.shipping_address&.state || 'default'

    country_rates = TAX_RATES[country] || TAX_RATES['default']

    if country_rates.is_a?(Hash)
      country_rates[state] || country_rates['default'] || 0.0
    else
      country_rates
    end
  end

  def get_rate_key(item)
    country = @order.shipping_address&.country || 'unknown'
    state = @order.shipping_address&.state

    state ? "#{country}-#{state}" : country
  end
end

# Correct implementation:
# def calculate
#   subtotal = BigDecimal('0')
#
#   @order.line_items.each do |item|
#     line_subtotal = BigDecimal(item.quantity.to_s) * BigDecimal(item.unit_price.to_s)
#     subtotal += line_subtotal
#   end
#
#   tax_rate = BigDecimal(get_tax_rate(@order.line_items.first).to_s)
#   (subtotal * tax_rate).round(2).to_f
# end
