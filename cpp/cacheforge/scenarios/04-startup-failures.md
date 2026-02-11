# Incident Report: Deployment Failures Across Environments

## Jira Ticket: CACHE-4721

**Priority**: Blocker
**Reporter**: DevOps Team
**Created**: 2024-01-21 09:45 UTC
**Status**: Open

---

## Summary

Multiple deployment attempts across different environments are failing with various cryptic errors. The same binary works on some machines but fails on others. Issues appear to be related to initialization order and configuration loading.

---

## Environment Details

| Environment | Status | Error Type |
|-------------|--------|------------|
| dev-local | Works | - |
| staging-01 | FAILED | Crash on startup |
| staging-02 | Works | - |
| prod-east-01 | FAILED | Crash on startup |
| prod-east-02 | FAILED | Crash on SIGTERM |
| prod-west-01 | Works | - |
| prod-west-02 | FAILED | Crash on startup |

---

## Error Reports

### Error Type 1: Crash on Startup (staging-01, prod-east-01, prod-west-02)

```
$ ./cacheforge-server
Segmentation fault (core dumped)

Core dump analysis:
#0  0x00007f8a2c001234 in std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::basic_string(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&) ()
#1  0x000055b8a3456789 in cacheforge::Server::Server(cacheforge::Config const&) () at server/server.cpp:9
#2  0x000055b8a3401234 in main () at main.cpp:38
```

Observation: The crash happens before any log output, during static initialization.

Additional gdb session:
```
(gdb) print CONFIG_INSTANCE
$1 = {bind_address = "", port = 0, log_level = "", max_connections = 0, ...}
(gdb) info variables CONFIG_INSTANCE
0x55b8a3800000  cacheforge::CONFIG_INSTANCE
(gdb) print &CONFIG_INSTANCE
$2 = (cacheforge::Config *) 0x55b8a3800000
```

The CONFIG_INSTANCE appears to be uninitialized (all zeros) even though it should have been constructed with default values.

### Error Type 2: Crash on SIGTERM (prod-east-02)

```
$ ./cacheforge-server &
[1] 12345
2024-01-21T10:00:00Z INFO  Starting CacheForge v1.0.0
2024-01-21T10:00:00Z INFO  CacheForge listening on 0.0.0.0:6379

$ kill 12345
<server hangs for 5 seconds then crashes>

Core dump:
#0  __lll_lock_wait () at ../sysdeps/unix/sysv/linux/x86_64/lowlevellock.S:152
#1  __GI___pthread_mutex_lock (mutex=0x7f8a2c002100) at pthread_mutex_lock.c:115
#2  spdlog::logger::log_(...) at spdlog/logger.h:89
#3  signal_handler(int) at main.cpp:22
#4  <signal handler called>
#5  __lll_lock_wait () at lowlevellock.S:152  <-- another thread already holding spdlog mutex
```

This is a classic "signal handler calling non-async-signal-safe function" issue. The signal interrupted spdlog while it held a mutex, and the handler tried to log, causing deadlock.

### Error Type 3: Environment Variable Parsing (intermittent)

```
$ CACHEFORGE_PORT=not_a_number ./cacheforge-server
terminate called after throwing an instance of 'std::invalid_argument'
  what():  stoi
Aborted (core dumped)

$ CACHEFORGE_PORT= ./cacheforge-server
terminate called after throwing an instance of 'std::invalid_argument'
  what():  stoi
Aborted (core dumped)
```

The server crashes when environment variables are set to invalid values instead of falling back to defaults.

### Error Type 4: Header Conflicts (compile-time)

During a clean rebuild on a new build machine:

```
$ cmake --build build
...
In file included from server/server.cpp:2:
server/connection.h:4:9: warning: 'CACHEFORGE_CONFIG_H' is defined as both a header guard in config.h and connection.h
 #define CACHEFORGE_CONFIG_H
         ^~~~~~~~~~~~~~~~~~~
server/server.cpp: In constructor 'cacheforge::Server::Server(const cacheforge::Config&)':
server/server.cpp:15:5: error: 'Config' was not declared in this scope
   15 |     Config c = config_;
      |     ^~~~~~

```

Investigation shows that `config.h` and `connection.h` use the same include guard macro `CACHEFORGE_CONFIG_H`, causing the second-included header to be skipped entirely.

---

## Reproduction Notes

**Startup crash reproduction**:
- Happens when linking order puts config.o before server.o
- Does NOT happen when config.o comes after
- Suggests static initialization order dependency

**Signal handler crash reproduction**:
```bash
# Start server
./cacheforge-server &

# Wait for it to be actively logging (processing requests)
sleep 1
cacheforge-cli SET foo bar &
cacheforge-cli GET foo &

# Kill while it's logging
kill $!
# High probability of deadlock/crash
```

**Environment variable crash reproduction**:
```bash
export CACHEFORGE_PORT=""
./cacheforge-server  # Crashes with std::invalid_argument
```

---

## Comparison: Working vs Failing

| Aspect | Working (dev-local) | Failing (staging-01) |
|--------|---------------------|----------------------|
| Compiler | GCC 11.2 | GCC 12.1 |
| Link order | server.o config.o | config.o server.o |
| Static init | Config first | Server first |

---

## Slack Discussion

**#platform-dev** - January 21, 2024

**@dev.alex** (10:15):
> Why does the same binary work on staging-02 but crash on staging-01? They're identical machines.

**@build.sam** (10:22):
> Actually, they're not. staging-01 was rebuilt last week with updated toolchain. The new GCC might be ordering object files differently.

**@dev.alex** (10:28):
> So it's a static initialization order fiasco? We're using globals before they're constructed?

**@build.sam** (10:35):
> Looks like it. CONFIG_INSTANCE is a file-scope static that's used by Server's constructor. If Server's translation unit is initialized first, CONFIG_INSTANCE is all zeros.

**@sre.kim** (10:40):
> What about the signal handler crash? That's a different issue right?

**@dev.alex** (10:45):
> Yeah, that's a separate problem. The signal handler calls spdlog::info() which is not async-signal-safe. If a signal arrives while another thread holds the spdlog mutex, we deadlock.

---

## Investigation Questions

1. Why does initialization order vary between machines?
2. How can we ensure Config is initialized before Server?
3. What functions are safe to call from signal handlers?
4. Why do two headers share the same include guard?
5. How should we handle invalid environment variable values?

---

## Files to Investigate

- `src/config/config.h` - Global config instance, include guard
- `src/config/config.cpp` - Static initialization
- `src/server/connection.h` - Include guard collision
- `src/server/server.cpp` - Uses CONFIG_INSTANCE at file scope
- `src/main.cpp` - Signal handler implementation

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Blocking**: Production deployment
