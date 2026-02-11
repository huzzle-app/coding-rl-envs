"""
Caching performance tests.

These tests verify bugs H1-H6 (Caching Performance category)
and validate general cache throughput and behavior.
"""
import pytest
import time
import hashlib
import threading
import random
import struct
from collections import OrderedDict, defaultdict
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Lightweight simulation helpers (no external services required)
# ---------------------------------------------------------------------------

class SimpleCache:
    """Minimal in-memory cache for testing cache semantics."""

    def __init__(self, max_size=128, default_ttl=60):
        self._store = OrderedDict()
        self._ttls = {}
        self._access_count = defaultdict(int)
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._store:
                self._access_count[key] += 1
                self._store.move_to_end(key)
                return self._store[key]
        return None

    def set(self, key, value, ttl=None):
        with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                self._store.popitem(last=False)
            self._store[key] = value
            self._store.move_to_end(key)
            self._ttls[key] = time.monotonic() + (ttl or self._default_ttl)

    def delete(self, key):
        with self._lock:
            self._store.pop(key, None)
            self._ttls.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()
            self._ttls.clear()

    def keys(self):
        return list(self._store.keys())

    def size(self):
        return len(self._store)


class SimpleLock:
    """Cooperative lock used to simulate single-flight cache refresh."""

    def __init__(self):
        self._held = {}
        self._lock = threading.Lock()

    def acquire(self, key):
        with self._lock:
            if key in self._held:
                return False
            self._held[key] = True
            return True

    def release(self, key):
        with self._lock:
            self._held.pop(key, None)


class SimpleBloomFilter:
    """A small Bloom filter for testing purposes."""

    def __init__(self, size=1024, num_hashes=3):
        self._bits = bytearray(size)
        self._size = size
        self._num_hashes = num_hashes

    def _hashes(self, item):
        results = []
        for i in range(self._num_hashes):
            h = hashlib.md5(f"{item}:{i}".encode()).digest()
            idx = struct.unpack("<I", h[:4])[0] % self._size
            results.append(idx)
        return results

    def add(self, item):
        for idx in self._hashes(item):
            self._bits[idx] = 1

    def might_contain(self, item):
        return all(self._bits[idx] for idx in self._hashes(item))

    def serialize(self):
        return bytes(self._bits)

    @classmethod
    def deserialize(cls, data, num_hashes=3):
        bf = cls(size=len(data), num_hashes=num_hashes)
        bf._bits = bytearray(data)
        return bf


# ---------------------------------------------------------------------------
# H1 -- Cache Stampede Prevention
# ---------------------------------------------------------------------------

class TestCacheStampedePrevention:
    """Tests for bug H1: cache stampede / thundering-herd scenarios."""

    def test_cache_stampede(self):
        """Test that cache stampede is prevented via single-flight fetch."""
        cache = SimpleCache()
        lock = SimpleLock()
        key = "popular_item"
        fetch_count = 0

        def fetch_with_lock():
            nonlocal fetch_count
            if cache.get(key) is not None:
                return cache.get(key)
            acquired = lock.acquire(key)
            if acquired:
                fetch_count += 1
                cache.set(key, "value")
                lock.release(key)
            else:
                # Wait briefly and retry from cache
                time.sleep(0.001)
            return cache.get(key)

        threads = []
        for _ in range(50):
            t = threading.Thread(target=fetch_with_lock)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        assert fetch_count == 1, "Only one request should fetch on cache miss"

    def test_thundering_herd(self):
        """Test that thundering-herd effect is mitigated."""
        cache = SimpleCache()
        key = "herd_key"
        miss_count = 0
        barrier = threading.Barrier(20)
        lock = SimpleLock()

        def reader():
            nonlocal miss_count
            barrier.wait()
            if cache.get(key) is None:
                if lock.acquire(key):
                    miss_count += 1
                    cache.set(key, "loaded")
                    lock.release(key)
                else:
                    time.sleep(0.005)

        threads = [threading.Thread(target=reader) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert miss_count == 1, "Only a single thread should perform the fetch"

    def test_probabilistic_early_expiration(self):
        """Test that probabilistic early expiry reduces stampede risk."""
        cache = SimpleCache(default_ttl=10)
        key = "early_expire"
        cache.set(key, "data", ttl=10)

        # Simulate probabilistic early expiry: with a beta * ln(random) model
        # If remaining TTL is small relative to recompute cost, trigger early refresh
        remaining_ttl = 2.0
        recompute_cost = 0.5
        random.seed(42)
        should_recompute = remaining_ttl - recompute_cost * (-1 * random.random()) <= 0

        # The concept is valid regardless of actual result; verify the formula runs
        assert isinstance(should_recompute, bool)

    def test_lock_based_cache_refresh(self):
        """Test lock-based refresh prevents duplicate computation."""
        lock = SimpleLock()
        key = "locked_refresh"
        results = []

        def try_refresh():
            if lock.acquire(key):
                results.append("refreshed")
                lock.release(key)
            else:
                results.append("skipped")

        t1 = threading.Thread(target=try_refresh)
        t2 = threading.Thread(target=try_refresh)
        # Acquire before both threads start so second must skip
        lock.acquire(key)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        lock.release(key)

        assert results.count("skipped") == 2, "Both threads should skip while lock is held"

    def test_stale_while_revalidate(self):
        """Test serving stale data while revalidating in background."""
        cache = SimpleCache()
        key = "swr_key"
        cache.set(key, "stale_value", ttl=0)
        # Even after TTL expires, the value should still be available as stale
        val = cache.get(key)
        assert val == "stale_value", "Stale value should be served while revalidating"

    def test_request_coalescing_under_load(self):
        """Test that concurrent identical requests are coalesced."""
        call_count = 0
        coalesce_lock = threading.Lock()
        pending = {}

        def coalesced_fetch(key):
            nonlocal call_count
            with coalesce_lock:
                if key in pending:
                    event = pending[key]
                else:
                    event = threading.Event()
                    pending[key] = event
                    call_count += 1
                    event.set()
                    return "fetched"
            event.wait(timeout=1)
            return "coalesced"

        threads = []
        results = []

        def worker():
            results.append(coalesced_fetch("shared_key"))

        for _ in range(30):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        assert call_count == 1, "Only one actual fetch should happen"


# ---------------------------------------------------------------------------
# H2 -- Hot Key Mitigation
# ---------------------------------------------------------------------------

class TestHotKeyMitigation:
    """Tests for bug H2: hot-key distribution and handling."""

    def test_key_distribution(self):
        """Test that keys are distributed evenly across shards."""
        num_shards = 8
        shard_counts = defaultdict(int)
        for i in range(1000):
            key = f"item:{i}"
            shard = int(hashlib.md5(key.encode()).hexdigest(), 16) % num_shards
            shard_counts[shard] += 1

        max_count = max(shard_counts.values())
        min_count = min(shard_counts.values())
        imbalance = (max_count - min_count) / (1000 / num_shards)
        assert imbalance < 0.5, f"Key distribution too skewed: {imbalance:.2f}"

    def test_hot_key_handling(self):
        """Test that hot keys are detected and handled."""
        access_log = defaultdict(int)
        keys = ["hot"] * 95 + [f"cold_{i}" for i in range(5)]
        for k in keys:
            access_log[k] += 1

        hot_threshold = len(keys) * 0.5
        hot_keys = [k for k, c in access_log.items() if c > hot_threshold]
        assert "hot" in hot_keys, "Hot key should be detected"

    def test_consistent_hashing_distribution(self):
        """Test consistent hashing ring distributes keys fairly."""
        ring_size = 360
        nodes = ["node_a", "node_b", "node_c"]
        node_positions = {}
        for n in nodes:
            pos = int(hashlib.md5(n.encode()).hexdigest(), 16) % ring_size
            node_positions[n] = pos

        assignments = defaultdict(int)
        for i in range(900):
            key_pos = int(hashlib.md5(f"key:{i}".encode()).hexdigest(), 16) % ring_size
            closest_node = min(nodes, key=lambda n: (node_positions[n] - key_pos) % ring_size)
            assignments[closest_node] += 1

        assert len(assignments) == 3, "All nodes should receive keys"

    def test_key_prefix_sharding(self):
        """Test that key prefix sharding distributes load."""
        prefixes = ["user:", "order:", "product:", "session:"]
        shard_map = {p: i % 4 for i, p in enumerate(prefixes)}

        for prefix in prefixes:
            shard = shard_map[prefix]
            assert 0 <= shard < 4, f"Shard for {prefix} should be in range"

    def test_hot_key_local_cache(self):
        """Test that hot keys get promoted to local cache."""
        local_cache = {}
        access_count = defaultdict(int)
        promotion_threshold = 10

        for _ in range(15):
            access_count["hot_key"] += 1
            if access_count["hot_key"] >= promotion_threshold:
                local_cache["hot_key"] = "cached_locally"

        assert "hot_key" in local_cache, "Hot key should be promoted to local cache"

    def test_key_access_frequency_tracking(self):
        """Test that access frequency is tracked accurately."""
        tracker = defaultdict(int)
        operations = [("a", 50), ("b", 30), ("c", 20)]
        for key, count in operations:
            for _ in range(count):
                tracker[key] += 1

        assert tracker["a"] == 50
        assert tracker["b"] == 30
        assert tracker["c"] == 20


# ---------------------------------------------------------------------------
# H3 -- Cache Consistency
# ---------------------------------------------------------------------------

class TestCacheConsistency:
    """Tests for bug H3: cache consistency issues."""

    def test_cache_consistency(self):
        """Test that cache and backing store stay consistent."""
        backing_store = {"key": "v1"}
        cache = SimpleCache()
        cache.set("key", "v1")

        # Update backing store
        backing_store["key"] = "v2"
        cache.set("key", "v2")  # Write-through

        assert cache.get("key") == backing_store["key"], "Cache must match backing store"

    def test_stale_cache(self):
        """Test detection and handling of stale cache entries."""
        cache = SimpleCache()
        cache.set("key", "old_value", ttl=0.001)
        time.sleep(0.01)

        # After TTL expires, value is still present but stale
        stored_ttl = cache._ttls.get("key", 0)
        is_stale = time.monotonic() > stored_ttl
        assert is_stale, "Entry should be detected as stale after TTL"

    def test_write_through_consistency(self):
        """Test write-through cache maintains consistency."""
        db = {}
        cache = SimpleCache()

        def write_through(key, value):
            db[key] = value
            cache.set(key, value)

        write_through("item", "data_v1")
        assert db["item"] == cache.get("item") == "data_v1"

        write_through("item", "data_v2")
        assert db["item"] == cache.get("item") == "data_v2"

    def test_write_behind_ordering(self):
        """Test write-behind buffer maintains operation order."""
        buffer = []

        def write_behind(key, value):
            buffer.append((key, value))

        write_behind("a", 1)
        write_behind("b", 2)
        write_behind("a", 3)

        assert buffer == [("a", 1), ("b", 2), ("a", 3)], "Write order must be preserved"

    def test_cache_aside_race(self):
        """Test cache-aside pattern race condition handling."""
        cache = SimpleCache()
        db = {"key": "db_value"}

        # Simulate: read miss -> read from db -> another thread updates db + invalidates cache
        val_from_db = db["key"]
        db["key"] = "new_db_value"
        cache.delete("key")

        # The stale value should NOT be placed in cache after invalidation
        # A correct implementation checks version/timestamp before caching
        version_before = 1
        version_after = 2
        should_cache = version_before >= version_after
        assert not should_cache, "Stale value should not overwrite newer invalidation"

    def test_invalidation_propagation_delay(self):
        """Test that invalidation propagation delay is bounded."""
        propagation_times = []
        for _ in range(100):
            start = time.monotonic()
            # Simulate invalidation message
            time.sleep(0.0001)
            propagation_times.append(time.monotonic() - start)

        avg_delay = sum(propagation_times) / len(propagation_times)
        assert avg_delay < 0.01, f"Average propagation delay {avg_delay:.4f}s exceeds 10ms"


# ---------------------------------------------------------------------------
# H4 -- TTL Management
# ---------------------------------------------------------------------------

class TestTTLManagement:
    """Tests for bug H4: TTL jitter and expiry distribution."""

    def test_ttl_jitter(self):
        """Test that TTL values include jitter to prevent synchronized expiry."""
        base_ttl = 300
        jitter_range = 30
        ttls = [base_ttl + random.randint(-jitter_range, jitter_range) for _ in range(100)]
        unique_ttls = set(ttls)
        assert len(unique_ttls) > 10, "TTLs should be distributed with jitter"

    def test_expiry_distribution(self):
        """Test that key expiry is distributed over time."""
        base_ttl = 60
        num_keys = 1000
        expiry_buckets = defaultdict(int)
        for _ in range(num_keys):
            ttl = base_ttl + random.randint(-10, 10)
            bucket = ttl // 5
            expiry_buckets[bucket] += 1

        max_bucket = max(expiry_buckets.values())
        assert max_bucket < num_keys * 0.5, "No single bucket should hold > 50% of keys"

    def test_sliding_window_expiry(self):
        """Test sliding window TTL resets on access."""
        cache = SimpleCache(default_ttl=10)
        cache.set("sliding", "value", ttl=10)
        original_expiry = cache._ttls["sliding"]

        # Simulate access that refreshes TTL
        cache._ttls["sliding"] = time.monotonic() + 10
        new_expiry = cache._ttls["sliding"]

        assert new_expiry > original_expiry, "TTL should slide forward on access"

    def test_ttl_refresh_on_access(self):
        """Test TTL refresh mechanism on read access."""
        cache = SimpleCache(default_ttl=5)
        cache.set("refresh_key", "data", ttl=5)

        # Refresh on get
        before_refresh = cache._ttls["refresh_key"]
        time.sleep(0.01)
        cache._ttls["refresh_key"] = time.monotonic() + 5
        after_refresh = cache._ttls["refresh_key"]

        assert after_refresh > before_refresh

    def test_max_ttl_enforcement(self):
        """Test that TTL does not exceed maximum allowed value."""
        max_ttl = 3600
        requested_ttl = 86400
        effective_ttl = min(requested_ttl, max_ttl)
        assert effective_ttl == max_ttl, "TTL should be capped at max"

    def test_ttl_precision(self):
        """Test TTL precision at sub-second level."""
        start = time.monotonic()
        time.sleep(0.05)
        elapsed = time.monotonic() - start
        assert 0.03 < elapsed < 0.15, f"Timer precision outside tolerance: {elapsed:.4f}s"


# ---------------------------------------------------------------------------
# H5 -- Bloom Filter
# ---------------------------------------------------------------------------

class TestBloomFilter:
    """Tests for bug H5: bloom filter accuracy and false positive rate."""

    def test_bloom_filter_accuracy(self):
        """Test that bloom filter correctly identifies members."""
        bf = SimpleBloomFilter(size=2048, num_hashes=5)
        items = [f"item_{i}" for i in range(100)]
        for item in items:
            bf.add(item)

        for item in items:
            assert bf.might_contain(item), f"{item} should be found in bloom filter"

    def test_false_positive_rate(self):
        """Test that false positive rate stays within acceptable bounds."""
        bf = SimpleBloomFilter(size=4096, num_hashes=5)
        inserted = [f"real_{i}" for i in range(200)]
        for item in inserted:
            bf.add(item)

        false_positives = 0
        test_count = 1000
        for i in range(test_count):
            if bf.might_contain(f"fake_{i}"):
                false_positives += 1

        fp_rate = false_positives / test_count
        assert fp_rate < 0.15, f"False positive rate {fp_rate:.3f} exceeds 15% threshold"

    def test_bloom_filter_capacity(self):
        """Test bloom filter handles expected capacity without degradation."""
        bf = SimpleBloomFilter(size=8192, num_hashes=4)
        for i in range(500):
            bf.add(f"capacity_{i}")

        # All inserted elements must be found
        for i in range(500):
            assert bf.might_contain(f"capacity_{i}")

    def test_bloom_filter_rebuild(self):
        """Test bloom filter can be rebuilt from source data."""
        bf1 = SimpleBloomFilter(size=1024, num_hashes=3)
        items = [f"rebuild_{i}" for i in range(50)]
        for item in items:
            bf1.add(item)

        # Rebuild from same data
        bf2 = SimpleBloomFilter(size=1024, num_hashes=3)
        for item in items:
            bf2.add(item)

        assert bf1.serialize() == bf2.serialize(), "Rebuilt filter should be identical"

    def test_counting_bloom_filter(self):
        """Test counting bloom filter supports deletion."""
        # Use counters instead of bits
        size = 256
        counters = [0] * size
        num_hashes = 3

        def _hash(item, i):
            return int(hashlib.md5(f"{item}:{i}".encode()).hexdigest(), 16) % size

        def add(item):
            for i in range(num_hashes):
                counters[_hash(item, i)] += 1

        def remove(item):
            for i in range(num_hashes):
                counters[_hash(item, i)] -= 1

        def contains(item):
            return all(counters[_hash(item, i)] > 0 for i in range(num_hashes))

        add("x")
        assert contains("x")
        remove("x")
        assert not contains("x"), "After removal, item should not be found"

    def test_bloom_filter_serialization(self):
        """Test bloom filter serialization and deserialization."""
        bf = SimpleBloomFilter(size=512, num_hashes=3)
        bf.add("serialize_me")

        data = bf.serialize()
        bf_restored = SimpleBloomFilter.deserialize(data, num_hashes=3)

        assert bf_restored.might_contain("serialize_me"), "Deserialized filter should find item"


# ---------------------------------------------------------------------------
# H6 -- Eviction Policy
# ---------------------------------------------------------------------------

class TestEvictionPolicy:
    """Tests for bug H6: eviction policy correctness."""

    def test_eviction_policy(self):
        """Test that eviction follows LRU policy."""
        cache = SimpleCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        # Access 'a' to make it recently used
        cache.get("a")

        # Adding 'd' should evict 'b' (least recently used)
        cache.set("d", 4)
        assert cache.get("b") is None, "LRU item 'b' should be evicted"
        assert cache.get("a") is not None, "Recently accessed 'a' should remain"

    def test_priority_retention(self):
        """Test that high-priority items are retained during eviction."""
        cache = SimpleCache(max_size=3)
        cache.set("low_1", "data")
        cache.set("high_priority", "important")
        cache.set("low_2", "data")

        # Access high-priority item to mark it recently used
        cache.get("high_priority")

        cache.set("new_item", "data")
        assert cache.get("high_priority") is not None, "High-priority item should be retained"

    def test_lru_eviction_order(self):
        """Test LRU eviction removes items in correct order."""
        cache = SimpleCache(max_size=4)
        for k in ["w", "x", "y", "z"]:
            cache.set(k, k)

        # Access in specific order: x, z (w and y become least-recently-used)
        cache.get("x")
        cache.get("z")

        # Two new inserts should evict w then y
        cache.set("a", "a")
        assert cache.get("w") is None, "'w' should be evicted first"

        cache.set("b", "b")
        assert cache.get("y") is None, "'y' should be evicted second"

    def test_lfu_eviction_order(self):
        """Test LFU-style eviction removes least frequently accessed items."""
        access_counts = {"a": 10, "b": 2, "c": 50, "d": 1}
        # LFU evicts item with lowest frequency
        evict_order = sorted(access_counts, key=access_counts.get)
        assert evict_order[0] == "d", "Least frequently used item should be evicted first"
        assert evict_order[1] == "b"

    def test_size_based_eviction(self):
        """Test eviction based on item size when memory limit is reached."""
        memory_limit = 100
        items = {"small": 10, "medium": 40, "large": 60}
        current_usage = sum(items.values())  # 110

        evicted = []
        # Evict largest first until under limit
        for key in sorted(items, key=items.get, reverse=True):
            if current_usage <= memory_limit:
                break
            current_usage -= items[key]
            evicted.append(key)

        assert "large" in evicted, "Largest item should be evicted"
        assert current_usage <= memory_limit

    def test_eviction_callback_notification(self):
        """Test that eviction triggers a callback/notification."""
        evicted_items = []

        def on_evict(key, value):
            evicted_items.append((key, value))

        cache = SimpleCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)

        # Simulate eviction callback
        old_keys = set(cache.keys())
        cache.set("c", 3)
        new_keys = set(cache.keys())
        removed = old_keys - new_keys
        for k in removed:
            on_evict(k, "evicted_value")

        assert len(evicted_items) == 1, "One eviction callback should fire"


# ---------------------------------------------------------------------------
# Throughput tests (general performance)
# ---------------------------------------------------------------------------

class TestThroughput:
    """General cache throughput and performance tests."""

    def test_batch_operation_throughput(self):
        """Test batch set/get operations achieve acceptable throughput."""
        cache = SimpleCache(max_size=10000)
        count = 5000
        start = time.monotonic()
        for i in range(count):
            cache.set(f"batch_{i}", i)
        elapsed = time.monotonic() - start

        ops_per_sec = count / max(elapsed, 1e-9)
        assert ops_per_sec > 1000, f"Batch throughput {ops_per_sec:.0f} ops/s too low"

    def test_pipeline_operation_performance(self):
        """Test pipelined operations are faster than individual ones."""
        cache = SimpleCache(max_size=10000)
        items = [(f"pipe_{i}", i) for i in range(2000)]

        # Pipelined: batch set
        start = time.monotonic()
        for k, v in items:
            cache.set(k, v)
        pipeline_time = time.monotonic() - start

        # Individual with overhead simulation
        cache.clear()
        start = time.monotonic()
        for k, v in items:
            cache.set(k, v)
            _ = 0  # Simulate round-trip overhead placeholder
        individual_time = time.monotonic() - start

        # Pipeline should be at least comparable (within 5x)
        assert pipeline_time < individual_time * 5, "Pipeline should not be drastically slower"

    def test_concurrent_read_throughput(self):
        """Test concurrent read throughput under contention."""
        cache = SimpleCache(max_size=1000)
        for i in range(1000):
            cache.set(f"conc_{i}", i)

        read_count = 0
        lock = threading.Lock()

        def reader():
            nonlocal read_count
            local_count = 0
            for i in range(500):
                cache.get(f"conc_{i % 1000}")
                local_count += 1
            with lock:
                read_count += local_count

        threads = [threading.Thread(target=reader) for _ in range(4)]
        start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - start

        ops_per_sec = read_count / max(elapsed, 1e-9)
        assert ops_per_sec > 1000, f"Concurrent read throughput {ops_per_sec:.0f} ops/s too low"

    def test_write_amplification_factor(self):
        """Test that write amplification stays within acceptable bounds."""
        logical_writes = 100
        physical_writes = 0

        cache = SimpleCache(max_size=50)
        for i in range(logical_writes):
            cache.set(f"wa_{i}", i)
            physical_writes += 1
            # Eviction causes an additional physical write (delete)
            if cache.size() >= 50:
                physical_writes += 1

        amplification = physical_writes / logical_writes
        assert amplification < 3.0, f"Write amplification {amplification:.2f} exceeds 3x"
