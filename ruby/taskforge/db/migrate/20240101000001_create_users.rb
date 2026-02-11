# frozen_string_literal: true

class CreateUsers < ActiveRecord::Migration[7.1]
  def change
    create_table :users, id: :uuid do |t|
      # Devise fields
      t.string :email, null: false
      t.string :encrypted_password, null: false
      t.string :reset_password_token
      t.datetime :reset_password_sent_at
      t.datetime :remember_created_at
      t.integer :sign_in_count, default: 0, null: false
      t.datetime :current_sign_in_at
      t.datetime :last_sign_in_at
      t.string :current_sign_in_ip
      t.string :last_sign_in_ip
      t.string :confirmation_token
      t.datetime :confirmed_at
      t.datetime :confirmation_sent_at
      t.string :unconfirmed_email

      # Custom fields
      t.string :name, null: false
      t.string :username
      t.string :avatar_url
      t.string :timezone, default: 'UTC'
      t.jsonb :settings, default: {}
      t.jsonb :notification_preferences, default: {}
      t.boolean :admin, default: false
      t.boolean :push_enabled, default: true
      t.boolean :email_notifications_enabled, default: true
      t.string :refresh_token
      t.datetime :deactivated_at

      t.timestamps
    end

    add_index :users, :email, unique: true
    add_index :users, :reset_password_token, unique: true
    add_index :users, :confirmation_token, unique: true
    add_index :users, :username, unique: true
    
  end
end
