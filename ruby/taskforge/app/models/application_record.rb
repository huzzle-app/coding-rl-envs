# frozen_string_literal: true

class ApplicationRecord < ActiveRecord::Base
  primary_abstract_class

  
  def self.search(query, options = {})
    # options hash is shared across calls if mutated
    options[:limit] ||= 100
    where('name ILIKE ?', "%#{query}%").limit(options[:limit])
  end
end
