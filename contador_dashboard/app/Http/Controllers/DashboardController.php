<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Http\Client\Pool;

class DashboardController extends Controller
{
    protected $apiUrl;

    public function __construct()
    {
        // Se cambió el prefijo original porque la nueva API no usa /api/v1 por defecto
        $this->apiUrl = config('services.api.url', 'http://api:8000');
    }

    public function index()
    {
        try {
            $responses = Http::pool(fn (Pool $pool) => [
                $pool->as('summary')->timeout(10)->get($this->apiUrl . '/dashboard/summary'),
                $pool->as('areas')->timeout(10)->get($this->apiUrl . '/dashboard/areas'),
                $pool->as('events')->timeout(10)->get($this->apiUrl . '/dashboard/events', ['limit' => 10])
            ]);
            
            if ($responses['summary']->successful() && $responses['areas']->successful() && $responses['events']->successful()) {
                $summaryData = $responses['summary']->json();
                $areasData = $responses['areas']->json();
                $eventsData = $responses['events']->json();
                
                $estados_areas = collect($areasData['items'] ?? [])->map(function($area) {
                    return (object)[
                        'name' => $area['name'],
                        'estado' => (object)['people_count' => $area['people_count'] ?? 0]
                    ];
                });

                $kpis = [
                    'total_personas' => $summaryData['total_people'] ?? 0,
                    'areas_activas' => $estados_areas->filter(fn($a) => $a->estado->people_count > 0)->count(),
                    'entradas_hoy' => $summaryData['total_entries'] ?? 0,
                    'salidas_hoy' => $summaryData['total_exits'] ?? 0,
                ];

                $eventos_recientes = collect($eventsData['items'] ?? [])->map(function($ev) {
                    return (object)[
                        'hora' => date('H:i:s', strtotime($ev['timestamp'])),
                        'area_name' => $ev['area_name'],
                        'event' => strtoupper($ev['event']),
                        'track_id' => $ev['track_id']
                    ];
                });

                return view('dashboard.index', compact('kpis', 'eventos_recientes', 'estados_areas'));
            }
            
            throw new \Exception("Error al conectar con la API: Alguna petición falló.");

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
            $responses = Http::pool(fn (Pool $pool) => [
                $pool->as('summary')->timeout(10)->get($this->apiUrl . '/dashboard/summary'),
                $pool->as('areas')->timeout(10)->get($this->apiUrl . '/dashboard/areas'),
                $pool->as('events')->timeout(10)->get($this->apiUrl . '/dashboard/events', ['limit' => 10])
            ]);
            
            if ($responses['summary']->successful() && $responses['areas']->successful() && $responses['events']->successful()) {
                $summaryData = $responses['summary']->json();
                $areasData = $responses['areas']->json();
                $eventsData = $responses['events']->json();
                
                $conteo_por_area = collect($areasData['items'] ?? [])->map(function($area) {
                    return [
                        'name' => $area['name'],
                        'count' => $area['people_count'] ?? 0
                    ];
                })->toArray();
                
                $eventos_recientes = collect($eventsData['items'] ?? [])->map(function($ev) {
                    return [
                        'hora' => date('H:i:s', strtotime($ev['timestamp'])),
                        'area_name' => $ev['area_name'],
                        'event' => strtoupper($ev['event']),
                        'track_id' => $ev['track_id']
                    ];
                })->toArray();

                $areas_activas = collect($conteo_por_area)->filter(fn($a) => $a['count'] > 0)->count();

                return response()->json([
                    'total_personas' => $summaryData['total_people'] ?? 0,
                    'areas_activas' => $areas_activas,
                    'entradas_hoy' => $summaryData['total_entries'] ?? 0,
                    'salidas_hoy' => $summaryData['total_exits'] ?? 0,
                    'conteo_por_area' => $conteo_por_area,
                    'eventos_recientes' => $eventos_recientes
                ]);
            }
            
            return response()->json(['error' => 'API Unavailable'], 503);
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }
}