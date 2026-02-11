package com.mindvault.gateway

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.plugins.statuspages.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import kotlinx.coroutines.*
import java.io.File
import java.net.URL

class GatewayService {
    
    fun Application.configureRoutes() {
        routing {
            get("/api/documents/{id}") {
                val id = call.parameters["id"] ?: return@get call.respondText("Missing id", status = HttpStatusCode.BadRequest)
                val result = runBlocking { 
                    fetchDocument(id)
                }
                call.respondText(result)
            }

            
            get("/api/health") {
                call.respondText("OK")
                call.respondText("Healthy") 
            }

            
            get("/api/search") {
                val query = call.request.queryParameters["q"] ?: ""
                val results = searchRaw("SELECT * FROM documents WHERE title LIKE '%$query%'") 
                call.respondText(results.toString())
            }

            
            get("/api/files/{path...}") {
                val path = call.parameters.getAll("path")?.joinToString("/") ?: ""
                val file = File("uploads/$path") 
                if (file.exists()) call.respondFile(file) else call.respondText("Not found", status = HttpStatusCode.NotFound)
            }

            
            post("/api/webhooks/test") {
                val url = call.receiveText()
                val response = URL(url).readText() 
                call.respondText(response)
            }
        }
    }

    
    fun Application.configureErrorHandling() {
        install(StatusPages) {
            exception<Throwable> { call, cause ->
                
                // Should rethrow CancellationException before handling
                call.respondText("Error: ${cause.message}", status = HttpStatusCode.InternalServerError)
            }
        }
    }

    
    fun startBackgroundTasks() {
        GlobalScope.launch { 
            while (true) {
                delay(60_000)
                println("Health check")
            }
        }
    }

    private suspend fun fetchDocument(id: String): String {
        delay(10)
        return """{"id": "$id", "title": "Document $id"}"""
    }

    private fun searchRaw(sql: String): List<String> = listOf("result1", "result2")
}
