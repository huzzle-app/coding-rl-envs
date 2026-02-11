# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "users", force: :cascade do |t|
    t.string "email", null: false
    t.string "full_name", null: false
    t.string "password_digest"
    t.string "phone"
    t.boolean "active", default: true
    t.datetime "last_login_at"
    t.integer "failed_login_attempts", default: 0
    t.datetime "locked_until"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["email"], name: "index_users_on_email", unique: true
  end

  create_table "sessions", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "session_token", null: false
    t.string "ip_address"
    t.string "user_agent"
    t.datetime "expires_at", null: false
    t.datetime "last_accessed_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["session_token"], name: "index_sessions_on_session_token", unique: true
    t.index ["user_id"], name: "index_sessions_on_user_id"
  end

  create_table "api_keys", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "name", null: false
    t.string "key_hash", null: false
    t.string "key_prefix", null: false
    t.text "permissions", default: "[]"
    t.datetime "last_used_at"
    t.datetime "expires_at"
    t.boolean "active", default: true
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["key_hash"], name: "index_api_keys_on_key_hash", unique: true
    t.index ["user_id", "name"], name: "index_api_keys_on_user_id_and_name", unique: true
    t.index ["user_id"], name: "index_api_keys_on_user_id"
  end

  add_foreign_key "sessions", "users"
  add_foreign_key "api_keys", "users"
end
