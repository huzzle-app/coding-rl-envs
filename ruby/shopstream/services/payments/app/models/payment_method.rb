# frozen_string_literal: true

class PaymentMethod < ApplicationRecord
  validates :user_id, presence: true
  validates :method_type, presence: true
  validates :token, presence: true, uniqueness: true

  scope :active, -> { where('exp_year > ? OR (exp_year = ? AND exp_month >= ?)', Date.current.year, Date.current.year, Date.current.month) }
  scope :default_method, -> { where(default: true) }
  scope :cards, -> { where(method_type: 'card') }

  def expired?
    return false unless exp_year && exp_month
    Date.new(exp_year, exp_month, -1) < Date.current
  end

  def display_name
    "#{brand} ending in #{last_four}"
  end

  def set_as_default!
    PaymentMethod.where(user_id: user_id).update_all(default: false)
    update!(default: true)
  end
end
