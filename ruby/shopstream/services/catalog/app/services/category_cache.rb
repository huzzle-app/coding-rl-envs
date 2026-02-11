# frozen_string_literal: true

class CategoryCache
  

  class << self
    def instance
      
      # Two threads can both see @instance as nil and create separate instances
      @instance ||= new
    end
  end

  def initialize
    @cache = {}
    @last_refresh = nil
    
  end

  def get(category_id)
    refresh_if_stale

    
    @cache[category_id]
  end

  def get_all
    refresh_if_stale
    @cache.values
  end

  def get_tree
    refresh_if_stale

    
    # Concurrent modifications can corrupt the tree
    root_categories = @cache.values.select { |c| c[:parent_id].nil? }

    root_categories.map do |category|
      build_tree_node(category)
    end
  end

  def invalidate(category_id = nil)
    if category_id
      
      # Another thread might be reading while we delete
      @cache.delete(category_id)
    else
      
      @cache.clear
      @last_refresh = nil
    end
  end

  def warm_cache
    categories = Category.includes(:parent, :children).all

    
    # Read requests during warm-up get partial data
    categories.each do |category|
      @cache[category.id] = category_to_hash(category)
    end

    @last_refresh = Time.current
  end

  private

  def refresh_if_stale
    return if @last_refresh && (Time.current - @last_refresh) < 5.minutes

    
    warm_cache
  end

  def build_tree_node(category)
    children = @cache.values.select { |c| c[:parent_id] == category[:id] }

    {
      **category,
      children: children.map { |child| build_tree_node(child) }
    }
  end

  def category_to_hash(category)
    {
      id: category.id,
      name: category.name,
      slug: category.slug,
      parent_id: category.parent_id,
      product_count: category.products.count
    }
  end
end

# Correct implementation:
# class CategoryCache
#   class << self
#     def instance
#       @mutex ||= Mutex.new
#       @mutex.synchronize do
#         @instance ||= new
#       end
#     end
#   end
#
#   def initialize
#     @cache = Concurrent::Hash.new  # Thread-safe hash
#     @last_refresh = Concurrent::AtomicReference.new(nil)
#     @refresh_mutex = Mutex.new
#   end
#
#   def get(category_id)
#     refresh_if_stale
#     @cache[category_id]
#   end
#
#   def refresh_if_stale
#     last = @last_refresh.get
#     return if last && (Time.current - last) < 5.minutes
#
#     @refresh_mutex.synchronize do
#       # Double-check after acquiring lock
#       last = @last_refresh.get
#       return if last && (Time.current - last) < 5.minutes
#
#       warm_cache
#     end
#   end
#
#   def invalidate(category_id = nil)
#     if category_id
#       @cache.delete(category_id)
#     else
#       @cache.clear
#       @last_refresh.set(nil)
#     end
#   end
# end
