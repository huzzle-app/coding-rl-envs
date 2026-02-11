# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "shipments", force: :cascade do |t|
    t.bigint "order_id", null: false
    t.bigint "carrier_id"
    t.string "tracking_number"
    t.string "status", default: "pending"
    t.string "carrier_name"
    t.decimal "weight", precision: 8, scale: 2
    t.string "dimensions"
    t.datetime "shipped_at"
    t.datetime "delivered_at"
    t.datetime "estimated_delivery_at"
    t.text "shipping_address"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["order_id"], name: "index_shipments_on_order_id"
    t.index ["carrier_id"], name: "index_shipments_on_carrier_id"
    t.index ["tracking_number"], name: "index_shipments_on_tracking_number"
    t.index ["status"], name: "index_shipments_on_status"
  end

  create_table "carriers", force: :cascade do |t|
    t.string "name", null: false
    t.string "code", null: false
    t.string "api_endpoint"
    t.string "api_key"
    t.boolean "active", default: true
    t.text "supported_services"
    t.text "tracking_url_template"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["code"], name: "index_carriers_on_code", unique: true
  end

  create_table "shipping_rates", force: :cascade do |t|
    t.bigint "carrier_id", null: false
    t.string "service_level", null: false
    t.string "origin_zone"
    t.string "destination_zone"
    t.decimal "base_rate", precision: 10, scale: 2, null: false
    t.decimal "per_lb_rate", precision: 10, scale: 2, default: "0.0"
    t.decimal "fuel_surcharge_pct", precision: 5, scale: 2, default: "0.0"
    t.integer "min_days"
    t.integer "max_days"
    t.boolean "active", default: true
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["carrier_id"], name: "index_shipping_rates_on_carrier_id"
    t.index ["carrier_id", "service_level", "origin_zone", "destination_zone"], name: "index_shipping_rates_on_route", unique: true
  end

  add_foreign_key "shipments", "carriers"
  add_foreign_key "shipping_rates", "carriers"
end
