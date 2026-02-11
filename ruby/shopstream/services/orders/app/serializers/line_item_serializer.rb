# frozen_string_literal: true

class LineItemSerializer < ActiveModel::Serializer
  attributes :id, :quantity, :unit_price, :total_price

  
  belongs_to :product, serializer: ProductSerializer

  attribute :product_name do
    
    object.product.name
  end

  attribute :product_image do
    
    object.product.primary_image&.url
  end

  attribute :total_price do
    object.quantity * object.unit_price
  end
end
