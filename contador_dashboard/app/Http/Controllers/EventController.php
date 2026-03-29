<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class EventController extends Controller
{
    protected $apiUrl;

    public function __construct()
    {
        $this->apiUrl = config('services.api.url', 'http://fastapi:8000/api/v1');
    }

    public function index(Request $request)
    {
        try {
            $page = (int) $request->get('page', 1);
            $limit = 50;
            $offset = ($page - 1) * $limit;

            $response = Http::get($this->apiUrl . '/events', [
                'limit' => $limit,
                'offset' => $offset
            ]);

            if ($response->successful()) {
                $data = $response->json();
                
                $eventos = collect($data['data'])->map(function($ev) {
                    return (object)[
                        'id' => $ev['id'],
                        'timestamp' => $ev['timestamp'],
                        'event' => $ev['event'],
                        'track_id' => $ev['track_id'],
                        'dwell' => $ev['dwell'] ?? 0,
                        'area' => (object)['name' => $ev['area_name']]
                    ];
                });

                $total = $data['total'] ?? 0;
                $totalPages = (int) ceil($total / $limit);

                return view('eventos.index', compact('eventos', 'page', 'totalPages', 'total'));
            }
            throw new \Exception("Error API: " . $response->status());
        } catch (\Exception $e) {
            Log::error("Event Index Error: " . $e->getMessage());
            $eventos = collect([]);
            $page = 1;
            $totalPages = 1;
            $total = 0;
            return view('eventos.index', compact('eventos', 'page', 'totalPages', 'total'))
                ->with('error', 'No se pudieron cargar los eventos.');
        }
    }
}