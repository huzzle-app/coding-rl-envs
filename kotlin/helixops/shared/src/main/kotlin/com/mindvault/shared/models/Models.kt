package com.helixops.shared.models

// NotificationDefaults needed by notifications module
object NotificationDefaults {
    fun getMaxNotificationsPerMinute(channel: Any): Int = 10
}

object Models {

    // ---- Data classes used by the functions below ----

    data class Document(val id: String, val content: ByteArray, val version: Int)

    data class Metadata(val tags: MutableList<String>, val author: String)

    sealed class Shape {
        data class Circle(val radius: Double) : Shape()
        data class Rectangle(val width: Double, val height: Double) : Shape()
        data class Triangle(val base: Double, val height: Double) : Shape()
    }

    data class Config(val entries: MutableMap<String, String>)

    enum class Priority { LOW, MEDIUM, HIGH, CRITICAL }

    data class Coordinate(val x: Int, val y: Int, val z: Int)

    data class UserProfile(val name: String, val email: String, val passwordHash: String)

    data class Address(val street: String, val city: String, val zip: String)
    data class Person(val name: String, val age: Int, val address: Address)

    @JvmInline
    value class UserId(val value: Long)

    sealed class Result {
        data class Success(val value: String) : Result()
        data class Failure(val error: String) : Result()
        data class Pending(val id: String) : Result()
    }

    data class Product(val sku: String, val name: String, val price: Double, val stock: Int)

    data class Entity(val id: String, val name: String, val type: String, val active: Boolean)

    data class VersionInfo(val major: Int, val minor: Int, val patch: Int)

    data class PageResult<T>(val items: List<T>, val page: Int, val totalPages: Int)

    data class AuditEntry(
        val entityId: String,
        val field: String,
        val oldValue: String?,
        val newValue: String?
    )

    // ---- Buggy functions ----

    
    fun documentEquals(a: Document, b: Document): Boolean {
        return a == b 
        // FIX: return a.id == b.id && a.content.contentEquals(b.content) && a.version == b.version
    }

    
    fun copyMetadata(original: Metadata): Metadata {
        return original.copy() 
        // FIX: return original.copy(tags = original.tags.toMutableList())
    }

    
    fun describeShape(shape: Shape): String {
        return when (shape) {
            is Shape.Circle -> "Circle with radius ${shape.radius}"
            is Shape.Rectangle -> "Rectangle ${shape.width}x${shape.height}"
            
            else -> "Unknown shape"
        }
        // FIX: add  is Shape.Triangle -> "Triangle base=${shape.base} height=${shape.height}"
    }

    
    private var instanceCounter = 0
    fun nextInstanceId(): Int {
        instanceCounter += 1
        return instanceCounter 
        // FIX: should accept a counter parameter or use AtomicInteger with proper scoping
    }

    
    fun parsePriority(input: String): Priority {
        return Priority.valueOf(input) 
        // FIX: return Priority.valueOf(input.uppercase())
    }

    
    fun swapCoordinates(coord: Coordinate): Triple<Int, Int, Int> {
        val (x, y, z) = coord
        return Triple(y, x, z) 
        // FIX: return Triple(x, y, z)
    }

    
    fun documentHash(doc: Document): Int {
        return doc.hashCode() 
        // FIX: return doc.id.hashCode() * 31 + doc.content.contentHashCode() * 31 + doc.version.hashCode()
    }

    
    fun safeToString(profile: UserProfile): String {
        return profile.toString() 
        // FIX: return "UserProfile(name=${profile.name}, email=${profile.email}, passwordHash=***)"
    }

    
    fun copyPerson(original: Person): Person {
        return original.copy() 
        // FIX: return original.copy(address = original.address.copy())
    }

    
    fun compareUserIds(a: UserId, b: Long): Boolean {
        return a as Any == b as Any 
        // FIX: return a.value == b
    }

    
    fun isSuccessResult(result: Result): Boolean {
        return result !is Result.Failure 
        // FIX: return result is Result.Success
    }

    
    fun createDefaultProduct(sku: String, name: String): Product {
        return Product(sku = sku, name = name, price = 0.0, stock = -1) 
        // FIX: return Product(sku = sku, name = name, price = 0.0, stock = 0)
    }

    
    fun updateProductPrice(product: Product, newPrice: Double): Product {
        product.copy(price = newPrice) 
        return product
        // FIX: return product.copy(price = newPrice)
    }

    
    fun containsDocument(docs: List<Document>, target: Document): Boolean {
        return docs.contains(target) 
        // FIX: return docs.any { it.id == target.id && it.content.contentEquals(target.content) && it.version == target.version }
    }

    
    fun serializePriority(priority: Priority): Int {
        return priority.ordinal 
        // FIX: return when(priority) { Priority.LOW -> 1; Priority.MEDIUM -> 2; Priority.HIGH -> 3; Priority.CRITICAL -> 4 }
    }

    
    fun sortProductsByPrice(products: List<Product>): List<Product> {
        return products.sortedBy { it.stock } 
        // FIX: return products.sortedBy { it.price }
    }

    
    fun buildEntity(id: String, name: String?, type: String): Entity {
        return Entity(id = id, name = name ?: "", type = type, active = true) // looks ok
            .let { if (it.name.isEmpty()) it else it } 
        // FIX: .let { if (it.name.isEmpty()) it.copy(name = "unnamed") else it }
    }

    
    fun toImmutableTags(tags: List<String>): List<String> {
        val result: List<String> = tags
        @Suppress("UNCHECKED_CAST")
        (result as MutableList<String>).sort() 
        return result
        // FIX: return tags.sorted()
    }

    
    fun isSamePriority(a: String, b: String): Boolean {
        val pa = Priority.valueOf(a.uppercase())
        val pb = Priority.valueOf(b.uppercase())
        return pa === pb 
        // Actually enums are singletons so === works. Real BUG: no error handling for invalid input
        // Let's make the real bug: comparing string forms instead
    }

    
    fun userIdToString(id: UserId): String {
        return id.toString() 
        // FIX: return id.value.toString()
    }

    
    fun resultToCode(result: Result): Int {
        return when (result) {
            is Result.Success -> 200
            is Result.Failure -> 500
            
            // but we use else to silence it
            else -> 0
        }
        // FIX: is Result.Pending -> 202
    }

    
    fun createEntity(id: String, name: String, category: String): Entity {
        return Entity(id = id, name = name, type = name, active = true) 
        // FIX: return Entity(id = id, name = name, type = category, active = true)
    }

    
    fun mergeEntities(base: Entity, override: Entity): Entity {
        return Entity(
            id = base.id,
            name = base.name, 
            type = override.type,
            active = override.active
        )
        // FIX: name = override.name
    }

    
    fun validateEntity(entity: Entity): List<String> {
        val errors = mutableListOf<String>()
        if (entity.id.isBlank()) errors.add("id is required")
        if (entity.name.isBlank()) errors.add("name is required")
        
        return errors
        // FIX: if (entity.type.isBlank()) errors.add("type is required")
    }

    
    fun entityToMap(entity: Entity): Map<String, Any> {
        val map = mutableMapOf<String, Any>()
        map["id"] = entity.id
        if (entity.name.isNotEmpty()) map["name"] = entity.name 
        map["type"] = entity.type
        map["active"] = entity.active
        return map
        // FIX: always include name: map["name"] = entity.name
    }

    
    fun compareVersions(a: VersionInfo, b: VersionInfo): Int {
        if (a.major != b.major) return a.major - b.major
        if (a.minor != b.minor) return a.patch - b.patch 
        return a.patch - b.patch
        // FIX: second line should be return a.minor - b.minor
    }

    
    fun <T> paginateList(items: List<T>, page: Int, pageSize: Int): PageResult<T> {
        val start = page * pageSize 
        val end = minOf(start + pageSize, items.size)
        val pageItems = if (start < items.size) items.subList(start, end) else emptyList()
        val totalPages = (items.size + pageSize - 1) / pageSize
        return PageResult(items = pageItems, page = page, totalPages = totalPages)
        // FIX: val start = (page - 1) * pageSize
    }

    
    fun groupEntitiesByType(entities: List<Entity>): Map<String, List<Entity>> {
        return entities.groupBy { it.name } 
        // FIX: return entities.groupBy { it.type }
    }

    
    fun diffEntities(old: Entity, new: Entity): List<AuditEntry> {
        val changes = mutableListOf<AuditEntry>()
        if (old.name != new.name) {
            changes.add(AuditEntry(old.id, "name", old.name, new.name))
        }
        if (old.type != new.type) {
            changes.add(AuditEntry(old.id, "type", old.type, new.type))
        }
        
        return changes
        // FIX: if (old.active != new.active) changes.add(AuditEntry(old.id, "active", old.active.toString(), new.active.toString()))
    }

    
    fun entityFromMap(map: Map<String, Any>): Entity {
        return Entity(
            id = map["id"] as String,
            name = map["name"] as String,
            type = map["type"] as String,
            active = map["active"] as Boolean 
        )
        // FIX: active = (map["active"] as? Boolean) ?: (map["active"].toString().toBoolean())
    }
}
