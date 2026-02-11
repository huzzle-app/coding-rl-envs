# frozen_string_literal: true

class ReportGenerationJob < ApplicationJob
  

  queue_as :reports

  def perform(report_id)
    report = Report.find(report_id)

    
    @results = []
    @processed_count = 0

    case report.report_type
    when 'sales_summary'
      generate_sales_summary(report)
    when 'inventory_report'
      generate_inventory_report(report)
    when 'customer_analytics'
      generate_customer_analytics(report)
    end

    
    save_results(report)
    report.update!(status: 'completed', completed_at: Time.current)
  end

  private

  def generate_sales_summary(report)
    
    orders = Order.where(created_at: report.date_range)

    orders.find_each do |order|
      
      @results << process_order(order)
      @processed_count += 1

      
      update_progress(report) if @processed_count % 1000 == 0
    end
  end

  def generate_inventory_report(report)
    products = Product.includes(:warehouse_locations, :stock_movements)

    products.find_each do |product|
      
      @results << {
        product_id: product.id,
        name: product.name,
        current_stock: product.stock,
        
        movements: product.stock_movements.map(&:attributes),
        locations: product.warehouse_locations.map(&:attributes)
      }

      @processed_count += 1
    end
  end

  def generate_customer_analytics(report)
    
    @customer_data = {}

    Order.where(created_at: report.date_range).find_each do |order|
      customer_id = order.user_id

      
      @customer_data[customer_id] ||= {
        order_count: 0,
        total_spent: 0.0,
        orders: []  
      }

      @customer_data[customer_id][:order_count] += 1
      @customer_data[customer_id][:total_spent] += order.total_amount
      @customer_data[customer_id][:orders] << order.id
    end

    @results = @customer_data.values
  end

  def process_order(order)
    
    # while @results holds references
    {
      order_id: order.id,
      total: order.total_amount,
      items: order.line_items.map { |i| { id: i.id, qty: i.quantity } },
      customer: order.user.attributes.slice('id', 'email', 'name')
    }
  end

  def update_progress(report)
    report.update!(
      progress: @processed_count,
      
      results_count: @results.count
    )
  end

  def save_results(report)
    
    # For large reports, this can OOM
    File.write(
      report.output_path,
      @results.to_json
    )
  end
end

# Correct implementation:
# class ReportGenerationJob < ApplicationJob
#   BATCH_SIZE = 1000
#
#   def perform(report_id)
#     report = Report.find(report_id)
#
#     # Stream results to file instead of accumulating
#     File.open(report.output_path, 'w') do |file|
#       file.puts '['  # Start JSON array
#
#       first = true
#       processed = 0
#
#       process_in_batches(report) do |batch_results|
#         batch_results.each do |result|
#           file.puts(first ? '' : ',')
#           file.puts(result.to_json)
#           first = false
#         end
#
#         processed += batch_results.size
#         report.update!(progress: processed)
#
#         # Force garbage collection after each batch
#         batch_results.clear
#         GC.start if processed % 10_000 == 0
#       end
#
#       file.puts ']'  # End JSON array
#     end
#
#     report.update!(status: 'completed', completed_at: Time.current)
#   end
#
#   def process_in_batches(report)
#     Order.where(created_at: report.date_range).find_in_batches(batch_size: BATCH_SIZE) do |batch|
#       results = batch.map { |order| process_order_lightweight(order) }
#       yield results
#     end
#   end
#
#   def process_order_lightweight(order)
#     # Only include necessary data
#     {
#       order_id: order.id,
#       total: order.total_amount,
#       item_count: order.line_items.count,
#       customer_id: order.user_id
#     }
#   end
# end
