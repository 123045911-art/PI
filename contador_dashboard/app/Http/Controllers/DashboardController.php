<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class DashboardController extends Controller
{
    protected $apiUrl;

    public function __construct()
    {
        $this->apiUrl = config('services.api.url', 'http://fastapi:8000/api/v1');
    }

    public function index()
    {
        try {
            $response = Http::timeout(10)->get($this->apiUrl . '/dashboard/summary');
            
            if ($response->successful()) {
                $data = $response->json();
                
                $kpis = [
                    'total_personas' => $data['total_personas'] ?? 0,
                    'areas_activas' => $data['areas_activas'] ?? 0,
                    'entradas_hoy' => $data['entradas_hoy'] ?? 0,
                    'salidas_hoy' => $data['salidas_hoy'] ?? 0,
                ];

                $eventos_recientes = collect($data['eventos_recientes'] ?? [])->map(function($ev) {
                    return (object)$ev;
                });

                $estados_areas = collect($data['conteo_por_area'] ?? [])->map(function($area) {
                    return (object)[
                        'name' => $area['name'],
                        'estado' => (object)['people_count' => $area['count'] ?? 0]
                    ];
                });

                return view('dashboard.index', compact('kpis', 'eventos_recientes', 'estados_areas'));
            }
            
            throw new \Exception("Error al conectar con la API: " . $response->status());

        } catch (\Exception $e) {
            Log::error("Dashboard Error: " . $e->getMessage());
            
            // Retorno con datos vacíos en caso de error para no romper la vista
            $kpis = ['total_personas' => 0, 'areas_activas' => 0, 'entradas_hoy' => 0, 'salidas_hoy' => 0];
            $eventos_recientes = collect([]);
            $estados_areas = collect([]);
            
            return view('dashboard.index', compact('kpis', 'eventos_recientes', 'estados_areas'))
                ->with('error', 'No se pudo conectar con el servicio de datos.');
        }
    }

    public function dataApi()
    {
        try {
            $response = Http::timeout(10)->get($this->apiUrl . '/dashboard/summary');
            
            if ($response->successful()) {
                return response()->json($response->json());
            }
            
            return response()->json(['error' => 'API Unavailable'], 503);
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }
}