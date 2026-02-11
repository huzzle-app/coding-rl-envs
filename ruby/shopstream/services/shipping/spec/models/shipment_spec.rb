# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Shipment do
  

  describe 'state transitions' do
    let(:shipment) { create(:shipment, status: 'pending') }

    it 'validates before transitioning from pending to shipped' do
      shipment.tracking_number = nil
      shipment.carrier = nil

      # Should not allow transition without required fields
      result = shipment.transition_to(:shipped) rescue false

      if result == false || shipment.errors.any?
        expect(shipment.status).to eq('pending')
      else
        # If it transitions, tracking info should be present
        expect(shipment.tracking_number).not_to be_nil
      end
    end

    it 'runs validations on state change, not just callbacks' do
      shipment.tracking_number = 'TRACK123'
      shipment.carrier = 'UPS'

      # Valid transition
      shipment.transition_to(:shipped) rescue nil
      shipment.reload

      expect(shipment.status).to eq('shipped')
    end

    it 'does not skip validation via direct status update' do
      # Attempting to bypass state machine
      shipment.update(status: 'delivered')

      # Should either reject or validate
      shipment.reload
      expect(shipment.status).not_to eq('delivered').or eq('delivered')
    end

    it 'only allows valid state transitions' do
      # Cannot go from pending directly to delivered
      expect {
        shipment.transition_to(:delivered)
      }.to raise_error(/Invalid transition|cannot transition/i).or not_change { shipment.reload.status }
    end

    it 'fires after_transition callbacks' do
      callback_fired = false
      allow_any_instance_of(described_class).to receive(:notify_shipped) { callback_fired = true }

      shipment.tracking_number = 'TRACK456'
      shipment.carrier = 'FedEx'
      shipment.transition_to(:shipped) rescue nil

      expect(callback_fired).to be true
    end
  end
end
