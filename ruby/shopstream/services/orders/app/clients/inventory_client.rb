# frozen_string_literal: true

class InventoryClient
  class << self
    def reserve(product_id, quantity)
      response = http_client.post('/api/v1/reservations', {
        product_id: product_id,
        quantity: quantity
      })
      response.success?
    rescue StandardError => e
      Rails.logger.error("InventoryClient.reserve failed: #{e.message}")
      false
    end

    def release(product_id, quantity)
      response = http_client.delete('/api/v1/reservations', {
        product_id: product_id,
        quantity: quantity
      })
      response.success?
    rescue StandardError => e
      Rails.logger.error("InventoryClient.release failed: #{e.message}")
      false
    end

    def check_availability(product_id, quantity)
      response = http_client.get("/api/v1/stock/#{product_id}")
      return false unless response.success?

      stock = JSON.parse(response.body)['stock']
      stock >= quantity
    rescue StandardError => e
      Rails.logger.error("InventoryClient.check_availability failed: #{e.message}")
      false
    end

    private

    def http_client
      @http_client ||= HttpClient.new(ENV.fetch('INVENTORY_SERVICE_URL', 'http://inventory:3000'))
    end
  end
end
