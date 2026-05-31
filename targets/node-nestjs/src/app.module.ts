import { Module } from '@nestjs/common'
import { HolamundoController } from './holamundo/holamundo.controller'

@Module({
  controllers: [HolamundoController],
})
export class AppModule {}
