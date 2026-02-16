package com.fleetpulse.shared.util;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Collection utility methods used across all FleetPulse microservices.
 *
 * Provides convenience methods for creating type-safe collections,
 * safe list operations, and map merging.
 *
 * Bugs: B1, B2, B3
 * Categories: Memory/Data Structures
 */
public class CollectionUtils {

    private CollectionUtils() {
        // Utility class - prevent instantiation
    }

    // Bug B1: Suboptimal Set implementation for enum values.
    // Category: Memory/Data Structures

    /**
     * Creates an optimized Set for enum values.
     *
     * @param values the enum values to include in the set
     * @return a Set containing the provided enum values
     */
    public static <E extends Enum<E>> Set<E> createEnumSet(Collection<E> values) {
        return new HashSet<>(values);
    }

    // Bug B2: String concatenation in loop causes O(n^2) performance
    // and significant garbage collection pressure.
    // Category: Memory/Data Structures

    /**
     * Joins a list of strings with the given delimiter.
     *
     * @param strings   the strings to join
     * @param delimiter the delimiter to insert between strings
     * @return the joined string
     */
    public static String joinStrings(List<String> strings, String delimiter) {
        if (strings == null || strings.isEmpty()) {
            return "";
        }

        String result = "";
        for (int i = 0; i < strings.size(); i++) {
            result += strings.get(i);
            if (i < strings.size() - 1) {
                result += delimiter;
            }
        }
        return result;
    }

    // Bug B3: TreeMap with CASE_INSENSITIVE_ORDER comparator violates the
    // consistency-with-equals contract. The comparator treats "abc" and "ABC"
    // as equal, but String.equals() does not.
    // Category: Memory/Data Structures

    /**
     * Creates a case-insensitive string-keyed TreeMap.
     *
     * @return a new TreeMap with case-insensitive key ordering
     */
    public static <V> TreeMap<String, V> createCaseInsensitiveMap() {
        return new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
    }

    /**
     * Returns a safe, independent sublist (not a view) to avoid memory leaks.
     *
     * @param list      the source list
     * @param fromIndex start index (inclusive)
     * @param toIndex   end index (exclusive)
     * @return a new ArrayList containing the specified range
     */
    public static <T> List<T> safeSubList(List<T> list, int fromIndex, int toIndex) {
        if (list == null || list.isEmpty()) {
            return new ArrayList<>();
        }
        int from = Math.max(0, fromIndex);
        int to = Math.min(list.size(), toIndex);
        if (from >= to) {
            return new ArrayList<>();
        }
        // Return independent copy (not a view) to avoid holding reference to entire list
        return new ArrayList<>(list.subList(from, to));
    }

    /**
     * Merges two maps, with values from map2 overriding map1 on key conflicts.
     *
     * @param map1 the base map
     * @param map2 the override map
     * @return a new merged map
     */
    public static <K, V> Map<K, V> mergeMaps(Map<K, V> map1, Map<K, V> map2) {
        if (map1 == null && map2 == null) {
            return new HashMap<>();
        }
        if (map1 == null) {
            return new HashMap<>(map2);
        }
        if (map2 == null) {
            return new HashMap<>(map1);
        }
        Map<K, V> result = new HashMap<>(map1);
        result.putAll(map2);
        return result;
    }

    /**
     * Partitions a list into chunks of the specified size.
     *
     * @param list the source list
     * @param size the maximum chunk size
     * @return a list of sublists, each of at most 'size' elements
     */
    public static <T> List<List<T>> partition(List<T> list, int size) {
        if (list == null || list.isEmpty() || size <= 0) {
            return new ArrayList<>();
        }
        List<List<T>> partitions = new ArrayList<>();
        for (int i = 0; i < list.size(); i += size) {
            partitions.add(new ArrayList<>(list.subList(i, Math.min(i + size, list.size()))));
        }
        return partitions;
    }
}
