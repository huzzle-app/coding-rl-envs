# frozen_string_literal: true

class CreateCommentsAndNotifications < ActiveRecord::Migration[7.1]
  def change
    create_table :milestones, id: :uuid do |t|
      t.string :name, null: false
      t.text :description
      t.date :due_date
      t.string :status, default: 'open'
      t.references :project, type: :uuid, foreign_key: true, null: false

      t.timestamps
    end

    create_table :comments, id: :uuid do |t|
      t.text :body, null: false
      t.references :user, type: :uuid, foreign_key: true, null: false
      t.references :task, type: :uuid, foreign_key: true, null: false

      t.timestamps
    end

    add_index :comments, [:task_id, :created_at]

    create_table :mentions, id: :uuid do |t|
      t.references :comment, type: :uuid, foreign_key: true, null: false
      t.references :user, type: :uuid, foreign_key: true, null: false

      t.timestamps
    end

    create_table :attachments, id: :uuid do |t|
      t.string :filename, null: false
      t.string :content_type
      t.integer :file_size
      t.string :storage_key
      t.references :task, type: :uuid, foreign_key: true, null: false
      t.references :user, type: :uuid, foreign_key: true, null: false

      t.timestamps
    end

    create_table :notifications, id: :uuid do |t|
      t.string :notification_type, null: false
      t.string :message
      t.datetime :read_at
      t.references :user, type: :uuid, foreign_key: true, null: false
      t.references :notifiable, polymorphic: true, type: :uuid

      t.timestamps
    end

    
    add_index :notifications, :user_id
    add_index :notifications, :read_at

    create_table :activity_logs, id: :uuid do |t|
      t.string :action, null: false
      t.jsonb :changes_data, default: {}
      t.references :user, type: :uuid, foreign_key: true
      t.references :trackable, polymorphic: true, type: :uuid
      t.references :project, type: :uuid, foreign_key: true

      t.timestamps
    end

    add_index :activity_logs, [:project_id, :created_at]
  end
end
