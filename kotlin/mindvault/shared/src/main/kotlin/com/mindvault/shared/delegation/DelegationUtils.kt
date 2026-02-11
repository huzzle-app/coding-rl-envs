package com.mindvault.shared.delegation

import kotlinx.serialization.*
import kotlinx.serialization.descriptors.*
import kotlinx.serialization.encoding.*


@Serializable(with = Event.Companion::class)
data class Event(val type: String, val data: String) {
    companion object : KSerializer<Event> {
        
        private var lastDecoded: Event? = null

        override val descriptor: SerialDescriptor = buildClassSerialDescriptor("Event") {
            element<String>("type")
            element<String>("data")
        }

        override fun serialize(encoder: Encoder, value: Event) {
            encoder.encodeStructure(descriptor) {
                encodeStringElement(descriptor, 0, value.type)
                encodeStringElement(descriptor, 1, value.data)
            }
        }

        override fun deserialize(decoder: Decoder): Event {
            return decoder.decodeStructure(descriptor) {
                var type = ""
                var data = ""
                while (true) {
                    when (val index = decodeElementIndex(descriptor)) {
                        0 -> type = decodeStringElement(descriptor, 0)
                        1 -> data = decodeStringElement(descriptor, 1)
                        CompositeDecoder.DECODE_DONE -> break
                        else -> error("Unexpected index: $index")
                    }
                }
                Event(type, data).also { lastDecoded = it } 
            }
        }
    }
}


// When delegated via `by`, `this` refers to delegate, not wrapper
interface Repository<T> {
    fun findAll(): List<T>
    fun count(): Int = findAll().size // `this` refers to delegate in `by` delegation
    fun className(): String = this::class.simpleName ?: "Unknown" // Returns delegate's class name
}
