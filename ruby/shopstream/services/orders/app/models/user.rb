# frozen_string_literal: true

class User < ApplicationRecord
  has_many :orders

  validates :email, presence: true, uniqueness: true
  validates :full_name, presence: true

  def phone_present?
    phone.present?
  end
end
