# frozen_string_literal: true

class Attachment < ApplicationRecord
  belongs_to :task
  belongs_to :user

  validates :filename, presence: true
  validates :storage_key, presence: true

  before_validation :generate_storage_key, on: :create

  private

  def generate_storage_key
    self.storage_key ||= "#{SecureRandom.uuid}/#{filename}"
  end
end
