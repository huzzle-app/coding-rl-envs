/**
 * Service Proxy Middleware
 *
 * BUG I1: SQL injection through search parameters
 * BUG I4: SSRF through URL parameter
 */

const axios = require('axios');
const config = require('../config');

async function proxyRequest(req, serviceName, path) {
  const service = config.services[serviceName];

  if (!service) {
    throw new Error(`Unknown service: ${serviceName}`);
  }

  const response = await axios({
    method: req.method,
    url: `${service.url}${path}`,
    data: req.body,
    headers: {
      ...req.headers,
      host: undefined,
      'x-user-id': req.user?.userId,
      'x-user-email': req.user?.email,
    },
    params: req.query,
    timeout: 30000,
  });

  return response.data;
}

function createProxyMiddleware(serviceName) {
  return async (req, res, next) => {
    try {
      const path = req.path.replace(`/${serviceName}`, '') || '/';
      const result = await proxyRequest(req, serviceName, path);
      res.json(result);
    } catch (error) {
      if (error.response) {
        res.status(error.response.status).json(error.response.data);
      } else {
        next(error);
      }
    }
  };
}

// Search handler with SQL injection vulnerability

function createSearchHandler(serviceName) {
  return async (req, res, next) => {
    try {
      const { q, sort, order } = req.query;

      
      // Attacker could pass: q='; DROP TABLE videos; --
      const searchQuery = {
        // This would be sent to the catalog service which builds SQL
        rawQuery: `SELECT * FROM videos WHERE title LIKE '%${q}%' ORDER BY ${sort} ${order}`,
        query: q,
        sort,
        order,
      };

      const result = await proxyRequest(req, serviceName, '/search', {
        method: 'POST',
        data: searchQuery,
      });

      res.json(result);
    } catch (error) {
      next(error);
    }
  };
}

// Thumbnail proxy with SSRF vulnerability

function createThumbnailProxy() {
  return async (req, res, next) => {
    try {
      const { url } = req.query;

      
      // Attacker could access internal services: url=http://169.254.169.254/metadata
      if (!url) {
        return res.status(400).json({ error: 'URL required' });
      }

      
      const response = await axios.get(url, {
        responseType: 'arraybuffer',
        timeout: 5000,
      });

      res.set('Content-Type', response.headers['content-type']);
      res.send(response.data);
    } catch (error) {
      next(error);
    }
  };
}

// Webhook handler with SSRF

async function sendWebhook(webhookUrl, payload) {
  
  // Could be used to probe internal network
  try {
    await axios.post(webhookUrl, payload, {
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return true;
  } catch (error) {
    console.error('Webhook failed:', error.message);
    return false;
  }
}

module.exports = {
  proxyRequest,
  createProxyMiddleware,
  createSearchHandler,
  createThumbnailProxy,
  sendWebhook,
};
