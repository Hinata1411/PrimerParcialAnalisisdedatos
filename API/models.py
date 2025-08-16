# models.py
from pydantic import BaseModel, Field, field_validator
from uuid import UUID, uuid4
from typing import List
from typing import Optional
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import unicodedata, re

CATEGORIAS_PERMITIDAS = {
    "fruta","verdura","grano","legumbre","lacteo","carnico",
    "procesado","organico","bebida","especia"
}
_name_re = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-_.]{2,79}$")

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=80)
    precio: Decimal = Field(gt=0, le=Decimal("1000000"))
    categorias: List[str] = Field(min_items=1, max_items=10)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = " ".join(v.strip().split())
        if not _name_re.match(v):
            raise ValueError("Nombre inválido (3-80, letras/números/ - _ .)")
        return v

    @field_validator("precio")
    @classmethod
    def validar_precio(cls, v: Decimal) -> Decimal:
        try:
            q = v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            raise ValueError("Precio inválido")
        if q <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        return q

    @field_validator("categorias")
    @classmethod
    def validar_categorias(cls, valores: List[str]) -> List[str]:
        limpias, vistos = [], set()
        for c in valores:
            c_norm = _strip_accents(" ".join(c.strip().lower().split()))
            if not c_norm or c_norm not in CATEGORIAS_PERMITIDAS:
                raise ValueError(f"Categoría no permitida: {c}")
            if c_norm not in vistos:
                limpias.append(c_norm)
                vistos.add(c_norm)
        return limpias

class ProductoOut(ProductoCreate):
    id: UUID = Field(default_factory=uuid4)

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=3, max_length=80)
    precio: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("1000000"))
    categorias: Optional[List[str]] = Field(default=None, min_items=1, max_items=10)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = " ".join(v.strip().split())
        if not _name_re.match(v):
            raise ValueError("Nombre inválido (3-80, letras/números/ - _ .)")
        return v

    @field_validator("precio")
    @classmethod
    def validar_precio(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        try:
            q = v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            raise ValueError("Precio inválido")
        if q <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        return q

    @field_validator("categorias")
    @classmethod
    def validar_categorias(cls, valores: Optional[List[str]]) -> Optional[List[str]]:
        if valores is None:
            return valores
        limpias, vistos = [], set()
        for c in valores:
            c_norm = _strip_accents(" ".join(c.strip().lower().split()))
            if not c_norm or c_norm not in CATEGORIAS_PERMITIDAS:
                raise ValueError(f"Categoría no permitida: {c}")
            if c_norm not in vistos:
                limpias.append(c_norm)
                vistos.add(c_norm)
        return limpias


class ProductosPage(BaseModel):
    total: int
    items: List[ProductoOut]