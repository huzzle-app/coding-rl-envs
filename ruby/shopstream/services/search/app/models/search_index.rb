# frozen_string_literal: true

class SearchIndex < ApplicationRecord
  validates :index_name, presence: true
  validates :document_type, presence: true
  validates :document_id, presence: true
  validates :document_id, uniqueness: { scope: [:index_name, :document_type] }

  serialize :metadata, coder: JSON

  scope :for_index, ->(name) { where(index_name: name) }
  scope :for_type, ->(type) { where(document_type: type) }
  scope :stale, -> { where('indexed_at < ?', 1.day.ago) }
  scope :boosted, -> { where('boost > 1.0') }

  def stale?
    indexed_at.nil? || indexed_at < 1.day.ago
  end

  def reindex!
    update!(indexed_at: Time.current)
  end

  class << self
    def index_document(index_name:, document_type:, document_id:, content:, metadata: {}, boost: 1.0)
      record = find_or_initialize_by(
        index_name: index_name,
        document_type: document_type,
        document_id: document_id
      )
      record.update!(
        content: content,
        metadata: metadata,
        boost: boost,
        indexed_at: Time.current
      )
      record
    end

    def remove_document(index_name:, document_type:, document_id:)
      find_by(
        index_name: index_name,
        document_type: document_type,
        document_id: document_id
      )&.destroy
    end

    def search(index_name:, query:, document_type: nil)
      scope = for_index(index_name)
      scope = scope.for_type(document_type) if document_type
      scope.where('content ILIKE ?', "%#{query}%").order(boost: :desc)
    end
  end
end
