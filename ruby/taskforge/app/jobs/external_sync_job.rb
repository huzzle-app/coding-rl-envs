# frozen_string_literal: true

class ExternalSyncJob < ApplicationJob
  queue_as :external

  retry_on StandardError, wait: :exponentially_longer, attempts: 3

  def perform(organization_id)
    organization = Organization.find(organization_id)

    
    response = sync_with_external_api(organization)

    if response.success?
      
      organization.update!(external_id: response.body['id'], synced_at: Time.current)
    else
      raise "Sync failed: #{response.body}"
    end
  rescue ActiveRecord::RecordNotFound
    # Organization deleted
  end

  private

  def sync_with_external_api(organization)
    
    HTTParty.post(
      ENV['EXTERNAL_API_URL'],
      body: {
        name: organization.name,
        slug: organization.slug,
        members_count: organization.members.count
      }.to_json,
      headers: { 'Content-Type' => 'application/json' }
    )
  end
end
