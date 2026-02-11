# frozen_string_literal: true

class CreateTasks < ActiveRecord::Migration[7.1]
  def change
    create_table :tasks, id: :uuid do |t|
      t.string :title, null: false
      t.text :description
      t.string :status, default: 'todo'
      t.string :priority, default: 'medium'
      t.date :due_date
      t.decimal :estimated_hours, precision: 8, scale: 2
      t.decimal :actual_hours, precision: 8, scale: 2
      t.integer :position
      t.datetime :completed_at
      t.jsonb :tags, default: []
      t.jsonb :metadata, default: {}

      t.references :project, type: :uuid, foreign_key: true, null: false
      t.references :creator, type: :uuid, foreign_key: { to_table: :users }, null: false
      t.references :assignee, type: :uuid, foreign_key: { to_table: :users }
      t.references :milestone, type: :uuid, foreign_key: true
      t.references :parent, type: :uuid, foreign_key: { to_table: :tasks }

      t.timestamps
    end

    add_index :tasks, [:project_id, :status]
    add_index :tasks, :due_date
    add_index :tasks, :assignee_id
    

    create_table :task_dependencies, id: :uuid do |t|
      t.references :task, type: :uuid, foreign_key: true, null: false
      t.references :dependency, type: :uuid, foreign_key: { to_table: :tasks }, null: false

      t.timestamps
    end

    add_index :task_dependencies, [:task_id, :dependency_id], unique: true
  end
end
