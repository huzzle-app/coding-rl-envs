# Incident Report: Random Crashes and Memory Corruption

## PagerDuty Alert Chain

**Initial Severity**: Medium (P3)
**Escalated To**: Critical (P1)
**Triggered**: 2024-01-20 08:15 UTC
**Team**: Cache Infrastructure

---

## Alert History (Last 72 Hours)

```
2024-01-18 03:42 UTC - cacheforge-prod-03 crashed (SIGSEGV)
2024-01-18 14:15 UTC - cacheforge-prod-01 crashed (SIGSEGV)
2024-01-19 09:23 UTC - cacheforge-prod-02 crashed (double free detected)
2024-01-19 22:47 UTC - cacheforge-prod-03 crashed (SIGSEGV)
2024-01-20 08:15 UTC - cacheforge-prod-01 crashed (heap corruption)
```

---

## Crash Analysis

### Crash Type 1: SIGSEGV in GET operations

```
Signal: SIGSEGV (Segmentation fault)
Address: 0x7f8a2c001000 (appears to be freed memory)
Backtrace:
#0  std::__cxx11::basic_string<char>::size() at /usr/include/c++/11/bits/basic_string.h:1034
#1  cacheforge::Value::get_string() at data/value.cpp:42
#2  cacheforge::HashTable::get(std::string const&) at storage/hashtable.cpp:41
#3  cacheforge::Server::handle_get() at server/server.cpp:89
```

Core dump analysis:
```
(gdb) print value.data_
$1 = {_M_p = 0x7f8a2c001000 <error: Cannot access memory at address 0x7f8a2c001000>}
(gdb) info symbol 0x7f8a2c001000
No symbol matches 0x7f8a2c001000 (address in freed memory region)
```

### Crash Type 2: Double Free

```
*** Error in `./cacheforge-server': double free or corruption (fasttop): 0x00007f8a2c045a80 ***

Backtrace:
#0  __GI_raise (sig=sig@entry=6) at ../sysdeps/unix/sysv/linux/raise.c:51
#1  __GI_abort () at abort.c:79
#2  __libc_message () at ../sysdeps/posix/libc_fatal.c:155
#3  malloc_printerr () at malloc.c:5457
#4  _int_free (av=<optimized out>, p=<optimized out>, have_lock=0) at malloc.c:4425
#5  cacheforge::MemoryPool::~MemoryPool() at utils/memory_pool.cpp:17
```

### Crash Type 3: Heap Corruption

```
*** glibc detected *** ./cacheforge-server: corrupted double-linked list: 0x00007f8a2c067b20 ***

Backtrace shows corruption detected during:
#5  cacheforge::Connection::~Connection() at server/connection.cpp:12
#6  std::__shared_ptr<cacheforge::Connection>::~__shared_ptr()
```

---

## AddressSanitizer Output

Compiled with `-fsanitize=address` and ran tests:

```
=================================================================
==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000050
READ of size 1024 at 0x602000000050 thread T3
    #0 memcpy <null>
    #1 cacheforge::Parser::parse_raw(unsigned char const*, unsigned long) parser.cpp:24
    #2 cacheforge::Connection::handle_data(unsigned char const*, unsigned long) connection.cpp:99

0x602000000050 is located 0 bytes to the right of 64-byte region [0x602000000010,0x602000000050)
allocated by thread T3 here:
    #0 malloc <null>
    #1 cacheforge::Connection::Connection() connection.cpp:8
=================================================================
```

And another:

```
=================================================================
==12346==ERROR: AddressSanitizer: heap-use-after-free on address 0x603000000040
READ of size 8 at 0x603000000040 thread T2
    #0 cacheforge::Value::get_string_view() data/value.cpp:38
    #1 cacheforge::HashTable::get() storage/hashtable.cpp:42

0x603000000040 is located 16 bytes inside of 48-byte region [0x603000000030,0x603000000060)
freed by thread T2 here:
    #0 operator delete(void*)
    #1 std::__cxx11::basic_string::~basic_string()
    #2 cacheforge::Value::Value(cacheforge::Value&&) data/value.cpp:18

previously allocated by thread T1 here:
    #0 operator new(unsigned long)
    #1 std::__cxx11::basic_string::basic_string(char const*)
    #2 cacheforge::HashTable::set() storage/hashtable.cpp:24
=================================================================
```

---

## Patterns Observed

1. **Crashes increase with load**: More frequent during peak hours (10AM-2PM, 4PM-7PM)

2. **Memory pool correlation**: Many crashes happen after the memory pool has been in use for >1 hour

3. **Connection lifecycle**: Some crashes correlate with high connection churn (many connects/disconnects)

4. **Large payload correlation**: More crashes when clients send large keys or values (>1KB)

5. **Pool growth timing**: Several crashes occurred ~5 minutes after heavy SET operations that would have triggered pool growth

---

## Memory Profile from Production

```
$ cacheforge-cli MEMORY STATS

peak.allocated: 4,234,567,890 bytes
total.allocated: 3,876,543,210 bytes
pool.allocated: 1,234,567,890 bytes
pool.free_blocks: 45,678
pool.total_blocks: 123,456
connections.active: 234
connections.total_created: 45,678,901
```

Observation: `connections.total_created` is very high compared to `connections.active`, suggesting connection churn.

---

## Valgrind Output (on test suite)

```
==54321== Invalid read of size 8
==54321==    at 0x4C32D1B: strlen (in /usr/lib/valgrind/vgpreload_memcheck-amd64-linux.so)
==54321==    by 0x10F234: cacheforge::Parser::extract_key(unsigned char const*, unsigned long) (parser.cpp:74)
==54321==  Address 0x5c23080 is 0 bytes after a block of size 16 alloc'd

==54321== Conditional jump or move depends on uninitialised value(s)
==54321==    at 0x10A456: cacheforge::Connection::get_buffer_raw() (connection.cpp:64)
```

---

## Customer Reports

> "We're seeing occasional corrupted data when reading keys back. The value returned doesn't match what we set. This happens maybe 1 in 10,000 reads." - Customer A

> "Our client library keeps getting disconnected with 'connection reset by peer'. The server seems to crash." - Customer B

> "Large file caching (we cache 5MB blobs) seems to trigger crashes more often than small values." - Customer C

---

## Investigation Questions

1. Why is the parser reading beyond the allocated buffer?
2. What is causing use-after-free in the Value class?
3. Why is the memory pool seeing double-frees?
4. Are connection objects being destroyed correctly?
5. Is there a dangling pointer issue with the custom memory pool?

---

## Files to Investigate

Based on stack traces and sanitizer output:
- `src/protocol/parser.cpp` - Buffer overflow in parse_raw()
- `src/data/value.cpp` - Use-after-free in string handling
- `src/utils/memory_pool.cpp` - Double-free and pool corruption
- `src/server/connection.cpp` - Connection lifecycle issues

---

**Status**: INVESTIGATING
**Assigned**: @memory-safety-team
**Priority**: P1 - Blocking production stability
