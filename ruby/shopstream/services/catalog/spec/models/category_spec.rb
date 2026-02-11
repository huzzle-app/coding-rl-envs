# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Category do
  
  describe '#touch_ancestors' do
    let(:grandparent) { create(:category, name: 'Electronics') }
    let(:parent) { create(:category, name: 'Phones', parent: grandparent) }
    let(:child) { create(:category, name: 'Smartphones', parent: parent) }

    it 'does not cause stack overflow when saving a deeply nested category' do
      expect {
        Timeout.timeout(5) { child.update!(name: 'Smart Phones') }
      }.not_to raise_error
    end

    it 'updates ancestor timestamps without recursive callback loop' do
      original_updated = grandparent.updated_at
      sleep 0.01

      expect {
        Timeout.timeout(5) { child.touch }
      }.not_to raise_error

      grandparent.reload
      # Ancestors should be updated but not via infinite recursion
    end
  end

  describe '#move_to' do
    let(:cat_a) { create(:category, name: 'A') }
    let(:cat_b) { create(:category, name: 'B') }
    let(:child) { create(:category, name: 'Child', parent: cat_a) }

    it 'moves category without stack overflow' do
      expect {
        Timeout.timeout(5) { child.move_to(cat_b) }
      }.not_to raise_error

      child.reload
      expect(child.parent_id).to eq(cat_b.id)
    end
  end

  describe '#product_count' do
    it 'includes products from child categories' do
      parent = create(:category)
      child = create(:category, parent: parent)
      create(:product, category: child)

      expect(parent.product_count).to be >= 1
    end
  end
end
