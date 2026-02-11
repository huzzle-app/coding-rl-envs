# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "orders", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "status", default: "pending", null: false
    t.decimal "total_amount", precision: 10, scale: 2, default: "0.0"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["user_id"], name: "index_orders_on_user_id"
    t.index ["created_at"], name: "index_orders_on_created_at"
    t.index ["status"], name: "index_orders_on_status"
  end

  create_table "events", force: :cascade do |t|
    t.string "event_type", null: false
    t.bigint "user_id"
    t.string "entity_type"
    t.bigint "entity_id"
    t.text "properties"
    t.string "source"
    t.string "session_id"
    t.string "ip_address"
    t.string "user_agent"
    t.datetime "occurred_at", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["event_type"], name: "index_events_on_event_type"
    t.index ["user_id"], name: "index_events_on_user_id"
    t.index ["entity_type", "entity_id"], name: "index_events_on_entity"
    t.index ["occurred_at"], name: "index_events_on_occurred_at"
    t.index ["session_id"], name: "index_events_on_session_id"
  end

  create_table "reports", force: :cascade do |t|
    t.string "name", null: false
    t.string "report_type", null: false
    t.string "status", default: "pending"
    t.text "parameters"
    t.daterange "date_range"
    t.string "output_path"
    t.string "output_format", default: "json"
    t.bigint "created_by_id"
    t.integer "progress", default: 0
    t.datetime "started_at"
    t.datetime "completed_at"
    t.string "error_message"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["report_type"], name: "index_reports_on_report_type"
    t.index ["status"], name: "index_reports_on_status"
    t.index ["created_by_id"], name: "index_reports_on_created_by_id"
  end
end
