const fastify = require('fastify')({ logger: false })

fastify.get('/holamundo', () => ({ mensaje: 'hola mundo' }))

fastify.listen({ port: 3000, host: '0.0.0.0' })
