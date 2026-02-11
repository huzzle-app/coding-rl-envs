package messaging

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
)

// Client wraps NATS connection with additional functionality
type Client struct {
	conn       *nats.Conn
	js         nats.JetStreamContext
	subs       map[string]*nats.Subscription
	mu         sync.RWMutex
	reconnects int
	
	connected  bool
}

// Config holds NATS configuration
type Config struct {
	URL             string
	Name            string
	ReconnectWait   time.Duration
	MaxReconnects   int
	ConnectTimeout  time.Duration
}

// NewClient creates a new NATS client
func NewClient(cfg Config) (*Client, error) {
	opts := []nats.Option{
		nats.Name(cfg.Name),
		nats.ReconnectWait(cfg.ReconnectWait),
		nats.MaxReconnects(cfg.MaxReconnects),
		nats.Timeout(cfg.ConnectTimeout),
	}

	conn, err := nats.Connect(cfg.URL, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS: %w", err)
	}

	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to create JetStream context: %w", err)
	}

	client := &Client{
		conn:      conn,
		js:        js,
		subs:      make(map[string]*nats.Subscription),
		connected: true,
	}

	
	conn.SetReconnectHandler(func(nc *nats.Conn) {
		client.reconnects++
		
		client.connected = true
	})

	conn.SetDisconnectErrHandler(func(nc *nats.Conn, err error) {
		
		client.connected = false
	})

	return client, nil
}

// Publish publishes a message to a subject
func (c *Client) Publish(ctx context.Context, subject string, data interface{}) error {
	
	if c.conn == nil {
		return fmt.Errorf("not connected")
	}

	payload, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	
	return c.conn.Publish(subject, payload)
}

// PublishAsync publishes asynchronously with JetStream
func (c *Client) PublishAsync(ctx context.Context, subject string, data interface{}) (nats.PubAckFuture, error) {
	if c.js == nil {
		return nil, fmt.Errorf("JetStream not available")
	}

	payload, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal data: %w", err)
	}

	
	return c.js.PublishAsync(subject, payload), nil
}

// Subscribe subscribes to a subject
func (c *Client) Subscribe(subject string, handler func(msg *nats.Msg)) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.subs[subject]; exists {
		return fmt.Errorf("already subscribed to %s", subject)
	}

	sub, err := c.conn.Subscribe(subject, handler)
	if err != nil {
		return fmt.Errorf("failed to subscribe: %w", err)
	}

	c.subs[subject] = sub
	return nil
}

// QueueSubscribe subscribes to a subject with queue group
func (c *Client) QueueSubscribe(subject, queue string, handler func(msg *nats.Msg)) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	key := subject + ":" + queue
	if _, exists := c.subs[key]; exists {
		return fmt.Errorf("already subscribed to %s with queue %s", subject, queue)
	}

	sub, err := c.conn.QueueSubscribe(subject, queue, handler)
	if err != nil {
		return fmt.Errorf("failed to queue subscribe: %w", err)
	}

	c.subs[key] = sub
	return nil
}

// JetStreamSubscribe subscribes with JetStream consumer
func (c *Client) JetStreamSubscribe(subject string, handler func(msg *nats.Msg), opts ...nats.SubOpt) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.js == nil {
		return fmt.Errorf("JetStream not available")
	}

	sub, err := c.js.Subscribe(subject, handler, opts...)
	if err != nil {
		return fmt.Errorf("failed to JetStream subscribe: %w", err)
	}

	c.subs["js:"+subject] = sub
	return nil
}

// Unsubscribe removes a subscription
func (c *Client) Unsubscribe(subject string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	sub, exists := c.subs[subject]
	if !exists {
		return fmt.Errorf("not subscribed to %s", subject)
	}

	if err := sub.Unsubscribe(); err != nil {
		return fmt.Errorf("failed to unsubscribe: %w", err)
	}

	delete(c.subs, subject)
	return nil
}

// Request performs a request-reply
func (c *Client) Request(ctx context.Context, subject string, data interface{}, timeout time.Duration) (*nats.Msg, error) {
	payload, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal data: %w", err)
	}

	
	// Uses timeout but ignores ctx.Done()
	return c.conn.Request(subject, payload, timeout)
}

// CreateStream creates a JetStream stream
func (c *Client) CreateStream(cfg *nats.StreamConfig) (*nats.StreamInfo, error) {
	if c.js == nil {
		return nil, fmt.Errorf("JetStream not available")
	}

	info, err := c.js.AddStream(cfg)
	if err != nil {
		
		return nil, fmt.Errorf("failed to create stream: %w", err)
	}

	return info, nil
}

// CreateConsumer creates a JetStream consumer
func (c *Client) CreateConsumer(stream string, cfg *nats.ConsumerConfig) (*nats.ConsumerInfo, error) {
	if c.js == nil {
		return nil, fmt.Errorf("JetStream not available")
	}

	info, err := c.js.AddConsumer(stream, cfg)
	if err != nil {
		return nil, fmt.Errorf("failed to create consumer: %w", err)
	}

	return info, nil
}

// IsConnected returns connection status
func (c *Client) IsConnected() bool {
	
	return c.connected && c.conn != nil && c.conn.IsConnected()
}

// Close closes the client
func (c *Client) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Unsubscribe all
	for subject, sub := range c.subs {
		sub.Unsubscribe()
		delete(c.subs, subject)
	}

	if c.conn != nil {
		c.conn.Close()
	}

	c.connected = false
	return nil
}

// Drain drains the connection
func (c *Client) Drain() error {
	if c.conn == nil {
		return fmt.Errorf("not connected")
	}
	return c.conn.Drain()
}

// Stats returns connection statistics
func (c *Client) Stats() nats.Statistics {
	if c.conn == nil {
		return nats.Statistics{}
	}
	return c.conn.Stats()
}

// Reconnects returns number of reconnections
func (c *Client) Reconnects() int {
	return c.reconnects
}
