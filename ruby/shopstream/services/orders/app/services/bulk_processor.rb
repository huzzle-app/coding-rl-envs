# frozen_string_literal: true

class BulkProcessor
  

  def initialize
    @connection = ActiveRecord::Base.connection
  end

  def bulk_update_status(order_ids, new_status)
    
    # PostgreSQL has a limit on prepared statements (default 10000)
    # With varying batch sizes, this leaks statements

    order_ids.each_slice(100) do |batch|
      
      # These are cached but never cleared
      Order.where(id: batch).update_all(status: new_status)
    end
  end

  def bulk_calculate_totals(order_ids)
    
    order_ids.each do |order_id|
      # Each unique order_id creates a new prepared statement
      @connection.execute(<<-SQL)
        UPDATE orders
        SET total_amount = (
          SELECT COALESCE(SUM(quantity * unit_price), 0)
          FROM line_items
          WHERE order_id = #{order_id}
        )
        WHERE id = #{order_id}
      SQL
    end
  end

  def bulk_archive(older_than:)
    
    Order.where('created_at < ?', older_than).find_each(batch_size: 500) do |order|
      # Each order creates new statements
      archive_order(order)
    end
  end

  private

  def archive_order(order)
    
    ArchivedOrder.create!(order.attributes)
    order.line_items.each do |item|
      ArchivedLineItem.create!(item.attributes.merge(archived_order_id: order.id))
    end
    order.destroy!
  end
end

# Correct implementation:
# def bulk_update_status(order_ids, new_status)
#   # Use a single parameterized query
#   Order.where(id: order_ids).update_all(status: new_status)
# end
#
# def bulk_calculate_totals(order_ids)
#   # Use a single UPDATE with subquery
#   @connection.execute(<<-SQL)
#     UPDATE orders o
#     SET total_amount = (
#       SELECT COALESCE(SUM(quantity * unit_price), 0)
#       FROM line_items li
#       WHERE li.order_id = o.id
#     )
#     WHERE o.id = ANY(ARRAY[#{order_ids.join(',')}])
#   SQL
# end
#
# def bulk_archive(older_than:)
#   # Use INSERT ... SELECT for bulk archive
#   Order.transaction do
#     connection.execute(<<-SQL)
#       INSERT INTO archived_orders (...)
#       SELECT ... FROM orders WHERE created_at < '#{older_than}'
#     SQL
#     Order.where('created_at < ?', older_than).delete_all
#   end
# end
