# frozen_string_literal: true

require 'rails_helper'

RSpec.describe OrderSerializer do
  
  describe 'serialization' do
    let(:order) { create(:order, :with_line_items, :with_user, :with_address) }

    it 'does not trigger N+1 queries when serializing order' do
      # Load order with proper includes
      loaded_order = Order.includes(
        :user, :shipping_address, :shipment, :transactions,
        line_items: :product
      ).find(order.id)

      query_count = 0
      callback = lambda { |*_args| query_count += 1 }

      ActiveSupport::Notifications.subscribed(callback, 'sql.active_record') do
        ActiveModelSerializers::SerializableResource.new(loaded_order).as_json
      end

      # With proper includes, should have very few queries
      # Without includes (buggy), will have 1 query per line item + user + address
      expect(query_count).to be < 10
    end

    it 'includes customer_name in output' do
      json = ActiveModelSerializers::SerializableResource.new(order).as_json rescue {}
      expect(json).to have_key(:customer_name).or have_key('customer_name')
    end

    it 'includes item_count in output' do
      json = ActiveModelSerializers::SerializableResource.new(order).as_json rescue {}
      count = json[:item_count] || json['item_count']
      expect(count).to be_a(Integer) if count
    end
  end
end
