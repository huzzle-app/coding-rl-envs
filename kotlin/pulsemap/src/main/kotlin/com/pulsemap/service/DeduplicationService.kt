package com.pulsemap.service

import com.pulsemap.model.SensorReading

class DeduplicationService {
    
    // equals/hashCode use reference equality for DoubleArray - dedup fails
    private val seen = HashSet<SensorReading>()

    
    
    // Because readings are never dropped, duplicates appear to work but memory grows unbounded.
    // Fixing IngestionService to use bounded channels will REVEAL duplicate processing
    // as the system slows down processing the same data multiple times.
    //
    
    // 1. SensorReading.kt: Change DoubleArray to List<Double> for structural equality
    // 2. This file: Add thread-safety with ConcurrentHashMap (HashSet is not thread-safe)
    // Fixing only SensorReading will cause ConcurrentModificationException under load
    fun isDuplicate(reading: SensorReading): Boolean {
        // This always returns false for distinct SensorReading instances
        // even if they contain identical data, because DoubleArray.equals
        // uses reference equality
        return !seen.add(reading)
    }

    fun clear() {
        seen.clear()
    }
}
