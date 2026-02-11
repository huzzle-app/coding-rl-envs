package com.pulsemap.routes

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import com.pulsemap.model.SensorReading
import com.pulsemap.service.IngestionService
import kotlinx.serialization.json.Json

fun Application.configureIngestionRoutes() {
    val ingestionService = IngestionService()

    routing {
        post("/ingest") {
            
            // Bypasses Ktor's content type checking and error handling
            val body = call.receiveText()
            val reading = try {
                Json.decodeFromString<SensorReading>(body)
            } catch (e: Exception) {
                // Raw parse exception leaks to client
                return@post call.respondText("Parse error: ${e.message}", status = HttpStatusCode.BadRequest)
            }

            ingestionService.ingest(reading)
            call.respondText("OK", status = HttpStatusCode.Created)
        }

        post("/ingest/batch") {
            val body = call.receiveText()
            
            val payload = Json.parseToJsonElement(body)
            val readings = payload as kotlinx.serialization.json.JsonArray  
            call.respondText("Ingested ${readings.size} readings", status = HttpStatusCode.Created)
        }
    }
}
