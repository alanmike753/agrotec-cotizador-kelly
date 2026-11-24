from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .discount_policy import validate_kelly_discounts


class CalculationRequest(BaseModel):
    profit_mode: Literal["markup", "fixed"] = "markup"
    profit_value: str = "25"
    rounding_increment: Literal["1", "10", "50", "100"] = "1"
    discounts: list[str] | None = None

    @field_validator("discounts")
    @classmethod
    def validate_temporary_discounts(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return validate_kelly_discounts(values, label="Los descuentos temporales")


class CommercialPreferenceInput(BaseModel):
    profit_mode: Literal["markup", "fixed"]
    profit_value: str
    rounding_increment: Literal["1", "10", "50", "100"]

    @field_validator("profit_value")
    @classmethod
    def validate_profit_value(cls, value: str) -> str:
        from decimal import Decimal, InvalidOperation

        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("La ganancia debe ser un decimal válido.") from exc
        if number < 0:
            raise ValueError("La ganancia no puede ser negativa.")
        return format(number, "f")


class RuleInput(BaseModel):
    discounts: list[str] = Field(min_length=1)
    explicit_zero: bool = False
    name: str = "Regla configurada localmente"

    @field_validator("discounts")
    @classmethod
    def validate_discounts(cls, values: list[str]) -> list[str]:
        return validate_kelly_discounts(values)

    @model_validator(mode="after")
    def validate_zero(self):
        if self.explicit_zero:
            raise ValueError("El 0% se configura en la tercera etapa; no requiere una marca adicional.")
        return self


class ProductUpdate(BaseModel):
    family: str | None = None
    default_markup_pct: str | None = None


class BulkFamilyUpdate(BaseModel):
    product_ids: list[str] = Field(min_length=1)
    family: str | None = None


class RulePreviewRequest(BaseModel):
    scope_type: Literal["family", "products"] = "products"
    scope_key: str | None = None
    product_ids: list[str] = Field(default_factory=list)
    rule: RuleInput

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope_type == "family" and not (self.scope_key and self.scope_key.strip()):
            raise ValueError("La vista previa familiar requiere una familia.")
        if self.scope_type == "products" and not self.product_ids:
            raise ValueError("Selecciona al menos un implemento.")
        return self


class RuleApplyRequest(BaseModel):
    scope_type: Literal["family", "product"]
    scope_key: str
    rule: RuleInput


class BulkProductRuleApplyRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1)
    rule: RuleInput


class SettingUpdate(BaseModel):
    default_markup_pct: str


class LoginInput(BaseModel):
    email: str
    password: str


class UserCreateInput(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "seller"] = "seller"


class UserUpdateInput(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    password: str | None = Field(default=None, min_length=12, max_length=256)
    role: Literal["admin", "seller"] | None = None
    is_active: bool | None = None

