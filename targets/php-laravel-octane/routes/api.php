<?php

use Illuminate\Support\Facades\Route;

Route::get('/holamundo', fn() => response()->json(['mensaje' => 'hola mundo']));
