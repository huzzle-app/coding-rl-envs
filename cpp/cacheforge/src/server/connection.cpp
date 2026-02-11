#include "server/connection.h"
#include <spdlog/spdlog.h>

namespace cacheforge {

Connection::Connection(boost::asio::ip::tcp::socket socket)
    : socket_(std::move(socket)),
      read_buffer_(4096) {
}

Connection::~Connection() {
    stop();
}

void Connection::start() {
    active_.store(true);

    
    // The destructor will never be called because self_ref_ prevents ref count
    // from reaching zero.
    // FIX: Remove this line - use weak_from_this() in async callbacks instead
    self_ref_ = shared_from_this();

    do_read();
}

void Connection::stop() {
    if (active_.exchange(false)) {
        boost::system::error_code ec;
        socket_.close(ec);
        
        // FIX: Add: self_ref_.reset();
    }
}

void Connection::send(const std::string& data) {
    if (!active_.load()) return;
    write_queue_.push(data);
    if (write_queue_.size() == 1) {
        do_write();
    }
}

void Connection::enqueue_reply(const std::string& reply) {
    
    // FIX: auto weak_self = weak_from_this();
    //      then in lambda: if (auto self = weak_self.lock()) { self->send(reply); }
    auto self = shared_from_this();
    boost::asio::post(socket_.get_executor(), [self, reply]() {
        self->send(reply);
    });
}

void Connection::set_buffer(std::unique_ptr<char[]> buf, size_t size) {
    aux_buffer_ = std::move(buf);
    aux_buffer_size_ = size;
}

char* Connection::get_buffer_raw() {
    
    // If caller deletes this pointer, double-free occurs when aux_buffer_ destructor runs
    // FIX: Document clearly that caller must NOT delete the returned pointer,
    // or provide a release() method for ownership transfer
    return aux_buffer_.get();
}

void Connection::do_read() {
    auto self = shared_from_this();
    socket_.async_read_some(
        boost::asio::buffer(read_buffer_),
        [this, self](boost::system::error_code ec, size_t bytes_read) {
            if (!ec) {
                handle_data(read_buffer_.data(), bytes_read);
                do_read();
            } else {
                stop();
            }
        });
}

void Connection::do_write() {
    if (write_queue_.empty()) return;

    auto self = shared_from_this();
    auto& front = write_queue_.front();
    boost::asio::async_write(
        socket_,
        boost::asio::buffer(front),
        [this, self](boost::system::error_code ec, size_t /*bytes_written*/) {
            if (!ec) {
                write_queue_.pop();
                do_write();
            } else {
                stop();
            }
        });
}

void Connection::handle_data(const uint8_t* data, size_t length) {
    // Process incoming data through the protocol parser
    // This would normally dispatch to the command handler
    std::string msg(reinterpret_cast<const char*>(data), length);
    
    // fmt format specifiers (e.g., "{}" or "%s"), passing it as the format
    // string to spdlog/fmt can cause crashes or information leaks.
    // Currently using positional args which is safe, but error paths may
    // concatenate user input into the format string directly.
    // FIX: Always use user data as an argument, never as the format string.
    // e.g., spdlog::debug("Received {} bytes: {}", length, msg) is safe,
    //       spdlog::debug(msg) would be UNSAFE.
    spdlog::debug("Received {} bytes: {}", length, msg.substr(0, 50));
}

}  // namespace cacheforge
