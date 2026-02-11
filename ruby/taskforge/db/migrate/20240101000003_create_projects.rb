# frozen_string_literal: true

class CreateProjects < ActiveRecord::Migration[7.1]
  def change
    create_table :projects, id: :uuid do |t|
      t.string :name, null: false
      t.string :slug, null: false
      t.text :description
      t.string :status, default: 'planning'
      t.string :visibility, default: 'private'
      t.date :due_date
      t.integer :tasks_count, default: 0
      t.integer :completed_tasks_count, default: 0
      t.integer :overdue_tasks_count, default: 0
      t.datetime :stats_updated_at
      t.references :organization, type: :uuid, foreign_key: true, null: false
      t.references :creator, type: :uuid, foreign_key: { to_table: :users }, null: false

      t.timestamps
    end

    add_index :projects, [:organization_id, :slug], unique: true
    

    create_table :project_memberships, id: :uuid do |t|
      t.references :project, type: :uuid, foreign_key: true, null: false
      t.references :user, type: :uuid, foreign_key: true, null: false
      t.string :role, default: 'member'

      t.timestamps
    end

    add_index :project_memberships, [:project_id, :user_id], unique: true
  end
end
