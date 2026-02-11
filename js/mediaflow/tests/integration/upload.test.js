/**
 * Upload Integration Tests
 *
 * Tests bugs D1 (saga compensation), D2 (saga dependencies), I4 (SSRF)
 */

describe('Upload Saga', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const upload = require('../../../services/upload/src/index');
    app = upload;
    request = global.testUtils.mockRequest(app);
  });

  describe('saga compensation', () => {
    
    it('saga compensation test', async () => {
      const compensationSteps = [];

      // Mock saga to track compensation
      jest.doMock('../../../services/upload/src/index', () => {
        const original = jest.requireActual('../../../services/upload/src/index');

        class MockUploadSaga {
          constructor() {
            this.completedSteps = [];
          }

          async execute(videoId, options) {
            // Simulate failure at queueTranscode
            this.completedSteps = [
              { name: 'createRecord', compensate: 'deleteRecord' },
              { name: 'uploadToStorage', compensate: 'deleteFromStorage' },
              { name: 'extractMetadata', compensate: null },
              { name: 'generateThumbnail', compensate: 'deleteThumbnail' },
            ];

            await this._compensate(videoId);
            throw new Error('Simulated failure');
          }

          async _compensate(videoId) {
            for (const step of this.completedSteps.reverse()) {
              if (step.compensate) {
                try {
                  await this._executeCompensation(step.compensate, videoId);
                  compensationSteps.push(step.compensate);
                } catch (e) {
                  
                  throw e;
                }
              }
            }
          }

          async _executeCompensation(name, videoId) {
            if (name === 'deleteFromStorage') {
              // Simulate compensation failure
              throw new Error('Storage delete failed');
            }
          }
        }

        return { ...original, UploadSaga: MockUploadSaga };
      });

      
      // deleteThumbnail should still be called
      expect(compensationSteps).toContain('deleteThumbnail');
      expect(compensationSteps).toContain('deleteRecord');
    });

    
    it('compensation retry test', async () => {
      const upload = jest.requireActual('../../../services/upload/src/index');
      const saga = new upload.UploadSaga();

      let retryCount = 0;

      // Override compensation to fail then succeed
      saga._executeCompensation = jest.fn(async (name, videoId) => {
        retryCount++;
        if (retryCount < 3) {
          throw new Error('Temporary failure');
        }
        return true;
      });

      // Execute a compensation that should retry on failure
      try {
        await saga._compensate('test-video', [
          { name: 'uploadToStorage', compensate: 'deleteFromStorage' },
        ]);
      } catch (e) {
        // May still throw if no retry logic
      }

      
      expect(retryCount).toBeGreaterThanOrEqual(3);
    });
  });

  describe('saga step dependencies', () => {
    
    it('saga dependencies test', async () => {
      const upload = require('../../../services/upload/src/index');
      const saga = new upload.UploadSaga();

      const stepOrder = [];
      const originalExecute = saga._executeStep?.bind(saga);

      // Track step execution order
      saga._executeStep = async (stepName, videoId, options) => {
        stepOrder.push(stepName);

        // Simulate async storage upload
        if (stepName === 'uploadToStorage') {
          await global.testUtils.delay(50);
        }

        if (originalExecute) {
          return originalExecute(stepName, videoId, options);
        }
        return { success: true };
      };

      try {
        await saga.execute('test-video', { inputUrl: 's3://test/input.mp4' });
      } catch (e) {
        // May fail due to bugs, that's expected
      }

      
      // Verify dependency order is respected
      if (stepOrder.includes('uploadToStorage') && stepOrder.includes('generateThumbnail')) {
        const uploadIdx = stepOrder.indexOf('uploadToStorage');
        const thumbIdx = stepOrder.indexOf('generateThumbnail');
        expect(thumbIdx).toBeGreaterThan(uploadIdx);
      }
      // At minimum, steps should have been attempted
      expect(stepOrder.length).toBeGreaterThan(0);
    });

    it('parallel step execution test', async () => {
      const upload = require('../../../services/upload/src/index');
      const saga = new upload.UploadSaga();

      const stepTimes = new Map();
      const originalExecute = saga._executeStep?.bind(saga);

      saga._executeStep = async (stepName, videoId, options) => {
        stepTimes.set(stepName, { start: Date.now() });
        await global.testUtils.delay(20);
        stepTimes.get(stepName).end = Date.now();

        if (originalExecute) {
          return originalExecute(stepName, videoId, options);
        }
        return { success: true };
      };

      try {
        await saga.execute('test-video', { inputUrl: 's3://test/input.mp4' });
      } catch (e) {
        // Expected
      }

      // Steps that have dependencies must not overlap in time
      // createRecord must complete before uploadToStorage starts
      if (stepTimes.has('createRecord') && stepTimes.has('uploadToStorage')) {
        expect(stepTimes.get('uploadToStorage').start).toBeGreaterThanOrEqual(
          stepTimes.get('createRecord').end
        );
      }
    });
  });
});

describe('SSRF Prevention', () => {
  let app;
  let request;
  let axios;

  beforeEach(() => {
    jest.resetModules();

    axios = {
      get: jest.fn(),
    };

    jest.doMock('axios', () => axios);

    const upload = require('../../../services/upload/src/index');
    app = upload;
    request = global.testUtils.mockRequest(app);
  });

  
  it('SSRF test metadata endpoint', async () => {
    axios.get.mockResolvedValue({ data: Buffer.from('image-data') });

    const response = await request
      .post('/videos/video-1/thumbnail-url')
      .send({
        url: 'http://169.254.169.254/latest/meta-data/',
      });

    
    expect(response.status).toBe(400);
    expect(axios.get).not.toHaveBeenCalled();
  });

  
  it('SSRF test internal service', async () => {
    axios.get.mockResolvedValue({ data: Buffer.from('data') });

    const response = await request
      .post('/videos/video-1/thumbnail-url')
      .send({
        url: 'http://localhost:3001/internal/secrets',
      });

    
    expect(response.status).toBe(400);
  });

  
  it('SSRF test private IP', async () => {
    axios.get.mockResolvedValue({ data: Buffer.from('data') });

    const response = await request
      .post('/videos/video-1/thumbnail-url')
      .send({
        url: 'http://192.168.1.1/admin',
      });

    
    expect(response.status).toBe(400);
  });

  
  it('SSRF test URL schemes', async () => {
    axios.get.mockResolvedValue({ data: Buffer.from('data') });

    // File scheme
    const fileResponse = await request
      .post('/videos/video-1/thumbnail-url')
      .send({
        url: 'file:///etc/passwd',
      });

    expect(fileResponse.status).toBe(400);

    // FTP scheme
    const ftpResponse = await request
      .post('/videos/video-1/thumbnail-url')
      .send({
        url: 'ftp://internal-ftp/data',
      });

    expect(ftpResponse.status).toBe(400);
  });

  it('valid thumbnail URL test', async () => {
    axios.get.mockResolvedValue({
      data: Buffer.from('valid-image'),
      headers: { 'content-type': 'image/jpeg' },
    });

    const response = await request
      .post('/videos/video-1/thumbnail-url')
      .send({
        url: 'https://images.example.com/thumbnail.jpg',
      });

    expect(response.status).toBe(200);
  });
});

describe('Upload API', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const upload = require('../../../services/upload/src/index');
    app = upload;
    request = global.testUtils.mockRequest(app);
  });

  it('should reject missing file', async () => {
    const response = await request.post('/videos');

    expect(response.status).toBe(400);
    expect(response.body.error).toBe('No video file provided');
  });

  it('should get upload status', async () => {
    const response = await request.get('/videos/video-123/status');

    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('status');
    expect(response.body).toHaveProperty('progress');
  });

  it('should check health', async () => {
    const response = await request.get('/health');

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('healthy');
    expect(response.body.service).toBe('upload');
  });
});
