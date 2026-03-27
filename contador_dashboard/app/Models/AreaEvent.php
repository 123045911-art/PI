<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
class AreaEvent extends Model
{
    use HasFactory;

    protected $table = 'area_events';
    public $timestamps = false;
    public function area()
    {
        return $this->belongsTo(Area::class, 'area_id', 'id');
    }
}