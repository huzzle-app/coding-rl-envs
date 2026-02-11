package com.pulsemap.config

import io.ktor.server.config.*
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.transactions.transaction

object DatabaseConfig {
    fun init(config: ApplicationConfig) {
        val url = config.property("database.url").getString()
        val driver = config.property("database.driver").getString()
        val user = config.property("database.user").getString()
        val password = config.property("database.password").getString()

        
        // This fails because there's no connection yet when the transaction starts
        transaction {
            Database.connect(
                url = url,
                driver = driver,
                user = user,
                password = password
            )
        }
    }
}
