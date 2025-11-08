const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// In-memory data store
let products = [
  { id: 1, name: 'Laptop', price: 999.99, stock: 10 },
  { id: 2, name: 'Mouse', price: 29.99, stock: 50 },
  { id: 3, name: 'Keyboard', price: 79.99, stock: 30 }
];

let nextId = 4;

// Middleware for logging
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  next();
});

// GET /api/products - Get all products
app.get('/api/products', (req, res) => {
  const { minPrice, maxPrice, inStock } = req.query;
  
  let filtered = [...products];
  
  if (minPrice) {
    filtered = filtered.filter(p => p.price >= parseFloat(minPrice));
  }
  
  if (maxPrice) {
    filtered = filtered.filter(p => p.price <= parseFloat(maxPrice));
  }
  
  if (inStock === 'true') {
    filtered = filtered.filter(p => p.stock > 0);
  }
  
  res.json({
    count: filtered.length,
    products: filtered
  });
});

// GET /api/products/:id - Get product by ID
app.get('/api/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const product = products.find(p => p.id === id);
  
  if (!product) {
    return res.status(404).json({
      error: 'Product not found',
      id: id
    });
  }
  
  res.json(product);
});

// POST /api/products - Create new product
app.post('/api/products', (req, res) => {
  const { name, price, stock } = req.body;
  
  // Validation
  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    return res.status(400).json({
      error: 'Invalid product name'
    });
  }
  
  if (!price || typeof price !== 'number' || price <= 0) {
    return res.status(400).json({
      error: 'Invalid price - must be a positive number'
    });
  }
  
  if (stock === undefined || typeof stock !== 'number' || stock < 0) {
    return res.status(400).json({
      error: 'Invalid stock - must be a non-negative number'
    });
  }
  
  const newProduct = {
    id: nextId++,
    name: name.trim(),
    price: parseFloat(price.toFixed(2)),
    stock: parseInt(stock)
  };
  
  products.push(newProduct);
  
  res.status(201).json(newProduct);
});

// PUT /api/products/:id - Update product
app.put('/api/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const productIndex = products.findIndex(p => p.id === id);
  
  if (productIndex === -1) {
    return res.status(404).json({
      error: 'Product not found',
      id: id
    });
  }
  
  const { name, price, stock } = req.body;
  const product = products[productIndex];
  
  // Update only provided fields
  if (name !== undefined) {
    if (typeof name !== 'string' || name.trim().length === 0) {
      return res.status(400).json({
        error: 'Invalid product name'
      });
    }
    product.name = name.trim();
  }
  
  if (price !== undefined) {
    if (typeof price !== 'number' || price <= 0) {
      return res.status(400).json({
        error: 'Invalid price - must be a positive number'
      });
    }
    product.price = parseFloat(price.toFixed(2));
  }
  
  if (stock !== undefined) {
    if (typeof stock !== 'number' || stock < 0) {
      return res.status(400).json({
        error: 'Invalid stock - must be a non-negative number'
      });
    }
    product.stock = parseInt(stock);
  }
  
  products[productIndex] = product;
  res.json(product);
});

// DELETE /api/products/:id - Delete product
app.delete('/api/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const productIndex = products.findIndex(p => p.id === id);
  
  if (productIndex === -1) {
    return res.status(404).json({
      error: 'Product not found',
      id: id
    });
  }
  
  products.splice(productIndex, 1);
  res.status(204).send();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: 'Endpoint not found',
    path: req.path
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    error: 'Internal server error',
    message: err.message
  });
});

// Start server
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Product API server running on port ${PORT}`);
  });
}

module.exports = app;

