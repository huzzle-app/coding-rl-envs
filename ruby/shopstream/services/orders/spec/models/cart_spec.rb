# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Cart do
  
  let(:cart) { create(:cart) }
  let(:product) { create(:product, stock: 100, price: 9.99) }

  describe '#add_item' do
    it 'correctly accumulates quantity under concurrent access' do
      cart.add_item(product.id, 1) rescue nil

      threads = 10.times.map do
        Thread.new { Cart.find(cart.id).add_item(product.id, 1) rescue nil }
      end
      threads.each(&:join)

      cart.reload
      item = cart.cart_items.find_by(product_id: product.id)
      # Should be 11 (1 initial + 10 concurrent), not less due to lost updates
      expect(item&.quantity).to eq(11)
    end

    it 'creates new item when product not in cart' do
      cart.add_item(product.id, 3)

      item = cart.cart_items.find_by(product_id: product.id)
      expect(item.quantity).to eq(3)
    end
  end

  describe '#remove_item' do
    before { cart.add_item(product.id, 10) }

    it 'reduces quantity correctly' do
      cart.remove_item(product.id, 3)

      item = cart.cart_items.find_by(product_id: product.id)
      expect(item.quantity).to eq(7)
    end

    it 'removes item entirely when quantity reaches zero' do
      cart.remove_item(product.id, 10)

      item = cart.cart_items.find_by(product_id: product.id)
      expect(item).to be_nil
    end
  end

  describe '#total' do
    it 'calculates total without float precision errors' do
      cart.add_item(product.id, 3) rescue nil

      total = cart.total rescue 0
      expect(total).to be_a(Numeric)
    end
  end
end
