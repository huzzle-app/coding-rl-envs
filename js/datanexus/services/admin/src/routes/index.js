const express = require('express');
const router = express.Router();

router.get('/tenants', (req, res) => {
  res.json({ tenants: [] });
});

router.post('/tenants', (req, res) => {
  res.json({ id: 'tenant-1' });
});

module.exports = router;
