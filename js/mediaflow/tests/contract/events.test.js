/**
 * Event Contract Tests
 */

describe('Video Event Contracts', () => {
  describe('video.created', () => {
    it('should have required fields', () => {
      const event = {
        id: 'evt-123',
        type: 'video.created',
        timestamp: '2024-01-01T00:00:00Z',
        data: {
          videoId: 'video-123',
          userId: 'user-123',
          title: 'Test Video',
        },
      };

      expect(event).toHaveProperty('id');
      expect(event).toHaveProperty('type');
      expect(event).toHaveProperty('timestamp');
      expect(event.data).toHaveProperty('videoId');
      expect(event.data).toHaveProperty('userId');
    });

    it('should have valid event type', () => {
      const event = { type: 'video.created' };
      expect(event.type).toMatch(/^video\./);
    });
  });

  describe('video.updated', () => {
    it('should include changed fields', () => {
      const event = {
        type: 'video.updated',
        data: {
          videoId: 'video-123',
          changes: {
            title: { old: 'Old Title', new: 'New Title' },
          },
        },
      };

      expect(event.data).toHaveProperty('videoId');
      expect(event.data).toHaveProperty('changes');
    });
  });

  describe('video.deleted', () => {
    it('should include video ID', () => {
      const event = {
        type: 'video.deleted',
        data: {
          videoId: 'video-123',
          deletedAt: '2024-01-01T00:00:00Z',
        },
      };

      expect(event.data).toHaveProperty('videoId');
      expect(event.data).toHaveProperty('deletedAt');
    });
  });

  describe('video.published', () => {
    it('should include publish info', () => {
      const event = {
        type: 'video.published',
        data: {
          videoId: 'video-123',
          publishedAt: '2024-01-01T00:00:00Z',
          visibility: 'public',
        },
      };

      expect(event.data).toHaveProperty('publishedAt');
      expect(event.data).toHaveProperty('visibility');
    });
  });
});

describe('Transcode Event Contracts', () => {
  describe('transcode.started', () => {
    it('should have job info', () => {
      const event = {
        type: 'transcode.started',
        data: {
          jobId: 'job-123',
          videoId: 'video-123',
          profiles: ['1080p', '720p'],
          startedAt: '2024-01-01T00:00:00Z',
        },
      };

      expect(event.data).toHaveProperty('jobId');
      expect(event.data).toHaveProperty('profiles');
    });
  });

  describe('transcode.progress', () => {
    it('should have progress info', () => {
      const event = {
        type: 'transcode.progress',
        data: {
          jobId: 'job-123',
          progress: 50,
          currentProfile: '1080p',
        },
      };

      expect(event.data).toHaveProperty('progress');
      expect(event.data.progress).toBeGreaterThanOrEqual(0);
      expect(event.data.progress).toBeLessThanOrEqual(100);
    });
  });

  describe('transcode.completed', () => {
    it('should have output info', () => {
      const event = {
        type: 'transcode.completed',
        data: {
          jobId: 'job-123',
          videoId: 'video-123',
          outputs: [
            { profile: '1080p', url: 's3://bucket/1080p.m3u8' },
            { profile: '720p', url: 's3://bucket/720p.m3u8' },
          ],
          completedAt: '2024-01-01T01:00:00Z',
        },
      };

      expect(event.data).toHaveProperty('outputs');
      expect(event.data.outputs.length).toBeGreaterThan(0);
    });
  });

  describe('transcode.failed', () => {
    it('should have error info', () => {
      const event = {
        type: 'transcode.failed',
        data: {
          jobId: 'job-123',
          videoId: 'video-123',
          error: {
            code: 'CODEC_ERROR',
            message: 'Unsupported codec',
          },
          failedAt: '2024-01-01T00:30:00Z',
        },
      };

      expect(event.data).toHaveProperty('error');
      expect(event.data.error).toHaveProperty('code');
      expect(event.data.error).toHaveProperty('message');
    });
  });
});

describe('Subscription Event Contracts', () => {
  describe('subscription.created', () => {
    it('should have subscription info', () => {
      const event = {
        type: 'subscription.created',
        data: {
          subscriptionId: 'sub-123',
          userId: 'user-123',
          planId: 'plan-premium',
          startDate: '2024-01-01',
        },
      };

      expect(event.data).toHaveProperty('subscriptionId');
      expect(event.data).toHaveProperty('planId');
    });
  });

  describe('subscription.updated', () => {
    it('should have plan change info', () => {
      const event = {
        type: 'subscription.updated',
        data: {
          subscriptionId: 'sub-123',
          previousPlan: 'plan-basic',
          newPlan: 'plan-premium',
          effectiveDate: '2024-02-01',
        },
      };

      expect(event.data).toHaveProperty('previousPlan');
      expect(event.data).toHaveProperty('newPlan');
    });
  });

  describe('subscription.canceled', () => {
    it('should have cancellation info', () => {
      const event = {
        type: 'subscription.canceled',
        data: {
          subscriptionId: 'sub-123',
          userId: 'user-123',
          canceledAt: '2024-01-15T00:00:00Z',
          effectiveDate: '2024-02-01',
          reason: 'user_requested',
        },
      };

      expect(event.data).toHaveProperty('canceledAt');
      expect(event.data).toHaveProperty('effectiveDate');
    });
  });
});

describe('Payment Event Contracts', () => {
  describe('payment.succeeded', () => {
    it('should have payment info', () => {
      const event = {
        type: 'payment.succeeded',
        data: {
          paymentId: 'pay-123',
          userId: 'user-123',
          amount: 999,
          currency: 'usd',
          method: 'card',
        },
      };

      expect(event.data).toHaveProperty('amount');
      expect(event.data).toHaveProperty('currency');
    });
  });

  describe('payment.failed', () => {
    it('should have failure info', () => {
      const event = {
        type: 'payment.failed',
        data: {
          paymentId: 'pay-123',
          userId: 'user-123',
          amount: 999,
          error: {
            code: 'card_declined',
            message: 'Card was declined',
          },
        },
      };

      expect(event.data).toHaveProperty('error');
    });
  });
});
