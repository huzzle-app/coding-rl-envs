
// and accesses global state without synchronization.
// FIX: Use a sig_atomic_t flag in the handler, check it in the main loop

#include "config/config.h"
#include "server/server.h"
#include <spdlog/spdlog.h>
#include <csignal>
#include <iostream>

namespace {

cacheforge::Server* g_server = nullptr;


// Calling non-async-signal-safe functions from a signal handler is undefined behavior.
// It can cause deadlocks (if spdlog holds a mutex when the signal fires) or corruption.
// FIX: Set a volatile sig_atomic_t flag and check it in the main event loop:
//   volatile sig_atomic_t g_shutdown_requested = 0;
//   void signal_handler(int) { g_shutdown_requested = 1; }
void signal_handler(int signum) {
    spdlog::info("Received signal {}, shutting down...", signum);  // UB!
    if (g_server) {
        g_server->stop();
    }
}

}  // namespace

int main(int argc, char* argv[]) {
    try {
        // Uses global CONFIG_INSTANCE which has BUG L1 (static init fiasco)
        auto& config = cacheforge::get_config();

        spdlog::set_level(spdlog::level::from_str(config.log_level));
        spdlog::info("Starting CacheForge v1.0.0");

        cacheforge::Server server(config);
        g_server = &server;

        std::signal(SIGINT, signal_handler);
        std::signal(SIGTERM, signal_handler);

        server.start();

        spdlog::info("CacheForge listening on {}:{}", config.bind_address, config.port);

        // Wait for shutdown
        while (server.is_running()) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }

        g_server = nullptr;
        spdlog::info("CacheForge shutdown complete");
        return 0;

    } catch (const std::exception& e) {
        spdlog::error("Fatal error: {}", e.what());
        return 1;
    }
}
