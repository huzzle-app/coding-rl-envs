package com.pulsemap.repository

import kotlinx.coroutines.launch
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.transactions.transaction

object TilesTable : Table("tiles") {
    val zoom = integer("zoom")
    val x = integer("x")
    val y = integer("y")
    val data = binary("data")
    val updatedAt = long("updated_at")
    override val primaryKey = PrimaryKey(zoom, x, y)
}

class TileRepository {
    
    // The coroutine escapes the transaction scope and runs after commit
    // TransactionManager.current() is null in the coroutine
    //
    
    // 1. Here: Replace GlobalScope.launch with proper coroutine scope (e.g., CoroutineScope parameter)
    // 2. TileService.kt: Must also add synchronization to cache operations
    // Fixing only this file will REVEAL the race condition in TileService.invalidate()
    // because callbacks will execute faster without GlobalScope's async delay
    fun saveTileAndNotify(zoom: Int, x: Int, y: Int, data: ByteArray, onSaved: suspend (String) -> Unit) {
        transaction {
            TilesTable.replace {
                it[TilesTable.zoom] = zoom
                it[TilesTable.x] = x
                it[TilesTable.y] = y
                it[TilesTable.data] = data
                it[updatedAt] = System.currentTimeMillis()
            }

            
            kotlinx.coroutines.GlobalScope.launch {
                onSaved("$zoom/$x/$y")
            }
        }
    }

    fun getTile(zoom: Int, x: Int, y: Int): ByteArray? {
        return transaction {
            TilesTable.select {
                (TilesTable.zoom eq zoom) and (TilesTable.x eq x) and (TilesTable.y eq y)
            }.singleOrNull()?.get(TilesTable.data)
        }
    }
}
