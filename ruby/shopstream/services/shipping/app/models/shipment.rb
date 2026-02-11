# frozen_string_literal: true

class Shipment < ApplicationRecord
  include AASM

  belongs_to :carrier, optional: true

  validates :order_id, presence: true
  validates :tracking_number, presence: true, if: :shipped?
  validates :carrier_name, presence: true, if: :shipped?

  scope :pending, -> { where(status: 'pending') }
  scope :shipped, -> { where(status: 'shipped') }
  scope :in_transit, -> { where(status: 'in_transit') }
  scope :delivered, -> { where(status: 'delivered') }
  scope :for_order, ->(order_id) { where(order_id: order_id) }

  aasm column: :status do
    state :pending, initial: true
    state :shipped
    state :in_transit
    state :out_for_delivery
    state :delivered
    state :failed
    state :returned

    event :ship do
      transitions from: :pending, to: :shipped, guard: :can_ship?
      after do
        self.shipped_at = Time.current
        notify_shipped
      end
    end

    event :transit do
      transitions from: :shipped, to: :in_transit
    end

    event :out_for_delivery do
      transitions from: :in_transit, to: :out_for_delivery
    end

    event :deliver do
      transitions from: [:in_transit, :out_for_delivery], to: :delivered
      after do
        self.delivered_at = Time.current
        notify_delivered
      end
    end

    event :fail_delivery do
      transitions from: [:shipped, :in_transit, :out_for_delivery], to: :failed
    end

    event :return_shipment do
      transitions from: [:shipped, :in_transit, :failed], to: :returned
    end
  end

  def transition_to(state)
    case state.to_sym
    when :shipped then ship!
    when :in_transit then transit!
    when :out_for_delivery then out_for_delivery!
    when :delivered then deliver!
    when :failed then fail_delivery!
    when :returned then return_shipment!
    else
      raise ArgumentError, "Invalid transition to #{state}"
    end
  end

  def tracking_url
    return nil unless carrier && tracking_number
    carrier.tracking_url_template&.gsub('{{tracking_number}}', tracking_number)
  end

  private

  def can_ship?
    tracking_number.present? && (carrier.present? || carrier_name.present?)
  end

  def shipped?
    status == 'shipped' || status == 'in_transit' || status == 'delivered'
  end

  def notify_shipped
    # Notification callback
  end

  def notify_delivered
    # Notification callback
  end
end
