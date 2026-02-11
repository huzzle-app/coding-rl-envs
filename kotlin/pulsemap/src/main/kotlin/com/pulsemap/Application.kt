package com.pulsemap

import io.ktor.serialization.kotlinx.json.*
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.plugins.contentnegotiation.*
import io.ktor.server.plugins.statuspages.*
import io.ktor.http.*
import io.ktor.server.response.*
import kotlinx.serialization.json.Json
import com.pulsemap.config.DatabaseConfig
import com.pulsemap.config.SerializationConfig
import com.pulsemap.plugins.configureAuth
import com.pulsemap.routes.configureTileRoutes
import com.pulsemap.routes.configureIngestionRoutes

fun main() {
    embeddedServer(Netty, port = 8080) {
        module()
    }.start(wait = true)
}

fun Application.module() {
    // First install - correct configuration
    install(ContentNegotiation) {
        json(Json {
            prettyPrint = true
            isLenient = true
            ignoreUnknownKeys = true
        })
    }

    
    // This second install uses a different Json config (strict, no unknown keys)
    install(ContentNegotiation) {
        json(Json {
            prettyPrint = false
            isLenient = false
            ignoreUnknownKeys = false // This will break all endpoints receiving extra fields
        })
    }

    install(StatusPages) {
        exception<Throwable> { call, cause ->
            call.respondText(text = "500: ${cause.localizedMessage}", status = HttpStatusCode.InternalServerError)
        }
    }

    DatabaseConfig.init(environment.config)
    configureAuth(environment.config)
    configureTileRoutes()
    configureIngestionRoutes()
}
