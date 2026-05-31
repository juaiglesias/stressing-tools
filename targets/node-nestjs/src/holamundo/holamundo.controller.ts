import { Controller, Get } from '@nestjs/common'

@Controller()
export class HolamundoController {
  @Get('holamundo')
  holamundo() {
    return { mensaje: 'hola mundo' }
  }
}
