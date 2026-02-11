# frozen_string_literal: true

class ProductCache
  
  # When cache expires, all concurrent requests hit the database

  CACHE_TTL = 5.minutes
  CACHE_PREFIX = 'product:'

  def initialize(redis = nil)
    @redis = redis || Redis.current
  end

  def get(product_id)
    cache_key = "#{CACHE_PREFIX}#{product_id}"
    cached = @redis.get(cache_key)

    if cached
      CacheSerializer.deserialize(cached)
    else
      
      # No locking or single-flight mechanism
      product = fetch_and_cache(product_id)
      product
    end
  end

  def get_many(product_ids)
    cache_keys = product_ids.map { |id| "#{CACHE_PREFIX}#{id}" }
    cached_values = @redis.mget(*cache_keys)

    results = {}
    missing_ids = []

    product_ids.each_with_index do |id, index|
      if cached_values[index]
        results[id] = CacheSerializer.deserialize(cached_values[index])
      else
        missing_ids << id
      end
    end

    
    if missing_ids.any?
      fetched = fetch_many_and_cache(missing_ids)
      results.merge!(fetched)
    end

    results
  end

  def invalidate(product_id)
    cache_key = "#{CACHE_PREFIX}#{product_id}"
    @redis.del(cache_key)
  end

  def warm_cache(product_ids)
    
    # Can overwhelm database if called with many IDs
    products = Product.where(id: product_ids).includes(:category, :brand)

    products.each do |product|
      cache_product(product)
    end
  end

  private

  def fetch_and_cache(product_id)
    
    product = Product.includes(:category, :brand, :variants).find(product_id)
    cache_product(product)
    product_to_hash(product)
  rescue ActiveRecord::RecordNotFound
    nil
  end

  def fetch_many_and_cache(product_ids)
    products = Product.where(id: product_ids).includes(:category, :brand)

    results = {}
    products.each do |product|
      cache_product(product)
      results[product.id] = product_to_hash(product)
    end

    results
  end

  def cache_product(product)
    cache_key = "#{CACHE_PREFIX}#{product.id}"
    data = product_to_hash(product)

    @redis.setex(cache_key, CACHE_TTL.to_i, CacheSerializer.serialize(data))
  end

  def product_to_hash(product)
    {
      id: product.id,
      name: product.name,
      sku: product.sku,
      price: product.price,
      stock: product.stock,
      category: product.category&.name,
      brand: product.brand&.name
    }
  end
end

# Correct implementation using cache stampede prevention:
# def get(product_id)
#   cache_key = "#{CACHE_PREFIX}#{product_id}"
#   lock_key = "#{cache_key}:lock"
#
#   cached = @redis.get(cache_key)
#   return CacheSerializer.deserialize(cached) if cached
#
#   # Try to acquire lock for cache population
#   if @redis.set(lock_key, '1', nx: true, ex: 10)
#     begin
#       # We got the lock, fetch and cache
#       product = fetch_and_cache(product_id)
#       return product
#     ensure
#       @redis.del(lock_key)
#     end
#   else
#     # Another process is populating, wait and retry
#     sleep(0.1)
#     get(product_id)  # Retry
#   end
# end
#
# # Or use cache with early expiration + background refresh:
# def get(product_id)
#   cache_key = "#{CACHE_PREFIX}#{product_id}"
#   cached = @redis.get(cache_key)
#
#   if cached
#     data = CacheSerializer.deserialize(cached)
#
#     # If close to expiry, trigger background refresh
#     ttl = @redis.ttl(cache_key)
#     if ttl < 60  # Less than 1 minute left
#       CacheRefreshJob.perform_later(product_id)
#     end
#
#     return data
#   end
#
#   fetch_and_cache(product_id)
# end
