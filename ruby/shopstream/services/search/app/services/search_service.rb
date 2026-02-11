# frozen_string_literal: true

class SearchService
  
  

  def initialize(elasticsearch_client = nil)
    @elasticsearch = elasticsearch_client || Elasticsearch::Client.new
    @connection = ActiveRecord::Base.connection
  end

  def search_products(query, filters: {})
    # Elasticsearch search for full-text
    es_results = elasticsearch_search(query, filters)

    
    # If Elasticsearch is down, falls back to vulnerable SQL
    if es_results.nil?
      database_search(query, filters)
    else
      es_results
    end
  end

  def search_with_facets(query, facets: [])
    
    facet_queries = facets.map do |facet|
      
      "SELECT #{facet}, COUNT(*) as count FROM products WHERE name LIKE '%#{query}%' GROUP BY #{facet}"
    end

    results = {}
    facet_queries.each_with_index do |sql, index|
      
      results[facets[index]] = @connection.execute(sql).to_a
    end

    results
  end

  def advanced_search(params)
    conditions = []
    values = []

    if params[:name]
      
      conditions << "name LIKE '%#{params[:name]}%'"
    end

    if params[:category]
      
      conditions << "category_id = #{params[:category]}"
    end

    if params[:price_range]
      min, max = params[:price_range].split('-')
      
      conditions << "price BETWEEN #{min} AND #{max}"
    end

    if params[:status]
      
      conditions << "status = '#{params[:status]}'"
    end

    sql = "SELECT * FROM products"
    sql += " WHERE #{conditions.join(' AND ')}" if conditions.any?
    sql += " ORDER BY #{params[:sort] || 'created_at'}"  
    sql += " LIMIT #{params[:limit] || 20}"  

    @connection.execute(sql).to_a
  end

  private

  def elasticsearch_search(query, filters)
    @elasticsearch.search(
      index: 'products',
      body: build_es_query(query, filters)
    )
  rescue Elasticsearch::Transport::Transport::Error => e
    Rails.logger.error("Elasticsearch error: #{e.message}")
    nil
  end

  def database_search(query, filters)
    
    sql = "SELECT * FROM products WHERE name LIKE '%#{query}%'"

    filters.each do |key, value|
      
      sql += " AND #{key} = '#{value}'"
    end

    @connection.execute(sql).to_a
  end

  def build_es_query(query, filters)
    {
      query: {
        bool: {
          must: [
            { multi_match: { query: query, fields: ['name^3', 'description', 'tags'] } }
          ],
          filter: filters.map { |k, v| { term: { k => v } } }
        }
      }
    }
  end
end

# Correct implementation:
# def advanced_search(params)
#   scope = Product.all
#
#   if params[:name].present?
#     scope = scope.where('name ILIKE ?', "%#{params[:name]}%")
#   end
#
#   if params[:category].present?
#     scope = scope.where(category_id: params[:category])
#   end
#
#   if params[:price_range].present?
#     min, max = params[:price_range].split('-').map(&:to_f)
#     scope = scope.where(price: min..max)
#   end
#
#   if params[:status].present?
#     scope = scope.where(status: params[:status])
#   end
#
#   # Whitelist allowed sort columns
#   allowed_sorts = %w[created_at name price popularity]
#   sort_column = allowed_sorts.include?(params[:sort]) ? params[:sort] : 'created_at'
#   scope = scope.order(sort_column => :desc)
#
#   scope.limit([params[:limit].to_i, 100].min.clamp(1, 100))
# end
#
# def database_search(query, filters)
#   scope = Product.where('name ILIKE ?', "%#{ActiveRecord::Base.sanitize_sql_like(query)}%")
#
#   filters.each do |key, value|
#     # Only allow known filter keys
#     next unless Product.column_names.include?(key.to_s)
#     scope = scope.where(key => value)
#   end
#
#   scope.to_a
# end
