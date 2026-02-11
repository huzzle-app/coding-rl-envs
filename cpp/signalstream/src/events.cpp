#include "signalstream/core.hpp"
#include <algorithm>

namespace signalstream {

// ---------------------------------------------------------------------------
// Event publishing and consumption
// ---------------------------------------------------------------------------

static std::unordered_map<std::string, std::vector<DataPoint>> topic_events;
static std::mutex events_mutex;

void publish_event(const std::string& topic, const DataPoint& event) {
    std::lock_guard lock(events_mutex);
    topic_events[topic].push_back(event);
}

std::vector<DataPoint> consume_events(const std::string& topic, int max_count) {
    std::lock_guard lock(events_mutex);

    auto it = topic_events.find(topic);
    if (it == topic_events.end()) {
        return {};
    }

    auto& events = it->second;
    int count = std::min(max_count, static_cast<int>(events.size()));

    std::vector<DataPoint> result(events.begin(), events.begin() + count);
    events.erase(events.end() - count, events.end());

    return result;
}

}  // namespace signalstream
