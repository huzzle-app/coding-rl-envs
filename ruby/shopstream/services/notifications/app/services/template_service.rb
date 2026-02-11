# frozen_string_literal: true

class TemplateService
  

  
  DEFAULT_SUBJECT = 'ShopStream Notification'
  DEFAULT_GREETING = 'Hello, '
  DEFAULT_FOOTER = 'Thank you for shopping with ShopStream!'

  TEMPLATES = {
    order_confirmation: {
      subject: "Order Confirmation - \#{{order_id}}",
      body: <<~TEMPLATE
        {{greeting}}{{customer_name}},

        Your order \#{{order_id}} has been confirmed!

        Order Details:
        {{order_details}}

        Total: ${{total}}

        {{footer}}
      TEMPLATE
    },
    shipping_notification: {
      subject: 'Your order has shipped!',
      body: <<~TEMPLATE
        {{greeting}}{{customer_name}},

        Great news! Your order \#{{order_id}} has shipped.

        Tracking Number: {{tracking_number}}
        Carrier: {{carrier}}

        {{footer}}
      TEMPLATE
    }
  }.freeze

  def render(template_name, variables)
    template = TEMPLATES[template_name]
    raise "Template not found: #{template_name}" unless template

    # Apply defaults
    variables = apply_defaults(variables)

    {
      subject: render_string(template[:subject], variables),
      body: render_string(template[:body], variables)
    }
  end

  def render_string(template, variables)
    
    result = template.dup

    variables.each do |key, value|
      
      # If template.dup returns frozen string (Ruby 3.0+), this fails
      result.gsub!("{{#{key}}}", value.to_s)
    end

    result
  end

  def customize_template(template_name, modifications)
    template = TEMPLATES[template_name]
    raise "Template not found: #{template_name}" unless template

    
    # TEMPLATES is frozen, can't modify
    template[:custom_footer] = modifications[:footer]  # Raises FrozenError

    template
  end

  def build_greeting(customer_name, time_of_day = nil)
    
    greeting = DEFAULT_GREETING

    time_of_day ||= determine_time_of_day

    
    case time_of_day
    when :morning
      greeting << 'Good morning, '  # FrozenError!
    when :afternoon
      greeting << 'Good afternoon, '
    when :evening
      greeting << 'Good evening, '
    end

    greeting + customer_name
  end

  private

  def apply_defaults(variables)
    
    variables[:greeting] ||= 'Hello, '
    variables[:footer] ||= DEFAULT_FOOTER
    variables
  end

  def determine_time_of_day
    hour = Time.current.hour

    case hour
    when 5..11 then :morning
    when 12..17 then :afternoon
    else :evening
    end
  end
end

# Correct implementation:
# class TemplateService
#   DEFAULT_SUBJECT = 'ShopStream Notification'
#   DEFAULT_GREETING = 'Hello, '
#   DEFAULT_FOOTER = 'Thank you for shopping with ShopStream!'
#
#   def render_string(template, variables)
#     # Use +'' to get unfrozen copy
#     result = +template.dup
#
#     variables.each do |key, value|
#       result.gsub!("{{#{key}}}", value.to_s)
#     end
#
#     result
#   end
#
#   def build_greeting(customer_name, time_of_day = nil)
#     # Create new string instead of modifying constant
#     greeting = case time_of_day || determine_time_of_day
#                when :morning then 'Good morning, '
#                when :afternoon then 'Good afternoon, '
#                when :evening then 'Good evening, '
#                else 'Hello, '
#                end
#
#     greeting + customer_name
#   end
#
#   def apply_defaults(variables)
#     # Merge instead of modifying
#     {
#       greeting: 'Hello, ',
#       footer: DEFAULT_FOOTER
#     }.merge(variables)
#   end
# end
