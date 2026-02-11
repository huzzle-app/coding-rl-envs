# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ReservationService do
  let(:product) { create(:product, stock: 10) }
  subject(:service) { described_class.new(product.id) }

  describe '#reserve' do
    
    context 'race condition with concurrent reservations' do
      it 'prevents overselling when multiple requests reserve simultaneously' do
        # Product has 10 units, two requests each want 8
        threads = 2.times.map do
          Thread.new do
            described_class.new(product.id).reserve(8, order_id: SecureRandom.uuid)
          end
        end

        results = threads.map(&:value)

        # Only one should succeed, one should fail with insufficient stock
        successful = results.count { |r| r[:success] }
        expect(successful).to eq(1)
      end

      it 'maintains accurate stock count under concurrent load' do
        initial_stock = product.stock
        reservation_amount = 1

        threads = 15.times.map do
          Thread.new do
            described_class.new(product.id).reserve(reservation_amount, order_id: SecureRandom.uuid)
          end
        end

        results = threads.map(&:value)
        successful_count = results.count { |r| r[:success] }

        product.reload
        # Stock should equal initial minus successful reservations
        expect(product.stock).to eq(initial_stock - (successful_count * reservation_amount))
      end

      it 'does not allow negative stock' do
        # Try to reserve more than available from multiple threads
        threads = 5.times.map do
          Thread.new do
            described_class.new(product.id).reserve(5, order_id: SecureRandom.uuid)
          end
        end

        threads.each(&:join)
        product.reload

        expect(product.stock).to be >= 0
      end
    end

    context 'atomic stock update' do
      it 'uses atomic decrement operation' do
        expect {
          service.reserve(5, order_id: SecureRandom.uuid)
        }.to change { product.reload.stock }.by(-5)
      end

      it 'rolls back on failure' do
        allow_any_instance_of(StockReservation).to receive(:save!).and_raise(ActiveRecord::RecordInvalid)

        expect {
          service.reserve(5, order_id: SecureRandom.uuid) rescue nil
        }.not_to change { product.reload.stock }
      end
    end
  end

  describe '#release' do
    let!(:reservation) do
      StockReservation.create!(
        product_id: product.id,
        order_id: SecureRandom.uuid,
        quantity: 5
      )
    end

    it 'atomically releases reserved stock' do
      original_stock = product.stock

      service.release(reservation.id)

      product.reload
      expect(product.stock).to eq(original_stock + 5)
    end

    it 'handles concurrent release attempts safely' do
      threads = 2.times.map do
        Thread.new do
          described_class.new(product.id).release(reservation.id) rescue nil
        end
      end

      threads.each(&:join)
      product.reload

      # Stock should only increase by reservation amount once
      expect(product.stock).to eq(15) # 10 + 5
    end
  end
end
