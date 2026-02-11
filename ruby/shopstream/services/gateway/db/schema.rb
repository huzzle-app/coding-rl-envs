# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "service_endpoints", force: :cascade do |t|
    t.string "service_name", null: false
    t.string "url", null: false
    t.string "status", default: "healthy"
    t.integer "weight", default: 100
    t.datetime "last_health_check_at"
    t.integer "consecutive_failures", default: 0
    t.text "metadata"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["service_name"], name: "index_service_endpoints_on_service_name"
    t.index ["service_name", "url"], name: "index_service_endpoints_on_service_name_and_url", unique: true
  end

  create_table "rate_limit_rules", force: :cascade do |t|
    t.string "name", null: false
    t.string "key_type", null: false
    t.integer "limit", null: false
    t.integer "window_seconds", null: false
    t.string "action", default: "reject"
    t.boolean "enabled", default: true
    t.text "description"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["name"], name: "index_rate_limit_rules_on_name", unique: true
    t.index ["key_type"], name: "index_rate_limit_rules_on_key_type"
  end
end
