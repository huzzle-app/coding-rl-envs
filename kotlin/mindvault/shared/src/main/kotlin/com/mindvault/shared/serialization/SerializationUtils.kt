package com.mindvault.shared.serialization

import kotlinx.serialization.json.*

object SerializationUtils {
    
    // Should use JsonObject/JsonElement
    fun parseDynamic(jsonStr: String): Map<String, Any> {
        val element = Json.parseToJsonElement(jsonStr)
        return toMap(element.jsonObject) // Returns Map<String, Any> - not serializable back
    }

    private fun toMap(jsonObject: JsonObject): Map<String, Any> {
        return jsonObject.mapValues { (_, value) ->
            when (value) {
                is JsonPrimitive -> value.content
                is JsonArray -> value.map { it.toString() }
                is JsonObject -> toMap(value)
                else -> value.toString()
            }
        }
    }
}
