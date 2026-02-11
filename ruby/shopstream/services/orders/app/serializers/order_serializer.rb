# frozen_string_literal: true

class OrderSerializer < ActiveModel::Serializer
  

  attributes :id, :status, :total_amount, :tax_amount, :shipping_amount,
             :discount_amount, :created_at, :updated_at

  
  has_many :line_items, serializer: LineItemSerializer

  # These cause additional queries for each order
  belongs_to :user, serializer: UserSerializer
  belongs_to :shipping_address, serializer: AddressSerializer

  attribute :customer_name do
    
    object.user.full_name
  end

  attribute :item_count do
    
    object.line_items.count
  end

  attribute :subtotal do
    
    object.line_items.sum { |item| item.quantity * item.unit_price }
  end

  attribute :shipping_address_formatted do
    
    return nil unless object.shipping_address

    [
      object.shipping_address.street,
      object.shipping_address.city,
      object.shipping_address.state,
      object.shipping_address.zip_code,
      object.shipping_address.country
    ].compact.join(', ')
  end

  attribute :payment_status do
    
    object.transactions.last&.status || 'pending'
  end

  attribute :can_cancel do
    # Simple attribute, no N+1
    object.status.in?(%w[pending confirmed])
  end

  attribute :tracking_info do
    
    return nil unless object.shipment_id

    shipment = object.shipment
    {
      carrier: shipment&.carrier,
      tracking_number: shipment&.tracking_number,
      status: shipment&.status
    }
  end
end

# Correct implementation - use includes in controller:
# class OrdersController < ApplicationController
#   def index
#     orders = Order.includes(
#       :user,
#       :shipping_address,
#       :shipment,
#       :transactions,
#       line_items: { product: :images }
#     ).where(user_id: current_user.id)
#
#     render json: orders, each_serializer: OrderSerializer
#   end
#
#   def show
#     order = Order.includes(
#       :user,
#       :shipping_address,
#       :shipment,
#       :transactions,
#       line_items: { product: :images }
#     ).find(params[:id])
#
#     render json: order, serializer: OrderSerializer
#   end
# end
#
# # Or use counter caches:
# class Order < ApplicationRecord
#   has_many :line_items, counter_cache: true
# end
#
# class OrderSerializer < ActiveModel::Serializer
#   attribute :item_count do
#     object.line_items_count  # Uses counter cache
#   end
# end
