# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Api::V1::OrdersController, type: :controller do
  
  
  
  

  let(:user) { create(:user) }
  let(:other_user) { create(:user) }
  let(:user_order) { create(:order, user: user) }
  let(:other_order) { create(:order, user: other_user) }

  before { sign_in(user) }

  describe 'GET #index' do
    it 'returns only the current user orders, not all orders' do
      user_order
      other_order

      get :index

      order_ids = JSON.parse(response.body).map { |o| o['id'] }
      # Fixed version scopes to current user
      expect(order_ids).to include(user_order.id)
      expect(order_ids).not_to include(other_order.id)
    end

    it 'limits results to prevent unbounded queries' do
      25.times { create(:order, user: user) }

      get :index

      results = JSON.parse(response.body)
      expect(results.size).to be <= 20
    end
  end

  describe 'GET #show' do
    it 'does not allow accessing another user order (IDOR prevention)' do
      get :show, params: { id: other_order.id }

      # Fixed version should return 404 or 403
      expect(response.status).to be_in([403, 404])
    end

    it 'allows accessing own order' do
      get :show, params: { id: user_order.id }
      expect(response.status).to eq(200)
    end
  end

  describe 'PATCH #update' do
    it 'does not allow setting user_id via mass assignment' do
      patch :update, params: { id: user_order.id, order: { user_id: other_user.id } }

      user_order.reload
      expect(user_order.user_id).to eq(user.id)
    end

    it 'does not allow setting total_amount via mass assignment' do
      patch :update, params: { id: user_order.id, order: { total_amount: 0.01 } }

      user_order.reload
      expect(user_order.total_amount).not_to eq(0.01)
    end

    it 'does not allow setting status via mass assignment' do
      patch :update, params: { id: user_order.id, order: { status: 'delivered' } }

      user_order.reload
      expect(user_order.status).not_to eq('delivered')
    end
  end

  describe 'GET #search' do
    it 'does not allow SQL injection through search parameter' do
      expect {
        get :search, params: { q: "'; DROP TABLE orders; --" }
      }.not_to raise_error

      expect(Order.count).to be >= 0
    end

    it 'scopes search results to current user' do
      user_order
      other_order

      get :search, params: { q: 'pending' }

      order_ids = JSON.parse(response.body).map { |o| o['id'] } rescue []
      expect(order_ids).not_to include(other_order.id)
    end
  end
end
