/**
 * Authentication Routes
 */

const express = require('express');
const router = express.Router();

router.post('/register', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { email, password, firstName, lastName } = req.body;

    // Check if user exists
    const existing = await db.User.findOne({ where: { email } });
    if (existing) {
      return res.status(400).json({ error: 'Email already registered' });
    }

    // Create user
    const user = await db.User.create({
      email,
      password,
      firstName,
      lastName,
    });

    // Generate tokens
    const tokens = services.jwtService.generateTokenPair(user);

    res.status(201).json({
      user: user.toJSON(),
      ...tokens,
    });
  } catch (error) {
    next(error);
  }
});

router.post('/login', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { email, password } = req.body;

    // Find user
    const user = await db.User.findOne({ where: { email } });
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Validate password
    const valid = await user.validatePassword(password);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Update last login
    user.lastLoginAt = new Date();
    await user.save();

    // Generate tokens
    const tokens = services.jwtService.generateTokenPair(user);

    res.json({
      user: user.toJSON(),
      ...tokens,
    });
  } catch (error) {
    next(error);
  }
});

router.post('/refresh', async (req, res, next) => {
  try {
    const { db, services } = req.app.locals;
    const { refreshToken } = req.body;

    // Verify refresh token
    const decoded = services.jwtService.verifyRefreshToken(refreshToken);
    if (!decoded) {
      return res.status(401).json({ error: 'Invalid refresh token' });
    }

    // Get user
    const user = await db.User.findByPk(decoded.userId);
    if (!user || !user.isActive) {
      return res.status(401).json({ error: 'User not found or inactive' });
    }

    // Generate new tokens
    const tokens = services.jwtService.generateTokenPair(user);

    res.json(tokens);
  } catch (error) {
    next(error);
  }
});

router.get('/oauth/:provider', async (req, res, next) => {
  try {
    const { services } = req.app.locals;
    const { provider } = req.params;
    const redirectUri = `${req.protocol}://${req.get('host')}/api/auth/oauth/${provider}/callback`;

    const oauthService = services.oauthService;
    if (!oauthService) {
      return res.status(501).json({ error: 'OAuth not configured' });
    }

    const { url, state } = oauthService.generateAuthUrl(provider, redirectUri);
    res.json({ url, state });
  } catch (error) {
    next(error);
  }
});

router.get('/oauth/:provider/callback', async (req, res, next) => {
  try {
    const { services } = req.app.locals;
    const { provider } = req.params;
    const { code, state } = req.query;
    const redirectUri = `${req.protocol}://${req.get('host')}/api/auth/oauth/${provider}/callback`;

    const oauthService = services.oauthService;
    if (!oauthService) {
      return res.status(501).json({ error: 'OAuth not configured' });
    }

    const result = await oauthService.handleCallback(provider, code, state, redirectUri);

    res.json({
      user: result.user,
      ...result.tokens,
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
