pub mod feed;
pub mod aggregator;

#[cfg(test)]
mod tests;

pub use feed::MarketFeed;
pub use aggregator::OHLCVAggregator;
