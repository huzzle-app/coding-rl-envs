package com.vertexgrid.shared.util;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Collection utility methods used across all VertexGrid microservices.
 *
 * Provides convenience methods for creating type-safe collections,
 * safe list operations, and map merging.
 */
public class CollectionUtils {

    private CollectionUtils() {
        // Utility class - prevent instantiation
    }

    
    // EnumSet uses a compact bit-vector representation that is orders of magnitude
    // faster than HashSet for enum types. HashSet boxes each enum value, computes
    // hash codes, and uses a backing HashMap with linked-list/tree buckets.
    // In VertexGrid this is called frequently to check ServiceStatus sets for
    // vehicle fleet health dashboards, causing unnecessary GC pressure.
    // Category: Memory/Data Structures
    // Fix: Use EnumSet.copyOf(values) instead of new HashSet<>(values).
    //      return values.isEmpty() ? EnumSet.noneOf(getEnumClass(values)) : EnumSet.copyOf(values);

    /**
     * Creates an optimized Set for enum values.
     *
     * @param values the enum values to include in the set
     * @return a Set containing the provided enum values
     */
    public static <E extends Enum<E>> Set<E> createEnumSet(Collection<E> values) {
        
        // HashSet has O(1) amortized but with high constant factor due to
        // boxing, hashing, and HashMap overhead. EnumSet uses bit vectors
        // for O(1) with tiny constant factor and zero boxing.
        return new HashSet<>(values);
        // Fix: return EnumSet.copyOf(values);
    }

    
    // Each += operation on a String creates a new String object and copies all
    // previous characters, resulting in O(n^2) time complexity and significant
    // garbage collection pressure. In VertexGrid this is used for building
    // CSV exports of vehicle telemetry data (thousands of rows).
    // Category: Memory/Data Structures
    // Fix: Use StringBuilder, or simply String.join(delimiter, strings).

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
            
            // For a list of 10,000 vehicle IDs, this creates ~10,000 intermediate
            // String objects totaling ~50 million characters copied.
            result += strings.get(i);
            if (i < strings.size() - 1) {
                result += delimiter;
            }
        }
        return result;
        // Fix: return String.join(delimiter, strings);
        //   or:
        //   StringBuilder sb = new StringBuilder();
        //   for (int i = 0; i < strings.size(); i++) {
        //       if (i > 0) sb.append(delimiter);
        //       sb.append(strings.get(i));
        //   }
        //   return sb.toString();
    }

    
    // String.CASE_INSENSITIVE_ORDER treats "abc" and "ABC" as equal (compareTo == 0),
    // but String.equals("abc", "ABC") returns false. Per the TreeMap contract,
    // "the ordering imposed by a comparator c on a set of elements S is said to be
    // consistent with equals if and only if c.compare(e1, e2)==0 has the same boolean
    // value as e1.equals(e2)." Violating this causes:
    //   - map.put("abc", v1); map.put("ABC", v2) overwrites v1 silently
    //   - map.containsKey("abc") returns true but the stored key shows "ABC"
    //   - Iteration may yield unexpected key capitalization
    // In VertexGrid, this affects HTTP header maps and configuration key lookups.
    // Category: Memory/Data Structures
    // Fix: Use a dedicated CaseInsensitiveKey wrapper that overrides equals/hashCode
    //      consistently, or use a HashMap with lowercased keys.

    
    /**
     * Creates a case-insensitive string-keyed TreeMap.
     *
     * @return a new TreeMap with case-insensitive key ordering
     */
    public static <V> TreeMap<String, V> createCaseInsensitiveMap() {
        
        // This causes "abc" and "ABC" to be treated as different keys
        return new TreeMap<>();
        // Fix: return new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
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
