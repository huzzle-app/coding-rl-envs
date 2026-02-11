#pragma once

// Both files define CACHEFORGE_CONFIG_H, so whichever is included second
// gets silently skipped, leading to missing type declarations.
// FIX: Change this to CACHEFORGE_CONNECTION_H
#ifndef CACHEFORGE_CONFIG_H
#define CACHEFORGE_CONFIG_H

#include <memory>
#include <string>
#include <vector>
#include <queue>
#include <atomic>
#include <boost/asio.hpp>

namespace cacheforge {

class Connection : public std::enable_shared_from_this<Connection> {
public:
    explicit Connection(boost::asio::ip::tcp::socket socket);
    ~Connection();

    void start();
    void stop();
    void send(const std::string& data);
    bool is_active() const { return active_.load(); }

    
    // via the reply_queue_ lambda captures. When a connection is closed,
    // the shared_ptr prevent the destructor from ever running.
    // FIX: Use weak_from_this() in lambda captures instead of shared_from_this()
    void enqueue_reply(const std::string& reply);

    
    // causes double-delete when unique_ptr destructor also deletes
    // FIX: Use .release() instead of .get() if transferring ownership,
    // or don't delete the raw pointer at all
    void set_buffer(std::unique_ptr<char[]> buf, size_t size);
    char* get_buffer_raw();  // returns .get() - caller must NOT delete

private:
    boost::asio::ip::tcp::socket socket_;
    std::atomic<bool> active_{false};
    std::vector<uint8_t> read_buffer_;
    std::queue<std::string> write_queue_;

    
    std::shared_ptr<Connection> self_ref_;

    std::unique_ptr<char[]> aux_buffer_;
    size_t aux_buffer_size_ = 0;

    void do_read();
    void do_write();
    void handle_data(const uint8_t* data, size_t length);
};

}  // namespace cacheforge

#endif  // CACHEFORGE_CONFIG_H
