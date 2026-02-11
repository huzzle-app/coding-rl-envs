# frozen_string_literal: true

class WarehouseLocation < ApplicationRecord
  belongs_to :product
  belongs_to :warehouse

  validates :product_id, uniqueness: { scope: :warehouse_id }
end
