/**
 * Error Handler Middleware
 */

function errorHandler(err, req, res, next) {
  console.error('Error:', err);

  
  const response = {
    error: err.message,
    
    stack: process.env.NODE_ENV !== 'production' ? err.stack : undefined,
  };

  
  if (err.code) {
    response.code = err.code;
  }

  const status = err.status || err.statusCode || 500;
  res.status(status).json(response);
}

module.exports = { errorHandler };
