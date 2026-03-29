<?php

namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Session;

class LoginController extends Controller
{
    protected $apiUrl;

    public function __construct()
    {
        // Usamos el host 'api' si estamos en Docker, o localhost si es local.
        $this->apiUrl = config('services.api.url', 'http://api:8000');
    }

    public function showLoginForm()
    {
        if (Session::has('user')) {
            return redirect()->route('dashboard');
        }
        return view('auth.login');
    }

    public function login(Request $request)
    {
        $request->validate([
            'username' => 'required|string',
            'password' => 'required|string',
        ]);

        try {
            $response = Http::post($this->apiUrl . '/auth/login', [
                'username' => $request->username,
                'password' => $request->password,
            ]);

            if ($response->successful()) {
                $data = $response->json();
                Session::put('user', $data['user']);
                Session::put('is_admin', $data['user']['is_admin'] ?? false);
                
                return redirect()->route('dashboard')->with('success', '¡Bienvenido de nuevo!');
            }

            return back()->withErrors(['username' => 'Credenciales inválidas.'])->withInput();
        } catch (\Exception $e) {
            return back()->withErrors(['username' => 'Error de conexión con el servicio de autenticación.'])->withInput();
        }
    }

    public function logout()
    {
        Session::forget('user');
        Session::forget('is_admin');
        return redirect()->route('login')->with('info', 'Has cerrado sesión.');
    }
}
