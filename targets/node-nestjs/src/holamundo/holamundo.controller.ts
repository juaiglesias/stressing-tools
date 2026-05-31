import { Controller, Get, Post, Query, Body, HttpCode } from '@nestjs/common'

const MOD = 1000000007

// O(n²) sobre n objetos + O(C³) multiplicación de matrices C×C (C=64).
function cpuCompute(n: number): number {
  const objects = new Array(n)
  for (let i = 0; i < n; i++) objects[i] = { id: i, x: (i * 31) % 1000 }
  const derived = new Array(n)
  for (let i = 0; i < n; i++) derived[i] = (objects[i].x * 2 + 1) % 1000

  let checksum = 0
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      checksum = (checksum + derived[i] * derived[j]) % MOD
    }
  }

  const C = 64
  for (let i = 0; i < C; i++) {
    for (let j = 0; j < C; j++) {
      let s = 0
      for (let k = 0; k < C; k++) s += ((i * C + k) % 100) * ((k + j) % 100)
      checksum = (checksum + s) % MOD
    }
  }
  return checksum
}

// Aloca n objetos anidados (todos vivos a la vez) y serializa una muestra.
function memAlloc(n: number) {
  const arr = new Array(n)
  for (let i = 0; i < n; i++) {
    arr[i] = {
      id: i,
      name: 'item-' + i,
      tags: [i, i + 1, i + 2],
      payload: { a: i % 100, b: (i * 2) % 100, c: (i * 3) % 100 },
    }
  }
  let sum = 0
  for (let i = 0; i < n; i++) sum += arr[i].payload.a
  return { count: n, sum, sample: arr.slice(0, 100) }
}

@Controller()
export class HolamundoController {
  @Get('holamundo')
  holamundo() {
    return { mensaje: 'hola mundo' }
  }

  @Get('dbquery')
  async dbquery() {
    await new Promise((r) => setTimeout(r, 25))
    const rows = []
    for (let k = 0; k < 10; k++) rows.push({ id: k, value: k * 10 })
    return { rows }
  }

  @Get('cpucompute')
  cpucompute(@Query('n') n: string) {
    const num = parseInt(n, 10) || 200
    return { checksum: cpuCompute(num), n: num }
  }

  @Get('memalloc')
  memalloc(@Query('n') n: string) {
    const num = parseInt(n, 10) || 20000
    return memAlloc(num)
  }

  @Post('payload')
  @HttpCode(200)
  payload(@Body() body: any) {
    const items = (body && body.items) || []
    let activeCount = 0
    let total = 0
    for (const it of items) {
      if (it.active) {
        activeCount++
        total += it.value
      }
    }
    const sample = items.slice(0, 10).map((it: any) => ({ id: it.id, name: String(it.name).toUpperCase(), value: it.value }))
    return { received: items.length, activeCount, total, sample }
  }
}
