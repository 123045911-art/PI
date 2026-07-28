<?php

namespace App\Http\Controllers;

use Illuminate\Support\Facades\Session;

abstract class Controller
{
    protected function apiAuthHeaders(): array
    {
        $token = Session::get('access_token');
        if (!$token) {
            return [];
        }
        return ['Authorization' => 'Bearer ' . $token];
    }
}
