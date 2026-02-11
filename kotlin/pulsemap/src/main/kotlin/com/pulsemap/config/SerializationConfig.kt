package com.pulsemap.config

import com.pulsemap.model.*
import kotlinx.serialization.json.Json
import kotlinx.serialization.modules.SerializersModule
import kotlinx.serialization.modules.polymorphic
import kotlinx.serialization.modules.subclass

object SerializationConfig {
    val json = Json {
        ignoreUnknownKeys = true
        serializersModule = SerializersModule {
            polymorphic(QueryFilter::class) {
                subclass(QueryFilter.BoundingBoxFilter::class)
                subclass(QueryFilter.PolygonFilter::class)
                
                // subclass(QueryFilter.RadiusFilter::class)
            }
        }
    }
}
