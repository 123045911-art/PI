<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Session;

class UserController extends Controller
{
    protected $apiUrl;

    public function __construct()
    {
        $this->apiUrl = config('services.api.url', 'http://api:8000');
    }

    /**
     * Middleware check for admin is handled in routes or here.
     * We'll add it here for extra safety.
     */
    protected function checkAdmin()
    {
        if (!Session::get('is_admin')) {
            abort(403, 'Acceso denegado: Se requieren permisos de administrador.');
        }
    }

    public function index(Request $request)
    {
        $this->checkAdmin();
        
        try {
            $name = $request->input('name');
            $response = Http::withHeaders([
                'X-Is-Admin' => Session::get('is_admin', false)
            ])->get($this->apiUrl . '/users', [
                'name' => $name
            ]);
            
            if ($response->successful()) {
                $users = collect($response->json());
                return view('users.index', compact('users'));
            }
            throw new \Exception("Error API: " . $response->status());
        } catch (\Exception $e) {
            Log::error("User Index Error: " . $e->getMessage());
            return view('users.index', ['users' => collect([])])->with('error', 'No se pudieron cargar los usuarios.');
        }
    }

    public function create()
    {
        $this->checkAdmin();
        return view('users.create');
    }

    public function store(Request $request)
    {
        $this->checkAdmin();
        
        $request->validate([
            'username' => 'required|string|max:50',
            'password' => 'required|string|min:4',
            'is_admin' => 'nullable'
        ]);

        try {
            $response = Http::withHeaders([
                'X-Is-Admin' => Session::get('is_admin', false)
            ])->post($this->apiUrl . '/users/', [
                'username' => $request->username,
                'password' => $request->password,
                'is_admin' => $request->has('is_admin')
            ]);

            if ($response->successful()) {
                return redirect()->route('users.index')->with('success', 'Usuario creado exitosamente.');
            }
            
            $detail = $response->json()['detail'] ?? 'Error al crear usuario.';
            return back()->withInput()->with('error', $detail);
        } catch (\Exception $e) {
            return back()->withInput()->with('error', 'Error de conexión: ' . $e->getMessage());
        }
    }

    public function edit($id)
    {
        $this->checkAdmin();
        
        try {
            $response = Http::withHeaders([
                'X-Is-Admin' => Session::get('is_admin', false)
            ])->get($this->apiUrl . '/users/' . $id);
            if ($response->successful()) {
                $user = (object)$response->json();
                return view('users.edit', compact('user'));
            }
            return redirect()->route('users.index')->with('error', 'Usuario no encontrado.');
        } catch (\Exception $e) {
            return redirect()->route('users.index')->with('error', 'Error al buscar el usuario.');
        }
    }

    public function update(Request $request, $id)
    {
        $this->checkAdmin();
        
        $request->validate([
            'username' => 'required|string|max:50',
            'password' => 'nullable|string|min:4',
            'is_admin' => 'nullable'
        ]);

        try {
            $payload = [
                'username' => $request->username,
                'is_admin' => $request->has('is_admin')
            ];
            if ($request->filled('password')) {
                $payload['password'] = $request->password;
            }

            $response = Http::withHeaders([
                'X-Is-Admin' => Session::get('is_admin', false)
            ])->put($this->apiUrl . '/users/' . $id, $payload);

            if ($response->successful()) {
                return redirect()->route('users.index')->with('success', 'Usuario actualizado.');
            }
            
            return back()->with('error', 'Error al actualizar el usuario.');
        } catch (\Exception $e) {
            return back()->with('error', 'Error de conexión: ' . $e->getMessage());
        }
    }

    public function destroy($id)
    {
        $this->checkAdmin();
        
        try {
            $response = Http::withHeaders([
                'X-Is-Admin' => Session::get('is_admin', false)
            ])->delete($this->apiUrl . '/users/' . $id);
            if ($response->successful()) {
                return redirect()->route('users.index')->with('success', 'Usuario eliminado.');
            }
            return redirect()->route('users.index')->with('error', 'Error al eliminar el usuario.');
        } catch (\Exception $e) {
            return redirect()->route('users.index')->with('error', 'Error de conexión.');
        }
    }
}
