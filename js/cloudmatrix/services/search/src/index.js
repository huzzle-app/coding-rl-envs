/**
 * Search Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3007,
  
  elasticsearchUrl: process.env.ELASTICSEARCH_URL || 'http://localhost:9200',
  redisHost: process.env.REDIS_HOST || 'localhost',
};

const { SearchService } = require('./services/search');


// Should create index mappings before accepting requests

app.get('/search', async (req, res) => {
  try {
    const service = new SearchService();
    const results = await service.search(req.query);
    res.json(results);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/search/autocomplete', async (req, res) => {
  try {
    const service = new SearchService();
    const results = await service.autocomplete(req.query.prefix);
    res.json(results);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/search/reindex', async (req, res) => {
  try {
    const service = new SearchService();
    
    await service.reindex();
    res.json({ status: 'reindexing' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(config.port, () => {
  console.log(`Search service listening on port ${config.port}`);
});

module.exports = app;
