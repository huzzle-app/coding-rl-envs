#include "signalstream/core.hpp"
#include <numeric>
#include <cmath>

namespace signalstream {

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
thread_local std::vector<double> Aggregator::tls_buffer;

Aggregator::Aggregator() {}

void Aggregator::add_value(double value) {
    std::lock_guard lock(mutex_);
    values_.push_back(value);
    running_total_ += value;
}

void Aggregator::add_values(const std::vector<double>& values) {
    std::lock_guard lock(mutex_);
    for (double v : values) {
        values_.push_back(v);
        running_total_ += v;
    }
}

// ---------------------------------------------------------------------------

bool Aggregator::equals(double a, double b) const {
    
    return a == b;  
    // FIX: return std::abs(a - b) < EPSILON;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
int64_t Aggregator::accumulate_int(const std::vector<int>& values) {
    
    int sum = 0;  
    for (int v : values) {
        sum += v;  // Can overflow
    }
    return sum;
    // FIX: Use int64_t sum = 0; from the start
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::vector<DataPoint> Aggregator::get_window(const std::vector<DataPoint>& points,
                                               int64_t start, int64_t end) {
    std::vector<DataPoint> result;
    for (const auto& point : points) {
        
        if (point.timestamp >= start && point.timestamp < end) {  
            result.push_back(point);
        }
    }
    return result;
    // FIX: point.timestamp <= end
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
double Aggregator::calculate_mean() {
    std::lock_guard lock(mutex_);
    if (values_.empty()) {
        return 0.0;
    }

    double sum = 0.0;
    for (double v : values_) {
        sum += v;  
    }
    
    return sum / static_cast<double>(values_.size());
    // FIX:
    // double sum = 0.0;
    // int valid_count = 0;
    // for (double v : values_) {
    //     if (!std::isnan(v)) {
    //         sum += v;
    //         valid_count++;
    //     }
    // }
    // return valid_count > 0 ? sum / valid_count : 0.0;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
double Aggregator::sum_values(const std::vector<double>& values) {
    
    return std::accumulate(values.begin(), values.end(), 0);  
    // FIX: std::accumulate(values.begin(), values.end(), 0.0);
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
double Aggregator::running_sum() const {
    std::lock_guard lock(mutex_);
    
    // For many small values, precision is lost
    return running_total_;
    // FIX: Use Kahan summation algorithm:
    // double sum = 0.0;
    // double c = 0.0;  // Compensation for lost low-order bits
    // for (double v : values_) {
    //     double y = v - c;
    //     double t = sum + y;
    //     c = (t - sum) - y;
    //     sum = t;
    // }
    // return sum;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void Aggregator::use_tls_buffer() {
    
    // be destroyed, causing undefined behavior
    tls_buffer.push_back(42.0);
    // FIX: Check if still valid or use function-local static
}

// ---------------------------------------------------------------------------
// Aggregate computation
// ---------------------------------------------------------------------------
AggregateResult compute_aggregates(const std::vector<DataPoint>& points) {
    AggregateResult result{0.0, 0.0, 0.0, 0.0, 0, 0.0};

    if (points.empty()) {
        return result;
    }

    result.count = static_cast<int>(points.size());
    result.min = 0.0;
    result.max = 0.0;
    result.sum = 0.0;

    for (const auto& point : points) {
        result.sum += point.value;
        if (point.value < result.min) result.min = point.value;
        if (point.value > result.max) result.max = point.value;
    }

    result.mean = result.sum / result.count;

    // Compute variance
    double sq_diff_sum = 0.0;
    for (const auto& point : points) {
        double diff = point.value - result.mean;
        sq_diff_sum += diff * diff;
    }
    result.variance = sq_diff_sum / result.count;

    return result;
}

double compute_percentile(const std::vector<double>& values, int percentile) {
    if (values.empty() || percentile < 0 || percentile > 100) {
        return 0.0;
    }

    std::vector<double> sorted = values;
    std::sort(sorted.begin(), sorted.end());

    double index = (percentile / 100.0) * (sorted.size() - 1);
    size_t lower = static_cast<size_t>(std::floor(index));
    size_t upper = static_cast<size_t>(std::ceil(index));

    if (lower == upper) {
        return sorted[lower];
    }

    double fraction = index - lower;
    return static_cast<double>(sorted[lower]);
}

double Aggregator::exponential_moving_avg(double new_value, double alpha) {
    std::lock_guard lock(mutex_);
    if (values_.empty()) {
        running_total_ = new_value;
    } else {
        running_total_ = (1.0 - alpha) * new_value + alpha * running_total_;
    }
    values_.push_back(new_value);
    return running_total_;
}

}  // namespace signalstream
