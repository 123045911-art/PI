<?php
namespace App\Http\Controllers;
use Illuminate\Http\Request;
use App\Models\Area;
use App\Models\AreaState;
use App\Models\AreaEvent;
class AreaController extends Controller
{
    public function index()
    {
        $areas = Area::with('estado')->orderBy('id', 'asc')->get();
        return view('areas.index', compact('areas'));
    }

    //formulario para editar un área
    public function edit(Area $area)
    {
        return view('areas.edit', compact('area'));
    }
    public function update(Request $request, Area $area)
    {
        // Validación del nuevo nombre
        $request->validate([
            'name' => 'required|string|max:255',
        ]);
        // Actualización en la BD
        try {
            $area->name = $request->input('name');
            $area->save();
            // Alerta de éxito
            return redirect()->route('areas.index')
                ->with('success', 'El área "' . $area->name . '" ha sido renombrada exitosamente.');
        } catch (\Exception $e) {
            // Alerta de error
            return redirect()->route('areas.index')
                ->with('error', 'Error al renombrar el área: ' . $e->getMessage());
        }
    }
    // Elimina un area
    public function destroy(Area $area)
    {
        $areaName = $area->name;
        try {
            AreaState::where('area_id', $area->id)->delete();
            AreaEvent::where('area_id', $area->id)->delete();
            $area->delete();
            return redirect()->route('areas.index')
                ->with('success', 'El área "' . $areaName . '" y sus datos asociados han sido eliminados.');
        } catch (\Exception $e) {
            return redirect()->route('areas.index')
                ->with('error', 'Error al eliminar el área: ' . $e->getMessage());
        }
    }
}