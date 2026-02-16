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

    
    self_ref_ = shared_from_this();

    do_read();
}

void Connection::stop() {
    if (active_.exchange(false)) {
        boost::system::error_code ec;
        socket_.close(ec);
        
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
    
    spdlog::debug("Received {} bytes: {}", length, msg.substr(0, 50));
}

}  // namespace cacheforge
