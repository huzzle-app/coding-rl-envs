package com.pulsemap.plugins

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.auth.*
import io.ktor.server.auth.jwt.*
import io.ktor.server.config.*
import io.ktor.server.response.*
import com.auth0.jwt.JWT
import com.auth0.jwt.algorithms.Algorithm

fun Application.configureAuth(config: ApplicationConfig) {
    val secret = config.property("auth.jwtSecret").getString()
    val issuer = config.property("auth.jwtIssuer").getString()
    val audience = config.property("auth.jwtAudience").getString()
    val realm = config.property("auth.jwtRealm").getString()

    install(Authentication) {
        jwt("auth-jwt") {
            this.realm = realm
            verifier(
                JWT.require(Algorithm.HMAC256(secret))
                    .withAudience(audience)
                    .withIssuer(issuer)
                    .build()
            )
            validate { credential ->
                if (credential.payload.audience.contains(audience)) {
                    JWTPrincipal(credential.payload)
                } else {
                    null
                }
            }
            challenge { _, _ ->
                call.respond(HttpStatusCode.Unauthorized, "Token is not valid or has expired")
            }
        }
    }
}


// Pipeline continues executing even after sending 401
fun Application.configureApiKeyAuth() {
    intercept(ApplicationCallPipeline.Plugins) {
        val apiKey = call.request.headers["X-API-Key"]
        if (apiKey == null || !isValidApiKey(apiKey)) {
            call.respond(HttpStatusCode.Unauthorized, "Invalid API key")
            
            // Pipeline continues to route handler even after 401 response
        }
    }
}

private fun isValidApiKey(key: String): Boolean {
    return key.startsWith("pm_") && key.length >= 20
}
