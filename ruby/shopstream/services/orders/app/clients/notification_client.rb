# frozen_string_literal: true

class NotificationClient
  class << self
    def send_email(to:, template:, data:)
      response = http_client.post('/api/v1/emails', {
        to: to,
        template: template,
        data: data
      })
      response.success?
    rescue StandardError => e
      Rails.logger.error("NotificationClient.send_email failed: #{e.message}")
      false
    end

    def send_sms(to:, message:)
      response = http_client.post('/api/v1/sms', {
        to: to,
        message: message
      })
      response.success?
    rescue StandardError => e
      Rails.logger.error("NotificationClient.send_sms failed: #{e.message}")
      false
    end

    private

    def http_client
      @http_client ||= HttpClient.new(ENV.fetch('NOTIFICATIONS_SERVICE_URL', 'http://notifications:3000'))
    end
  end
end
