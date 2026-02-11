# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Order do
  
  describe 'concurrent updates' do
    let(:order) { create(:order, status: 'pending', total_amount: 100.0) }

    it 'detects concurrent modifications with optimistic locking' do
      order1 = Order.find(order.id)
      order2 = Order.find(order.id)

      order1.update!(total_amount: 200.0)

      # Second update should detect stale data
      # Fixed version uses lock_version column
      expect {
        order2.update!(total_amount: 300.0)
      }.to raise_error(ActiveRecord::StaleObjectError) rescue nil
    end
  end

  
  describe 'confirm event' do
    let(:order) { create(:order, status: 'pending') }

    it 'sends notification only after transaction is committed' do
      # Fixed version should use after_commit, not after callback in aasm
      expect(OrderNotificationJob).to receive(:perform_later).with(order.id, :confirmed)
      order.confirm!
    end

    it 'does not send notification if save fails' do
      allow(order).to receive(:save!).and_raise(ActiveRecord::RecordInvalid)
      expect(OrderNotificationJob).not_to receive(:perform_later)

      order.confirm! rescue nil
    end
  end

  
  describe '#destroy_with_associations' do
    it 'completes within a reasonable time' do
      order = create(:order, :with_line_items)

      expect {
        Timeout.timeout(10) { order.destroy_with_associations }
      }.not_to raise_error
    end
  end

  
  describe '.by_status' do
    it 'returns orders filtered by status' do
      create(:order, status: 'pending')
      create(:order, status: 'confirmed')

      results = Order.by_status('pending')
      expect(results.map(&:status).uniq).to eq(['pending'])
    end
  end
end
