"""Webhooks service models."""


class WebhookSubscription:
    """Webhook subscription model."""

    def __init__(self, subscription_id, url, events, secret=None):
        self.subscription_id = subscription_id
        self.url = url
        self.events = events
        self.secret = secret
        self.is_active = True
