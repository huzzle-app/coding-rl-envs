package com.mindvault.shared.observability

import kotlinx.coroutines.CancellationException
import org.slf4j.LoggerFactory
import org.slf4j.MDC

object Logging {
    private val logger = LoggerFactory.getLogger(Logging::class.java)

    
    fun handleException(e: Throwable) {
        logger.debug("Unhandled exception: ${e.message}", e) 
    }

    
    inline fun <T> safeCatching(block: () -> T): Result<T> {
        return runCatching(block)
        
        // .onFailure { if (it is CancellationException) throw it }
    }
}
