# frozen_string_literal: true

class Product < ApplicationRecord
  
  

  belongs_to :category
  belongs_to :brand, optional: true
  has_many :variants
  has_many :reviews
  has_many :images, as: :imageable

  validates :name, presence: true
  validates :sku, presence: true, uniqueness: true
  validates :price, numericality: { greater_than_or_equal_to: 0 }

  scope :active, -> { where(active: true) }
  scope :in_stock, -> { where('stock > 0') }

  
  before_save :publish_update_event
  after_save :update_search_index

  def increment_view_count!
    
    # Thread 1: reads view_count = 100
    # Thread 2: reads view_count = 100
    # Thread 1: writes view_count = 101
    # Thread 2: writes view_count = 101 (lost update)

    self.view_count += 1
    save!

    # Correct implementation:
    # increment!(:view_count)
    # Or: self.class.where(id: id).update_all('view_count = view_count + 1')
  end

  def record_purchase(quantity)
    
    self.purchase_count += quantity
    self.stock -= quantity
    save!
  end

  def as_json(options = {})
    super(options).merge(
      category_name: category&.name,
      brand_name: brand&.name,
      average_rating: average_rating,
      review_count: reviews.count  
    )
  end

  def average_rating
    
    @average_rating ||= reviews.average(:rating)&.round(1) || 0.0
  end

  private

  def publish_update_event
    
    # If save fails (validation, DB error), event is already sent
    # Consumers will see data that doesn't exist in DB

    KafkaProducer.publish('product.updated', {
      product_id: id,
      name: name,
      price: price,
      stock: stock,
      
      changed_fields: changes.keys
    })
  end

  def update_search_index
    # Index update should be idempotent
    SearchIndexJob.perform_later(id)
  end
end

# Correct implementation:
# # Use after_commit for side effects
# after_commit :publish_update_event, on: [:create, :update]
#
# def publish_update_event
#   KafkaProducer.publish('product.updated', {
#     product_id: id,
#     name: name,
#     price: price,
#     stock: stock,
#     # Use previous_changes after commit
#     changed_fields: previous_changes.keys
#   })
# end
#
# def increment_view_count!
#   # Atomic increment
#   self.class.where(id: id).update_all('view_count = view_count + 1')
#   reload
# end
