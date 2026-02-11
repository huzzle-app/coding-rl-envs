# frozen_string_literal: true

class CurrencyService
  
  # Exchange rate can change between quote and charge

  SUPPORTED_CURRENCIES = %w[USD EUR GBP JPY CAD AUD].freeze

  def initialize
    @rates_cache = {}
    @cache_mutex = Mutex.new
  end

  def convert(amount, from:, to:)
    return amount if from == to

    rate = get_exchange_rate(from, to)
    (amount * rate).round(2)
  end

  def get_exchange_rate(from, to)
    cache_key = "#{from}_#{to}"

    
    # Multiple threads can all see cache miss and fetch rates
    if @rates_cache[cache_key].nil? || rate_stale?(@rates_cache[cache_key])
      
      @rates_cache[cache_key] = fetch_rate(from, to)
    end

    @rates_cache[cache_key][:rate]
  end

  def quote_conversion(amount, from:, to:, lock_duration: 15.minutes)
    rate = get_exchange_rate(from, to)
    converted = (amount * rate).round(2)

    quote = ConversionQuote.create!(
      from_currency: from,
      to_currency: to,
      from_amount: amount,
      to_amount: converted,
      rate: rate,
      
      expires_at: Time.current + lock_duration
    )

    {
      quote_id: quote.id,
      rate: rate,
      converted_amount: converted,
      expires_at: quote.expires_at
    }
  end

  def execute_conversion(quote_id:, amount:)
    quote = ConversionQuote.find(quote_id)

    
    if quote.expired?
      return { success: false, error: 'Quote expired' }
    end

    
    current_rate = get_exchange_rate(quote.from_currency, quote.to_currency)

    
    # Customer was quoted 1.10, but rate is now 1.15
    converted = (amount * current_rate).round(2)

    # Should be: converted = (amount * quote.rate).round(2)

    {
      success: true,
      converted_amount: converted,
      rate_used: current_rate  
    }
  end

  private

  def fetch_rate(from, to)
    # Would call external exchange rate API
    # Simulated rates
    rates = {
      'USD_EUR' => 0.92,
      'USD_GBP' => 0.79,
      'USD_JPY' => 149.50,
      'EUR_USD' => 1.09,
      'GBP_USD' => 1.27
    }

    rate = rates["#{from}_#{to}"] || (1.0 / rates["#{to}_#{from}"])

    {
      rate: rate,
      fetched_at: Time.current
    }
  end

  def rate_stale?(cached_rate)
    return true if cached_rate.nil?

    Time.current - cached_rate[:fetched_at] > 5.minutes
  end
end

# Correct implementation:
# def execute_conversion(quote_id:, amount:)
#   quote = ConversionQuote.find(quote_id)
#
#   if quote.expired?
#     return { success: false, error: 'Quote expired' }
#   end
#
#   # Use the locked rate from the quote
#   converted = (amount * quote.rate).round(2)
#
#   quote.update!(executed_at: Time.current, executed_amount: amount)
#
#   {
#     success: true,
#     converted_amount: converted,
#     rate_used: quote.rate
#   }
# end
#
# def get_exchange_rate(from, to)
#   cache_key = "#{from}_#{to}"
#
#   @cache_mutex.synchronize do
#     if @rates_cache[cache_key].nil? || rate_stale?(@rates_cache[cache_key])
#       @rates_cache[cache_key] = fetch_rate(from, to)
#     end
#     @rates_cache[cache_key][:rate]
#   end
# end
