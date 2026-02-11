package com.pulsemap.util

import kotlinx.serialization.json.Json
import kotlinx.serialization.serializer

object JsonUtils {
    val json = Json { ignoreUnknownKeys = true }

    
    inline fun <reified T> deserialize(jsonStr: String): T {
        return json.decodeFromString(serializer(), jsonStr)
    }

    
    // At runtime, type information is erased, causing serialization failure
    // The @Suppress allows compilation but causes ClassCastException at runtime
    @Suppress("UNCHECKED_CAST")
    fun <T> processAndDeserialize(jsonStr: String): T {
        val cleaned = jsonStr.trim()
        
        return deserialize<Any>(cleaned) as T // Will throw ClassCastException at runtime
    }
}
