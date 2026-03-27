<?php
namespace App\Http\Controllers;
use Illuminate\Http\Request;
use App\Models\Area;
use App\Models\AreaEvent;
use Illuminate\Support\Facades\DB;
class DashboardController extends Controller
{
    public function index()
    {
        $today = now()->format(format: 'Y-m-d');
        $estados_areas = Area::with('estado')->get();
        $total_personas_dentro = $estados_areas->sum(fn($area) => $area->estado->people_count ?? 0);
        $areas_activas_count = $estados_areas->filter(fn($area) => ($area->estado->people_count ?? 0) > 0)->count();

        // Calcular Entradas y Salidas del día
        $entradas_hoy = AreaEvent::whereDate('timestamp', $today)
            ->where('event', 'enter')
            ->count();
        $salidas_hoy = AreaEvent::whereDate('timestamp', $today)
            ->where('event', 'exit')
            ->count();

        $kpis = [
            'total_personas' => $total_personas_dentro,
            'areas_activas' => $areas_activas_count,
            'entradas_hoy' => $entradas_hoy,
            'salidas_hoy' => $salidas_hoy,
        ];

        // Tabla de eventos Recientes
        $eventos_recientes = AreaEvent::with('area')
            ->orderBy('timestamp', 'desc')
            ->limit(10)
            ->get();

        return view('dashboard.index', compact('kpis', 'eventos_recientes', 'estados_areas'));
    }
    public function dataApi()
    {
        // obtener conteo por área para la gráficay lo demas
        $conteo_por_area = Area::with('estado')
            ->get()
            ->map(fn($area) => [
                'name' => $area->name,
                'count' => $area->estado->people_count ?? 0,
            ]);

        $total_personas_dentro = $conteo_por_area->sum('count');
        $areas_activas_count = $conteo_por_area->filter(fn($area) => $area['count'] > 0)->count();

        $today = now()->format('Y-m-d');

        $entradas_hoy = AreaEvent::whereDate('timestamp', $today)
            ->where('event', 'enter')
            ->count();

        $salidas_hoy = AreaEvent::whereDate('timestamp', $today)
            ->where('event', 'exit')
            ->count();

        $eventos_recientes = AreaEvent::with('area')
            ->orderBy('timestamp', 'desc')
            ->limit(10)
            ->get()
            ->map(function ($evento) {
                return [
                    'hora' => \Carbon\Carbon::parse($evento->timestamp)->format('H:i:s'),
                    'area_name' => $evento->area->name ?? 'N/A',
                    'event' => strtoupper($evento->event),
                    'track_id' => $evento->track_id,
                ];
            });

        return response()->json([
            'total_personas' => $total_personas_dentro,
            'areas_activas' => $areas_activas_count,
            'entradas_hoy' => $entradas_hoy,
            'salidas_hoy' => $salidas_hoy,
            'conteo_por_area' => $conteo_por_area,
            'eventos_recientes' => $eventos_recientes,
        ]);
    }
}