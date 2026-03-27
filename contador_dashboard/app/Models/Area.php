<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
class Area extends Model
{
    use HasFactory;
    protected $table = 'areas';
    public $timestamps = false;
    public function estado()
    {
        return $this->hasOne(AreaState::class, 'area_id', 'id');
    }
    public function eventos()
    {
        return $this->hasMany(AreaEvent::class, 'area_id', 'id');
    }
}