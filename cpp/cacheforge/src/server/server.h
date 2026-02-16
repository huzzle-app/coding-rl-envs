#pragma once

#include <memory>
#include <vector>
#include <thread>
#include <atomic>
#include <functional>
#include <boost/asio.hpp>
#include "config/config.h"

namespace cacheforge {

class Connection;

class Server {
public:
    Server(const Config& config);
    ~Server();

    void start();
    void stop();
    bool is_running() const { return running_.load(); }

    size_t connection_count() const;
    void broadcast(const std::string& message);

    
    void accept_connection();

    
    volatile bool accepting_ = true;

private:
    Config config_;
    boost::asio::io_context io_context_;
    boost::asio::ip::tcp::acceptor acceptor_;
    std::vector<std::shared_ptr<Connection>> connections_;
    std::vector<std::thread> worker_threads_;
    std::atomic<bool> running_{false};

    void run_workers(int thread_count);
    void cleanup_connections();
};

}  // namespace cacheforge
