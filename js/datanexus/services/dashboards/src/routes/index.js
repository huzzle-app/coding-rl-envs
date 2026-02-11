const express = require('express');
const router = express.Router();

router.get('/dashboards', (req, res) => {
  res.json({ dashboards: [] });
});

router.post('/dashboards', (req, res) => {
  res.json({ id: 'dashboard-1' });
});

module.exports = router;
