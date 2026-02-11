/**
 * Error Handler Middleware
 */

function errorHandler(err, req, res, next) {
  console.error('Request error:', err);

  const statusCode = err.statusCode || 500;

  
  res.status(statusCode).json({
    error: err.message,
    
    stack: process.env.NODE_ENV === 'production' ? undefined : err.stack,
    path: req.path,
    
    input: req.body,
  });
}

module.exports = { errorHandler };
