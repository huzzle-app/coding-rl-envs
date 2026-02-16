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
 * Bugs: A8, A9, H1, H2, C4
 * Categories: Concurrency, Caching, Spring/DI
 */
@Service
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    private final Map<String, List<String>> templateCache = new ConcurrentHashMap<>();
    private final Map<String, Object> cache = new ConcurrentHashMap<>();

    // Bug A8: Volatile array reference does not make array elements volatile.
    // Modifications to individual elements may not be visible to other threads.
    // Category: Concurrency
    private volatile String[] notificationChannels = {"EMAIL", "SMS", "PUSH"};

    /**
     * Sends a notification on the specified channel.
     *
     * @param channel the delivery channel (EMAIL, SMS, PUSH)
     * @param userId  the recipient user ID
     * @param message the notification message body
     */
    // Bug A9: Synchronizing on String.intern() causes unrelated code blocking
    // when other code synchronizes on the same interned string value.
    // Category: Concurrency
    public void sendNotification(String channel, String userId, String message) {
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
    // Bug H1: Both getUserNotifications() and getUserPreferences() use the same
    // cache name "notifications" with key "#userId", causing cache key collision.
    // Category: Caching
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
    // Bug H1 (continued): Collides with getUserNotifications() above.
    // Category: Caching
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
    // Bug H2: When a cache entry is missing, all concurrent threads invoke the
    // loader independently instead of only one thread loading and others waiting.
    // Category: Caching
    public Object getCachedData(String key, Callable<Object> loader) {
        Object value = cache.get(key);
        if (value == null) {
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
    // Bug C4: Spring's default key generator may produce the same key for
    // getTemplate(Long) and getTemplate(String) when parameter values overlap.
    // Category: Spring/DI
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
    // Bug C4 (continued): Collides with getTemplate(Long) above.
    // Category: Spring/DI
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
        notificationChannels[index] = newChannel;
    }
}
