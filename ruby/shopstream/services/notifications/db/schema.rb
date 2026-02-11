# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "notifications", force: :cascade do |t|
    t.bigint "user_id"
    t.string "notification_type", null: false
    t.string "channel", null: false
    t.string "status", default: "pending"
    t.string "recipient", null: false
    t.string "subject"
    t.text "body"
    t.text "metadata"
    t.datetime "scheduled_at"
    t.datetime "sent_at"
    t.datetime "delivered_at"
    t.datetime "read_at"
    t.string "error_message"
    t.integer "retry_count", default: 0
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["user_id"], name: "index_notifications_on_user_id"
    t.index ["status"], name: "index_notifications_on_status"
    t.index ["notification_type"], name: "index_notifications_on_notification_type"
    t.index ["scheduled_at"], name: "index_notifications_on_scheduled_at"
  end

  create_table "notification_templates", force: :cascade do |t|
    t.string "name", null: false
    t.string "notification_type", null: false
    t.string "channel", null: false
    t.string "subject_template"
    t.text "body_template", null: false
    t.text "default_variables"
    t.boolean "active", default: true
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["name"], name: "index_notification_templates_on_name", unique: true
    t.index ["notification_type", "channel"], name: "index_notification_templates_on_type_and_channel"
  end
end
