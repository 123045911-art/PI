<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class AreaController extends Controller
{
    protected $apiUrl;

    public function __construct()
    {
        $this->apiUrl = config('services.api.url', 'http://fastapi:8000/api/v1');
    }

    public function index()
    {
        try {
            $response = Http::get($this->apiUrl . '/areas');
            
            if ($response->successful()) {
                $areas = collect($response->json())->map(function($area) {
                    return (object)[
                        'id' => $area['id'],
                        'name' => $area['name'],
                        'estado' => (object)[
                            'people_count' => $area['people_count'] ?? 0,
                            'last_update' => $area['last_update'] ?? 'N/A'
                        ]
                    ];
                });
                return view('areas.index', compact('areas'));
            }
            throw new \Exception("Error API: " . $response->status());
        } catch (\Exception $e) {
            Log::error("Area Index Error: " . $e->getMessage());
            $areas = collect([]);
            return view('areas.index', compact('areas'))->with('error', 'No se pudieron cargar las áreas.');
        }
    }

    public function edit($id)
    {
        try {
            $response = Http::get($this->apiUrl . '/areas/' . $id);
            if ($response->successful()) {
                $area = (object)$response->json();
                return view('areas.edit', compact('area'));
            }
            return redirect()->route('areas.index')->with('error', 'Área no encontrada.');
        } catch (\Exception $e) {
            return redirect()->route('areas.index')->with('error', 'Error al buscar el área.');
        }
    }

    public function update(Request $request, $id)
    {
        $request->validate([
            'name' => 'required|string|max:255',
        ]);

        try {
            $response = Http::withHeaders([
                'X-Is-Admin' => session('is_admin', false)
            ])->patch($this->apiUrl . '/areas/' . $id, [
                'name' => $request->input('name')
            ]);

            if ($response->successful()) {
                return redirect()->route('areas.index')
                    ->with('success', 'El área ha sido renombrada exitosamente.');
            }
            throw new \Exception("Error API: " . $response->status());
        } catch (\Exception $e) {
            return redirect()->route('areas.index')
                ->with('error', 'Error al renombrar el área: ' . $e->getMessage());
        }
    }

    public function destroy($id)
    {
        try {
            $response = Http::withHeaders([
                'X-Is-Admin' => session('is_admin', false)
            ])->delete($this->apiUrl . '/areas/' . $id);
            if ($response->successful()) {
                return redirect()->route('areas.index')
                    ->with('success', 'El área y sus datos asociados han sido eliminados.');
            }
            throw new \Exception("Error API: " . $response->status());
        } catch (\Exception $e) {
            return redirect()->route('areas.index')
                ->with('error', 'Error al eliminar el área: ' . $e->getMessage());
        }
    }
}