<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

// Nota: la lógica va inline en cada closure (no funciones top-level) para que
// `php artisan route:cache` (SerializableClosure) funcione: cuando las rutas
// están cacheadas, este archivo no se vuelve a incluir en cada request.

Route::get('/holamundo', fn() => response()->json(['mensaje' => 'hola mundo']));

Route::get('/dbquery', function () {
    usleep(25000); // simula I/O de DB (~25ms, bloqueante en PHP)
    $rows = [];
    for ($k = 0; $k < 10; $k++) {
        $rows[] = ['id' => $k, 'value' => $k * 10];
    }
    return response()->json(['rows' => $rows]);
});

Route::get('/cpucompute', function (Request $request) {
    $n = (int) $request->query('n', 200);
    $mod = 1000000007;

    $derived = [];
    for ($i = 0; $i < $n; $i++) {
        $x = ($i * 31) % 1000;
        $derived[$i] = ($x * 2 + 1) % 1000;
    }

    $checksum = 0;
    for ($i = 0; $i < $n; $i++) {
        $di = $derived[$i];
        for ($j = 0; $j < $n; $j++) {
            $checksum = ($checksum + $di * $derived[$j]) % $mod;
        }
    }

    $C = 64;
    for ($i = 0; $i < $C; $i++) {
        for ($j = 0; $j < $C; $j++) {
            $s = 0;
            for ($k = 0; $k < $C; $k++) {
                $s += (($i * $C + $k) % 100) * (($k + $j) % 100);
            }
            $checksum = ($checksum + $s) % $mod;
        }
    }

    return response()->json(['checksum' => $checksum, 'n' => $n]);
});

Route::get('/memalloc', function (Request $request) {
    $n = (int) $request->query('n', 20000);
    $arr = [];
    for ($i = 0; $i < $n; $i++) {
        $arr[$i] = [
            'id' => $i,
            'name' => 'item-' . $i,
            'tags' => [$i, $i + 1, $i + 2],
            'payload' => ['a' => $i % 100, 'b' => ($i * 2) % 100, 'c' => ($i * 3) % 100],
        ];
    }
    $sum = 0;
    for ($i = 0; $i < $n; $i++) {
        $sum += $arr[$i]['payload']['a'];
    }
    return response()->json(['count' => $n, 'sum' => $sum, 'sample' => array_slice($arr, 0, 100)]);
});

Route::post('/payload', function (Request $request) {
    $items = $request->input('items', []);
    $activeCount = 0;
    $total = 0;
    foreach ($items as $it) {
        if (!empty($it['active'])) {
            $activeCount++;
            $total += $it['value'];
        }
    }
    $sample = [];
    foreach (array_slice($items, 0, 10) as $it) {
        $sample[] = ['id' => $it['id'], 'name' => strtoupper((string) $it['name']), 'value' => $it['value']];
    }
    return response()->json([
        'received' => count($items),
        'activeCount' => $activeCount,
        'total' => $total,
        'sample' => $sample,
    ]);
});
