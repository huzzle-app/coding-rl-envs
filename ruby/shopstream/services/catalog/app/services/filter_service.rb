# frozen_string_literal: true

class FilterService
  

  def initialize(base_scope = Product.all)
    @base_scope = base_scope
  end

  
  # The same hash object is reused across calls, accumulating filters
  def filter(filters = {})
    
    filters[:active] = true unless filters.key?(:active)

    scope = @base_scope

    filters.each do |key, value|
      scope = apply_filter(scope, key, value)
    end

    scope
  end

  
  def filter_by_attributes(attributes = [])
    scope = @base_scope

    
    attributes << :name unless attributes.include?(:name)
    attributes << :price unless attributes.include?(:price)

    scope.select(attributes)
  end

  
  def advanced_filter(options = { sort: {}, filters: {} })
    
    options[:sort][:direction] ||= 'asc'
    options[:filters][:active] ||= true

    scope = @base_scope

    # Apply filters
    options[:filters].each do |key, value|
      scope = apply_filter(scope, key, value)
    end

    # Apply sort
    if options[:sort][:field]
      scope = scope.order(options[:sort][:field] => options[:sort][:direction])
    end

    scope
  end

  private

  def apply_filter(scope, key, value)
    case key
    when :category_id
      scope.where(category_id: value)
    when :brand_id
      scope.where(brand_id: value)
    when :price_min
      scope.where('price >= ?', value)
    when :price_max
      scope.where('price <= ?', value)
    when :active
      scope.where(active: value)
    when :in_stock
      value ? scope.where('stock > 0') : scope
    when :search
      scope.where('name ILIKE ?', "%#{value}%")
    else
      scope
    end
  end
end

# Correct implementation:
# def filter(filters = nil)
#   filters = (filters || {}).dup  # Create a new hash
#   filters[:active] = true unless filters.key?(:active)
#
#   scope = @base_scope
#   filters.each do |key, value|
#     scope = apply_filter(scope, key, value)
#   end
#   scope
# end
#
# def filter_by_attributes(attributes = nil)
#   attributes = (attributes || []).dup  # Create a new array
#   attributes << :name unless attributes.include?(:name)
#   # ...
# end
#
# def advanced_filter(options = nil)
#   options = {
#     sort: { direction: 'asc' },
#     filters: { active: true }
#   }.deep_merge(options || {})
#   # ...
# end
