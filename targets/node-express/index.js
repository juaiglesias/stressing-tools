const express = require('express')
const app = express()

app.get('/holamundo', (req, res) => {
  res.json({ mensaje: 'hola mundo' })
})

app.listen(3000, '0.0.0.0')
