package com.vertexgrid.shared;

import com.vertexgrid.shared.model.ServiceStatus;
import com.vertexgrid.shared.util.CollectionUtils;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class CollectionUtilsTest {

    
    @Test
    void test_enum_set_used() {
        Set<ServiceStatus> statuses = CollectionUtils.createEnumSet(
            List.of(ServiceStatus.RUNNING, ServiceStatus.DEGRADED));

        assertNotNull(statuses);
        assertEquals(2, statuses.size());
        assertTrue(statuses.contains(ServiceStatus.RUNNING));
        
        assertTrue(statuses instanceof EnumSet,
            "Should use EnumSet for enum values, not " + statuses.getClass().getSimpleName());
    }

    @Test
    void test_enum_collection_performance() {
        List<ServiceStatus> all = List.of(ServiceStatus.values());
        Set<ServiceStatus> set = CollectionUtils.createEnumSet(all);
        assertEquals(ServiceStatus.values().length, set.size());
    }

    @Test
    void test_enum_set_contains() {
        Set<ServiceStatus> set = CollectionUtils.createEnumSet(
            List.of(ServiceStatus.RUNNING));
        assertTrue(set.contains(ServiceStatus.RUNNING));
        assertFalse(set.contains(ServiceStatus.ERROR));
    }

    
    @Test
    void test_string_join_efficient() {
        List<String> strings = new ArrayList<>();
        for (int i = 0; i < 1000; i++) {
            strings.add("item" + i);
        }

        long start = System.nanoTime();
        String result = CollectionUtils.joinStrings(strings, ",");
        long elapsed = System.nanoTime() - start;

        assertNotNull(result);
        assertTrue(result.contains("item0"));
        assertTrue(result.contains("item999"));
        
        assertTrue(elapsed < 1_000_000_000L, // 1 second
            "Join should be efficient, took " + (elapsed / 1_000_000) + "ms");
    }

    @Test
    void test_no_string_concat_loop() {
        List<String> strings = List.of("a", "b", "c");
        String result = CollectionUtils.joinStrings(strings, "-");
        assertEquals("a-b-c", result);
    }

    @Test
    void test_join_empty_list() {
        String result = CollectionUtils.joinStrings(List.of(), ",");
        assertEquals("", result);
    }

    @Test
    void test_join_single_element() {
        String result = CollectionUtils.joinStrings(List.of("only"), ",");
        assertEquals("only", result);
    }

    
    @Test
    void test_treemap_consistency() {
        TreeMap<String, Integer> map = CollectionUtils.createCaseInsensitiveMap();
        map.put("abc", 1);
        map.put("ABC", 2);

        
        // The map should have only 1 entry, with value 2 (last put wins)
        assertEquals(1, map.size(), "Case-insensitive map should treat abc and ABC as same key");
        assertEquals(2, map.get("abc"));
    }

    @Test
    void test_case_insensitive_map() {
        TreeMap<String, String> map = CollectionUtils.createCaseInsensitiveMap();
        map.put("Key", "value1");

        assertTrue(map.containsKey("key"));
        assertTrue(map.containsKey("KEY"));
        assertTrue(map.containsKey("Key"));
    }

    @Test
    void test_safe_sublist() {
        List<Integer> list = List.of(1, 2, 3, 4, 5);
        List<Integer> sub = CollectionUtils.safeSubList(list, 1, 3);
        assertEquals(List.of(2, 3), sub);
    }

    @Test
    void test_safe_sublist_out_of_bounds() {
        List<Integer> list = List.of(1, 2, 3);
        List<Integer> sub = CollectionUtils.safeSubList(list, 0, 100);
        assertEquals(3, sub.size());
    }

    @Test
    void test_merge_maps() {
        Map<String, Integer> m1 = Map.of("a", 1, "b", 2);
        Map<String, Integer> m2 = Map.of("b", 3, "c", 4);
        Map<String, Integer> merged = CollectionUtils.mergeMaps(m1, m2);
        assertEquals(3, merged.size());
        assertEquals(3, merged.get("b")); // m2 overwrites m1
    }
}
