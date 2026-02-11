# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Product do
  
  describe '#increment_view_count!' do
    let(:product) { create(:product, view_count: 0) }

    it 'atomically increments view count under concurrent access' do
      initial = product.view_count
      threads = 10.times.map do
        Thread.new do
          Product.find(product.id).increment_view_count! rescue nil
        end
      end
      threads.each(&:join)

      product.reload
      # With non-atomic updates, some increments are lost
      # Fixed version should have exactly 10 more views
      expect(product.view_count).to eq(initial + 10)
    end

    it 'does not lose updates when two threads increment simultaneously' do
      product.update!(view_count: 100)

      t1 = Thread.new { Product.find(product.id).increment_view_count! rescue nil }
      t2 = Thread.new { Product.find(product.id).increment_view_count! rescue nil }
      [t1, t2].each(&:join)

      product.reload
      expect(product.view_count).to eq(102)
    end
  end

  
  describe 'before_save callback' do
    it 'does not publish event if save fails due to validation' do
      product = build(:product, name: nil) # invalid
      expect(KafkaProducer).not_to receive(:publish)

      product.save # should fail validation
    end

    it 'publishes event only after successful save' do
      product = create(:product)
      # Fixed version uses after_commit instead of before_save
      expect(KafkaProducer).to receive(:publish).with('product.updated', hash_including(:product_id))
      product.update!(price: product.price + 1)
    end
  end

  describe '#record_purchase' do
    let(:product) { create(:product, stock: 100, purchase_count: 0) }

    it 'atomically decrements stock and increments purchase count' do
      product.record_purchase(5)
      product.reload

      expect(product.stock).to eq(95)
      expect(product.purchase_count).to eq(5)
    end
  end
end
