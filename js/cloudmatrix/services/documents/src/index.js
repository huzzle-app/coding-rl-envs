/**
 * Documents Service
 */

const express = require('express');
const app = express();
app.use(express.json({ limit: '50mb' }));

const config = {
  port: process.env.PORT || 3003,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

const { DocumentService } = require('./services/document');

app.get('/documents', async (req, res) => {
  try {
    const service = new DocumentService();
    const docs = await service.listDocuments(req.query);
    res.json(docs);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/documents/:id', async (req, res) => {
  res.json({ id: req.params.id, title: 'Test Document', content: {} });
});

app.post('/documents', async (req, res) => {
  try {
    const service = new DocumentService();
    const doc = await service.createDocument(req.body);
    res.status(201).json(doc);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.put('/documents/:id', async (req, res) => {
  try {
    const service = new DocumentService();
    const doc = await service.updateDocument(req.params.id, req.body);
    res.json(doc);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(config.port, () => {
  console.log(`Documents service listening on port ${config.port}`);
});

module.exports = app;
