# frozen_string_literal: true

class AddressSerializer < ActiveModel::Serializer
  attributes :id, :street, :city, :state, :zip_code, :country
end
