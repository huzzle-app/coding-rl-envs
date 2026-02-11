package com.pulsemap.routes

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import com.pulsemap.service.TileService
import kotlinx.coroutines.runBlocking
import java.io.File

fun Application.configureTileRoutes() {
    val tileService = TileService()

    routing {
        get("/tiles/{z}/{x}/{y}") {
            val z = call.parameters["z"]?.toIntOrNull() ?: return@get call.respondText("Invalid z", status = HttpStatusCode.BadRequest)
            val x = call.parameters["x"]?.toIntOrNull() ?: return@get call.respondText("Invalid x", status = HttpStatusCode.BadRequest)
            val y = call.parameters["y"]?.toIntOrNull() ?: return@get call.respondText("Invalid y", status = HttpStatusCode.BadRequest)

            
            // Ktor route handlers already run in a coroutine context
            val tileData = runBlocking {
                tileService.getTile(z, x, y)
            }

            if (tileData != null) {
                call.respondBytes(tileData, ContentType.Image.PNG)
            } else {
                call.respondText("Tile not found", status = HttpStatusCode.NotFound)
            }
        }

        
        get("/static/tiles/{path...}") {
            val path = call.parameters.getAll("path")?.joinToString("/") ?: ""
            // VULNERABLE: No path validation, allows ../../etc/passwd
            val file = File("tiles/$path")
            if (file.exists()) {
                call.respondFile(file)
            } else {
                call.respondText("Not found", status = HttpStatusCode.NotFound)
            }
        }
    }
}
