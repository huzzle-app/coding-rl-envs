package com.pulsemap.repository

import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.transactions.transaction

object SensorsTable : Table("sensors") {
    val id = varchar("id", 50)
    val sensorId = varchar("sensor_id", 50)
    val name = varchar("name", 255).nullable()
    val latitude = double("latitude")
    val longitude = double("longitude")
    val value = double("value")
    val timestamp = long("timestamp")
    override val primaryKey = PrimaryKey(id)
}

class SensorRepository {
    fun insertSensor(id: String, sensorId: String, name: String?, lat: Double, lng: Double, value: Double, ts: Long) {
        transaction {
            SensorsTable.insert {
                it[SensorsTable.id] = id
                it[SensorsTable.sensorId] = sensorId
                
                // If name is null, the column is skipped entirely, causing NOT NULL constraint violation
                // if the column has a default, or inserting null into non-null context
                name?.let { n -> it[SensorsTable.name] = n }
                it[latitude] = lat
                it[longitude] = lng
                it[SensorsTable.value] = value
                it[timestamp] = ts
            }
        }
    }

    
    // Generates RETURNING * for every row - massive overhead on large batches
    fun bulkInsert(sensors: List<Map<String, Any>>) {
        transaction {
            SensorsTable.batchInsert(sensors) { sensor ->
                this[SensorsTable.id] = sensor["id"] as String
                this[SensorsTable.sensorId] = sensor["sensorId"] as String
                this[SensorsTable.name] = sensor["name"] as? String
                this[SensorsTable.latitude] = sensor["latitude"] as Double
                this[SensorsTable.longitude] = sensor["longitude"] as Double
                this[SensorsTable.value] = sensor["value"] as Double
                this[SensorsTable.timestamp] = sensor["timestamp"] as Long
            }
        }
    }

    
    fun searchByName(name: String): List<ResultRow> {
        return transaction {
            // VULNERABLE: String interpolation in raw SQL
            exec("SELECT * FROM sensors WHERE name = '$name'") { rs ->
                val results = mutableListOf<ResultRow>()
                // Parse results...
                results
            } ?: emptyList()
        }
    }

    fun findById(id: String): ResultRow? {
        return transaction {
            SensorsTable.select { SensorsTable.id eq id }.singleOrNull()
        }
    }
}
