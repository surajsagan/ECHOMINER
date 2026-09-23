from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    full_name: str = Field(min_length=2, max_length=200)
    designation: str = Field(min_length=2, max_length=200)
    affiliation: str = Field(min_length=2, max_length=300)
    institute: str = Field(min_length=2, max_length=300)
    taluk: Optional[str] = Field(default=None, max_length=120)
    district: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=120)
    country_iso2: str = Field(min_length=2, max_length=2)
    email: EmailStr
    phone_e164: Optional[str] = Field(default=None, max_length=20)
    project_title: str = Field(min_length=2, max_length=300)
    project_description: str = Field(min_length=2)
    purpose: str = Field(min_length=2)
    agreement_accepted: bool
    agreement_text: str = Field(min_length=1)
    captcha_token: str

    @field_validator("country_iso2")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("agreement_accepted")
    @classmethod
    def _must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("the copyright and usage agreement must be accepted")
        return v


class RegistrationResponse(BaseModel):
    status: str
    email: EmailStr
    otp_required: bool = True


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)


class OtpResendRequest(BaseModel):
    email: EmailStr
    captcha_token: str


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    email: EmailStr
    full_name: str
    institute: str
    country_iso2: str
    status: str
