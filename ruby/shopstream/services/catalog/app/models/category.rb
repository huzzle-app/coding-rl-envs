# frozen_string_literal: true

class Category < ApplicationRecord
  

  belongs_to :parent, class_name: 'Category', optional: true
  has_many :children, class_name: 'Category', foreign_key: :parent_id
  has_many :products

  validates :name, presence: true
  validates :slug, presence: true, uniqueness: true

  
  belongs_to :parent, class_name: 'Category', optional: true, touch: true

  before_save :generate_slug
  before_save :update_full_path
  
  after_save :touch_ancestors

  def ancestors
    result = []
    current = parent

    while current
      result << current
      current = current.parent
    end

    result.reverse
  end

  def descendants
    result = children.to_a

    children.each do |child|
      result.concat(child.descendants)
    end

    result
  end

  def full_path
    (ancestors.map(&:name) + [name]).join(' > ')
  end

  def move_to(new_parent)
    
    # Which triggers their parents, etc.
    self.parent = new_parent
    save!

    # Update all descendants' paths
    
    descendants.each do |descendant|
      descendant.update_full_path
      descendant.save!  # Triggers callback loop
    end
  end

  def product_count
    products.count + children.sum(&:product_count)
  end

  private

  def generate_slug
    self.slug ||= name.parameterize
  end

  def update_full_path
    self.cached_path = full_path
  end

  def touch_ancestors
    
    # Which touches its parent, etc.
    # If there's a cycle or deep hierarchy, this explodes
    parent&.touch
    parent&.touch_ancestors if parent  
  end
end

# Correct implementation:
# # Remove touch: true from parent association
# belongs_to :parent, class_name: 'Category', optional: true
#
# # Use update_column to skip callbacks when just updating timestamps
# def touch_ancestors
#   return unless parent_id
#
#   ancestor_ids = []
#   current = parent
#
#   while current
#     ancestor_ids << current.id
#     current = current.parent
#   end
#
#   # Single query to update all ancestors
#   Category.where(id: ancestor_ids).update_all(updated_at: Time.current)
# end
#
# def move_to(new_parent)
#   self.parent = new_parent
#
#   Category.transaction do
#     save!
#
#     # Use update_all to skip callbacks
#     descendant_ids = descendants.map(&:id)
#     descendants.each do |d|
#       Category.where(id: d.id).update_all(
#         cached_path: d.full_path,
#         updated_at: Time.current
#       )
#     end
#   end
# end
