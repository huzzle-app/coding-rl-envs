# frozen_string_literal: true

class CreateOrganizations < ActiveRecord::Migration[7.1]
  def change
    create_table :organizations, id: :uuid do |t|
      t.string :name, null: false
      t.string :slug, null: false
      t.text :description
      t.string :logo_url
      t.string :status, default: 'active'
      t.integer :projects_count, default: 0
      t.string :external_id
      t.datetime :synced_at

      t.timestamps
    end

    add_index :organizations, :slug, unique: true
    add_index :organizations, :status

    create_table :organization_memberships, id: :uuid do |t|
      t.references :organization, type: :uuid, foreign_key: true, null: false
      t.references :user, type: :uuid, foreign_key: true, null: false
      t.string :role, default: 'member'

      t.timestamps
    end

    add_index :organization_memberships, [:organization_id, :user_id], unique: true
  end
end
