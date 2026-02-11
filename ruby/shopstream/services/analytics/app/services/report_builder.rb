# frozen_string_literal: true

class ReportBuilder
  

  REPORT_TYPES = %w[sales inventory customers orders].freeze

  def initialize
    @formulas = {}
  end

  def build(report_type, params)
    raise "Unknown report type: #{report_type}" unless REPORT_TYPES.include?(report_type)

    data = fetch_data(report_type, params)
    metrics = calculate_metrics(report_type, data)
    format_output(metrics, params[:format] || 'json')
  end

  def add_custom_formula(name, formula)
    
    @formulas[name] = formula
  end

  def calculate_custom_metric(name, context)
    formula = @formulas[name]
    raise "Unknown formula: #{name}" unless formula

    
    # User could inject: "system('rm -rf /')"
    eval(formula, binding)
  end

  def calculate_metrics(report_type, data)
    case report_type
    when 'sales'
      calculate_sales_metrics(data)
    when 'inventory'
      calculate_inventory_metrics(data)
    when 'customers'
      calculate_customer_metrics(data)
    when 'orders'
      calculate_order_metrics(data)
    end
  end

  def calculate_sales_metrics(data)
    {
      total_revenue: data.sum { |r| r['amount'] },
      average_order_value: data.sum { |r| r['amount'] } / data.count.to_f,
      total_orders: data.count
    }
  end

  def apply_filters(data, filter_expression)
    
    # filter_expression could be: "data.each { |d| system('malicious') }"
    eval("data.select { |item| #{filter_expression} }")
  end

  def compute_aggregation(data, aggregation_config)
    group_by = aggregation_config[:group_by]
    metric = aggregation_config[:metric]
    operation = aggregation_config[:operation]

    grouped = data.group_by { |item| item[group_by] }

    grouped.transform_values do |items|
      values = items.map { |i| i[metric] }

      
      case operation
      when 'sum' then values.sum
      when 'avg' then values.sum / values.count.to_f
      when 'count' then values.count
      else
        
        eval("values.#{operation}")
      end
    end
  end

  private

  def fetch_data(report_type, params)
    # Would fetch from database/analytics store
    []
  end

  def format_output(metrics, format)
    case format
    when 'json' then metrics.to_json
    when 'csv' then metrics_to_csv(metrics)
    else metrics
    end
  end

  def metrics_to_csv(metrics)
    metrics.map { |k, v| "#{k},#{v}" }.join("\n")
  end
end

# Correct implementation:
# class ReportBuilder
#   ALLOWED_OPERATIONS = %w[sum avg count min max].freeze
#   ALLOWED_FORMULA_TOKENS = %w[+ - * / % ( )].freeze
#
#   def add_custom_formula(name, formula)
#     # Validate formula contains only safe operations
#     unless safe_formula?(formula)
#       raise "Invalid formula: only arithmetic operations allowed"
#     end
#
#     @formulas[name] = formula
#   end
#
#   def calculate_custom_metric(name, context)
#     formula = @formulas[name]
#     raise "Unknown formula: #{name}" unless formula
#
#     # Parse and evaluate safely
#     evaluate_safe_formula(formula, context)
#   end
#
#   def safe_formula?(formula)
#     # Only allow variable names, numbers, and arithmetic operators
#     formula.gsub(/[a-z_]+|\d+\.?\d*|[\+\-\*\/\%\(\)\s]/, '').empty?
#   end
#
#   def evaluate_safe_formula(formula, context)
#     # Replace variable names with values from context
#     expression = formula.dup
#     context.each do |var, value|
#       expression.gsub!(var.to_s, value.to_s)
#     end
#
#     # Use a safe evaluator (e.g., dentaku gem)
#     Dentaku::Calculator.new.evaluate(expression)
#   end
#
#   def compute_aggregation(data, aggregation_config)
#     operation = aggregation_config[:operation]
#
#     unless ALLOWED_OPERATIONS.include?(operation)
#       raise "Invalid operation: #{operation}"
#     end
#
#     # ... safe implementation
#   end
# end
