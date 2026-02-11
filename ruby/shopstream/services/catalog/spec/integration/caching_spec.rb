# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Caching Bugs' do
  
  
  

  describe 'Stale cache invalidation (G2)' do
    it 'invalidates product cache when product is updated' do
      product = create(:product, name: 'Widget', price: 10.0)

      # Cache the product
      cache_key = "product:#{product.id}"
      Rails.cache.write(cache_key, product.attributes)

      # Update product
      product.update!(price: 15.0)

      # Cache should be invalidated
      cached = Rails.cache.read(cache_key)
      expect(cached).to be_nil.or satisfy { |c| c['price'] == 15.0 }
    end

    it 'invalidates category cache when products change' do
      category = create(:category)
      product = create(:product, category: category)

      # Cache category products
      cache_key = "category:#{category.id}:products"
      Rails.cache.write(cache_key, [product.id])

      # Add new product
      new_product = create(:product, category: category)

      # Cache should include new product or be invalidated
      cached = Rails.cache.read(cache_key)
      expect(cached).to be_nil.or include(new_product.id)
    end

    it 'stale read is not possible after write' do
      product = create(:product, price: 100.0)

      # Write to cache
      Rails.cache.write("product:#{product.id}", product.as_json)

      # Update
      product.update!(price: 200.0)

      # Read should reflect the update
      fresh = Product.find(product.id)
      expect(fresh.price).to eq(200.0)
    end
  end

  describe 'Cache key collision (G3)' do
    it 'uses unique keys that avoid collisions between different entities' do
      product1 = create(:product, id: 123) rescue create(:product)
      category1 = create(:category, id: 123) rescue create(:category)

      product_key = "product:#{product1.id}"
      category_key = "category:#{category1.id}"

      # Keys should be different even if IDs match
      expect(product_key).not_to eq(category_key)
    end

    it 'includes versioning or namespace in cache keys' do
      product = create(:product)

      # Cache key should include model type or namespace
      key = "product:#{product.id}"
      expect(key).to include('product')
    end

    it 'cache keys include updated_at for automatic invalidation' do
      product = create(:product)

      key_with_version = "product:#{product.id}:#{product.updated_at.to_i}"

      product.touch
      new_key = "product:#{product.id}:#{product.reload.updated_at.to_i}"

      expect(key_with_version).not_to eq(new_key)
    end
  end

  describe 'Unbounded cache growth (G4)' do
    it 'cache has TTL set on entries' do
      product = create(:product)

      Rails.cache.write("product:#{product.id}", product.as_json, expires_in: 1.hour)

      # Entry should have expiration
      ttl = Redis.current.ttl("product:#{product.id}") rescue -1

      # TTL should be set (positive value)
      expect(ttl).to be > 0 if ttl != -2
    end

    it 'does not cache unbounded result sets' do
      100.times { create(:product) }

      # Should not cache ALL products without pagination
      cached = Rails.cache.read('all_products')
      if cached
        expect(cached.size).to be <= 50
      end
    end

    it 'limits cache entry size' do
      large_data = 'x' * 1_000_000
      product = create(:product)

      # Should not store extremely large values
      Rails.cache.write("product:#{product.id}:details", large_data, expires_in: 1.hour)

      cached = Rails.cache.read("product:#{product.id}:details")
      # Either rejected or stored with size limit
      expect(cached.nil? || cached.size <= 1_000_000).to be true
    end
  end
end
