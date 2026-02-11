# frozen_string_literal: true

class ServiceEndpoint < ApplicationRecord
  validates :service_name, presence: true
  validates :url, presence: true
  validates :url, uniqueness: { scope: :service_name }

  scope :healthy, -> { where(status: 'healthy') }
  scope :unhealthy, -> { where(status: 'unhealthy') }
  scope :for_service, ->(name) { where(service_name: name) }

  serialize :metadata, coder: JSON

  def healthy?
    status == 'healthy'
  end

  def mark_healthy!
    update!(
      status: 'healthy',
      consecutive_failures: 0,
      last_health_check_at: Time.current
    )
  end

  def mark_unhealthy!
    update!(
      status: 'unhealthy',
      consecutive_failures: consecutive_failures + 1,
      last_health_check_at: Time.current
    )
  end

  def record_failure!
    new_failures = consecutive_failures + 1
    new_status = new_failures >= 3 ? 'unhealthy' : 'degraded'
    update!(
      status: new_status,
      consecutive_failures: new_failures,
      last_health_check_at: Time.current
    )
  end

  class << self
    def get_healthy_endpoint(service_name)
      for_service(service_name).healthy.order('RANDOM()').first
    end

    def register(service_name, url, metadata: {})
      find_or_create_by!(service_name: service_name, url: url) do |endpoint|
        endpoint.metadata = metadata
      end
    end

    def deregister(service_name, url = nil)
      scope = for_service(service_name)
      scope = scope.where(url: url) if url
      scope.destroy_all
    end
  end
end
