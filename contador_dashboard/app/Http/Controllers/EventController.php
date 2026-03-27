<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Models\AreaEvent;

class EventController extends Controller
{
    public function index()
    {
        $eventos = AreaEvent::with('area')
            ->orderBy('timestamp', 'desc')
            ->paginate(50);
        return view('eventos.index', compact('eventos'));
    }
}