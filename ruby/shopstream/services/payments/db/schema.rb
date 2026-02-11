# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "orders", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "status", default: "pending", null: false
    t.decimal "total_amount", precision: 10, scale: 2, default: "0.0"
    t.decimal "subtotal", precision: 10, scale: 2, default: "0.0"
    t.decimal "tax_amount", precision: 10, scale: 2, default: "0.0"
    t.decimal "shipping_amount", precision: 10, scale: 2, default: "0.0"
    t.decimal "discount_amount", precision: 10, scale: 2, default: "0.0"
    t.string "payment_status", default: "pending"
    t.string "payment_id"
    t.datetime "paid_at"
    t.string "payment_error"
    t.decimal "total_refunded", precision: 10, scale: 2, default: "0.0"
    t.integer "lock_version", default: 0
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["user_id"], name: "index_orders_on_user_id"
    t.index ["payment_status"], name: "index_orders_on_payment_status"
  end

  create_table "line_items", force: :cascade do |t|
    t.bigint "order_id", null: false
    t.bigint "product_id", null: false
    t.integer "quantity", null: false
    t.decimal "unit_price", precision: 10, scale: 2, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["order_id"], name: "index_line_items_on_order_id"
    t.index ["product_id"], name: "index_line_items_on_product_id"
  end

  create_table "products", force: :cascade do |t|
    t.string "name", null: false
    t.string "sku", null: false
    t.decimal "price", precision: 10, scale: 2, null: false
    t.decimal "current_price", precision: 10, scale: 2
    t.integer "stock", default: 0
    t.boolean "active", default: true
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["sku"], name: "index_products_on_sku", unique: true
  end

  create_table "transactions", force: :cascade do |t|
    t.bigint "order_id", null: false
    t.decimal "amount", precision: 10, scale: 2, null: false
    t.string "status", null: false
    t.string "transaction_type", null: false
    t.string "external_id"
    t.string "idempotency_key"
    t.string "payment_method"
    t.string "currency", default: "USD"
    t.text "metadata"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["order_id"], name: "index_transactions_on_order_id"
    t.index ["idempotency_key"], name: "index_transactions_on_idempotency_key", unique: true
    t.index ["external_id"], name: "index_transactions_on_external_id"
  end

  create_table "refunds", force: :cascade do |t|
    t.bigint "order_id", null: false
    t.bigint "transaction_id"
    t.decimal "amount", precision: 10, scale: 2, null: false
    t.string "status", null: false
    t.string "reason"
    t.string "external_id"
    t.datetime "processed_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["order_id"], name: "index_refunds_on_order_id"
    t.index ["transaction_id"], name: "index_refunds_on_transaction_id"
  end

  create_table "payment_methods", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "method_type", null: false
    t.string "token", null: false
    t.string "last_four"
    t.string "brand"
    t.integer "exp_month"
    t.integer "exp_year"
    t.boolean "default", default: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["user_id"], name: "index_payment_methods_on_user_id"
    t.index ["token"], name: "index_payment_methods_on_token", unique: true
  end

  create_table "accounts", force: :cascade do |t|
    t.string "name", null: false
    t.string "account_type", null: false
    t.decimal "balance", precision: 15, scale: 2, default: "0.0"
    t.string "currency", default: "USD"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
  end

  create_table "ledger_entries", force: :cascade do |t|
    t.bigint "account_id", null: false
    t.decimal "amount", precision: 15, scale: 2, null: false
    t.decimal "balance_after", precision: 15, scale: 2, null: false
    t.string "entry_type", null: false
    t.string "reference"
    t.text "description"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["account_id"], name: "index_ledger_entries_on_account_id"
    t.index ["reference"], name: "index_ledger_entries_on_reference"
  end

  add_foreign_key "line_items", "orders"
  add_foreign_key "line_items", "products"
  add_foreign_key "transactions", "orders"
  add_foreign_key "refunds", "orders"
  add_foreign_key "refunds", "transactions"
  add_foreign_key "ledger_entries", "accounts"
end
