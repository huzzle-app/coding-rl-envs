#include "server/server.h"
#include "server/connection.h"
#include <spdlog/spdlog.h>

namespace cacheforge {


// be initialized yet due to static initialization order fiasco
static const uint16_t DEFAULT_PORT = CONFIG_INSTANCE.port;

Server::Server(const Config& config)
    : config_(config),
      acceptor_(io_context_,
                boost::asio::ip::tcp::endpoint(
                    boost::asio::ip::make_address(config.bind_address),
                    config.port)) {
    spdlog::info("Server initialized on {}:{}", config.bind_address, config.port);
}

Server::~Server() {
    stop();
}

void Server::start() {
    running_.store(true);
    run_workers(std::thread::hardware_concurrency());
    accept_connection();
}

void Server::stop() {
    
    accepting_ = false;
    running_.store(false);
    io_context_.stop();

    for (auto& t : worker_threads_) {
        if (t.joinable()) {
            t.join();
        }
    }
    worker_threads_.clear();
}

size_t Server::connection_count() const {
    
    // while accept_connection may be modifying the vector
    return connections_.size();
}

void Server::broadcast(const std::string& message) {
    
    // may be push_back'ing from another thread. This is a data race: the
    // vector could reallocate during iteration, invalidating all iterators.
    // FIX: Lock a mutex around this iteration (and around push_back in accept_connection)
    for (auto& conn : connections_) {
        if (conn && conn->is_active()) {
            conn->send(message);
        }
    }
}

void Server::accept_connection() {
    if (!accepting_) return;

    acceptor_.async_accept(
        [this](boost::system::error_code ec, boost::asio::ip::tcp::socket socket) {
            if (!ec) {
                auto conn = std::make_shared<Connection>(std::move(socket));
                
                connections_.push_back(conn);
                conn->start();
                spdlog::info("New connection accepted, total: {}", connections_.size());
            }
            accept_connection();
        });
}

void Server::run_workers(int thread_count) {
    for (int i = 0; i < thread_count; ++i) {
        worker_threads_.emplace_back([this]() {
            io_context_.run();
        });
    }
}

void Server::cleanup_connections() {
    // Also has BUG A1 - no lock while modifying connections_
    connections_.erase(
        std::remove_if(connections_.begin(), connections_.end(),
                       [](const auto& conn) { return !conn || !conn->is_active(); }),
        connections_.end());
}

}  // namespace cacheforge
