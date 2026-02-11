# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "products", force: :cascade do |t|
    t.string "name", null: false
    t.string "sku", null: false
    t.integer "stock", default: 0
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["sku"], name: "index_products_on_sku", unique: true
  end

  create_table "warehouses", force: :cascade do |t|
    t.string "name", null: false
    t.string "code", null: false
    t.string "address"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["code"], name: "index_warehouses_on_code", unique: true
  end

  create_table "warehouse_locations", force: :cascade do |t|
    t.bigint "product_id", null: false
    t.bigint "warehouse_id", null: false
    t.integer "quantity", default: 0
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["product_id", "warehouse_id"], name: "index_warehouse_locations_on_product_and_warehouse", unique: true
  end

  create_table "stock_movements", force: :cascade do |t|
    t.bigint "product_id", null: false
    t.bigint "warehouse_id", null: false
    t.bigint "user_id"
    t.integer "quantity", null: false
    t.string "movement_type", null: false
    t.string "reason", null: false
    t.bigint "reversed_movement_id"
    t.datetime "audited_at"
    t.datetime "reversed_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["product_id"], name: "index_stock_movements_on_product_id"
    t.index ["warehouse_id"], name: "index_stock_movements_on_warehouse_id"
  end

  create_table "reservations", force: :cascade do |t|
    t.bigint "product_id", null: false
    t.bigint "order_id"
    t.integer "quantity", null: false
    t.string "status", default: "pending"
    t.datetime "expires_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["product_id"], name: "index_reservations_on_product_id"
  end

  add_foreign_key "stock_movements", "products"
  add_foreign_key "stock_movements", "warehouses"
  add_foreign_key "warehouse_locations", "products"
  add_foreign_key "warehouse_locations", "warehouses"
  add_foreign_key "reservations", "products"
end
