package com.fleetpulse.notifications.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.*;

/**
 * Service managing notification delivery, template caching, and channel
 * configuration for the FleetPulse notification system.
 *
 * Contains intentional bugs:
 *   A8 - Volatile array reference does not make array elements volatile
 *   A9 - Synchronized on String.intern() causes unrelated code blocking
 *   H1 - Cache key collision between different data types
 *   H2 - Thundering herd / cache stampede on cache miss
 *   C4 - @Cacheable key collision for overloaded methods
 */
@Service
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    private final Map<String, List<String>> templateCache = new ConcurrentHashMap<>();
    private final Map<String, Object> cache = new ConcurrentHashMap<>();

    
    // The volatile keyword guarantees visibility of the array reference itself (i.e.,
    // if the entire array is replaced, all threads see the new array). However, it does
    // NOT guarantee visibility of modifications to individual array elements. When one
    // thread calls updateChannel(0, "WEBHOOK"), other threads may still see "EMAIL" at
    // index 0 due to CPU cache inconsistency.
    // Fix: Use AtomicReferenceArray<String> instead:
    //   private final AtomicReferenceArray<String> notificationChannels =
    //       new AtomicReferenceArray<>(new String[]{"EMAIL", "SMS", "PUSH"});
    private volatile String[] notificationChannels = {"EMAIL", "SMS", "PUSH"};

    /**
     * Sends a notification on the specified channel.
     *
     * @param channel the delivery channel (EMAIL, SMS, PUSH)
     * @param userId  the recipient user ID
     * @param message the notification message body
     */
    
    // String.intern() returns the canonical representation from the JVM string pool.
    // All code anywhere in the JVM that synchronizes on the same interned string
    // value will contend for the same lock. For example, if another library also
    // synchronizes on "EMAIL".intern(), it will block when this method holds the lock.
    // Additionally, the string pool lock itself can become a bottleneck.
    // Fix: Use a dedicated lock object per channel:
    //   private final ConcurrentHashMap<String, Object> channelLocks = new ConcurrentHashMap<>();
    //   Object lock = channelLocks.computeIfAbsent(channel, k -> new Object());
    //   synchronized (lock) { ... }
    public void sendNotification(String channel, String userId, String message) {
        
        // on the same lock if they also intern the same string value
        synchronized (channel.intern()) {
            log.info("Sending {} notification to {}: {}", channel, userId, message);
            // Simulate sending
            try { Thread.sleep(50); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    /**
     * Retrieves notifications for a user (cached).
     *
     * @param userId the user ID
     * @return list of notification messages
     */
    
    // Both getUserNotifications() and getUserPreferences() use cache name "notifications"
    // with key "#userId". When getUserNotifications(42) is cached, a subsequent call to
    // getUserPreferences(42) returns the notifications list instead of preferences,
    // because they share the same cache entry.
    // Fix: Use distinct cache names:
    //   @Cacheable(value = "user-notifications", key = "#userId")
    //   @Cacheable(value = "user-preferences", key = "#userId")
    @Cacheable(value = "notifications", key = "#userId")
    public List<String> getUserNotifications(Long userId) {
        log.info("Loading notifications for user: {}", userId);
        return List.of("Welcome notification", "System update");
    }

    /**
     * Retrieves notification preferences for a user (cached).
     *
     * @param userId the user ID
     * @return list of preference strings
     */
    
    // collides with getUserNotifications() above - returns wrong data type
    @Cacheable(value = "notifications", key = "#userId")
    public List<String> getUserPreferences(Long userId) {
        log.info("Loading preferences for user: {}", userId);
        return List.of("email=true", "sms=false");
    }

    /**
     * Retrieves data from the application cache, loading it via the supplied
     * callable if not already present.
     *
     * @param key    the cache key
     * @param loader a callable that produces the value on cache miss
     * @return the cached or freshly loaded value
     */
    
    // When a cache entry is missing or expired, all concurrent threads see the
    // null value simultaneously and each one invokes the loader independently.
    // If the loader is expensive (e.g., a database query), this can overwhelm
    // the backend with N identical requests instead of 1.
    // Fix: Use ConcurrentHashMap.computeIfAbsent() which is atomic:
    //   return cache.computeIfAbsent(key, k -> {
    //       try { return loader.call(); }
    //       catch (Exception e) { throw new RuntimeException(e); }
    //   });
    public Object getCachedData(String key, Callable<Object> loader) {
        Object value = cache.get(key);
        if (value == null) {
            
            // Each one calls the loader, potentially overwhelming the backend
            try {
                value = loader.call();
                cache.put(key, value);
            } catch (Exception e) {
                log.error("Cache load failed for key: {}", key, e);
            }
        }
        return value;
    }

    /**
     * Retrieves a notification template by numeric ID (cached).
     *
     * @param id the template ID
     * @return the template content
     */
    
    // Spring's default key generator (SimpleKeyGenerator) uses the method
    // parameters as the cache key. When getTemplate(Long) and getTemplate(String)
    // both use cache "templates", a call to getTemplate(1L) and getTemplate("1")
    // may produce the same key (depending on key generator implementation),
    // returning the wrong template type.
    // Fix: Specify explicit key generators or use different cache names:
    //   @Cacheable(value = "templates-by-id", key = "#id")
    //   @Cacheable(value = "templates-by-name", key = "#name")
    @Cacheable(value = "templates")
    public String getTemplate(Long id) {
        return "Template for ID: " + id;
    }

    /**
     * Retrieves a notification template by name (cached).
     *
     * @param name the template name
     * @return the template content
     */
    
    // collides with getTemplate(Long) above when parameter values overlap
    @Cacheable(value = "templates")
    public String getTemplate(String name) {
        return "Template for name: " + name;
    }

    /**
     * Returns the current array of notification channel names.
     *
     * @return the channel names array
     */
    public String[] getNotificationChannels() {
        return notificationChannels;
    }

    /**
     * Updates a notification channel name at the given index.
     *
     * @param index      the array index to update
     * @param newChannel the new channel name
     */
    public void updateChannel(int index, String newChannel) {
        
        // to other threads despite the array reference being volatile.
        // Volatile only protects the reference, not element-level writes.
        notificationChannels[index] = newChannel;
    }
}
