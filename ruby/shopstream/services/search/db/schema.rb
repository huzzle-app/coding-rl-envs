# This file is auto-generated from the current state of the database.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000001) do
  enable_extension "plpgsql"

  create_table "products", force: :cascade do |t|
    t.string "name", null: false
    t.string "sku", null: false
    t.decimal "price", precision: 10, scale: 2, null: false
    t.integer "stock", default: 0
    t.boolean "active", default: true
    t.bigint "category_id"
    t.bigint "brand_id"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["sku"], name: "index_products_on_sku", unique: true
    t.index ["category_id"], name: "index_products_on_category_id"
    t.index ["brand_id"], name: "index_products_on_brand_id"
  end

  create_table "search_queries", force: :cascade do |t|
    t.string "query", null: false
    t.bigint "user_id"
    t.string "ip_address"
    t.integer "result_count", default: 0
    t.text "filters"
    t.string "sort_by"
    t.string "sort_order"
    t.integer "page", default: 1
    t.integer "per_page", default: 20
    t.float "response_time_ms"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["query"], name: "index_search_queries_on_query"
    t.index ["user_id"], name: "index_search_queries_on_user_id"
    t.index ["created_at"], name: "index_search_queries_on_created_at"
  end

  create_table "search_indices", force: :cascade do |t|
    t.string "index_name", null: false
    t.string "document_type", null: false
    t.bigint "document_id", null: false
    t.text "content"
    t.text "metadata"
    t.float "boost", default: 1.0
    t.datetime "indexed_at"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["index_name", "document_type", "document_id"], name: "index_search_indices_on_document", unique: true
    t.index ["index_name"], name: "index_search_indices_on_index_name"
  end
end
