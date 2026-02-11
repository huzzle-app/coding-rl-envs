# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Security Integration' do
  
  # Additional security patterns

  describe 'Mass assignment protection (I2)' do
    let(:user) { create(:user) }
    let(:order) { create(:order, user: user, status: 'pending', total_amount: 100.0) }

    it 'does not allow setting payment_status via mass assignment' do
      order.assign_attributes(payment_status: 'paid')

      # Strong params should filter this out
      expect(order.changed_attributes.keys).not_to include('payment_status')
    end

    it 'Order.new does not accept admin-only attributes' do
      params = {
        user_id: user.id,
        total_amount: 0.01,
        payment_status: 'paid',
        status: 'delivered',
        admin_notes: 'hacked'
      }

      order = Order.new(params.except(:user_id))

      # Sensitive fields should not be mass-assignable
      expect(order.payment_status).not_to eq('paid')
      expect(order.total_amount).not_to eq(0.01)
    end
  end

  describe 'Parameter filtering' do
    it 'filters sensitive params from logs' do
      # Password, credit_card, token should be filtered
      if defined?(Rails.application.config.filter_parameters)
        filters = Rails.application.config.filter_parameters
        expect(filters).to include(:password).or include('password')
      end
    end
  end
end
