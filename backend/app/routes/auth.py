"""Auth routes: password signup/login, OAuth, JWT session cookies."""

from __future__ import annotations

import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    SessionResponse,
    SignUpRequest,
    TenantMembership,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_password_user,
    create_tenant_and_user,
    find_or_create_oauth_user,
    user_to_response,
)
from app.services.jwt_service import AUTH_COOKIE, create_access_token, decode_access_token
from app.services.tenant_cognee import ensure_tenant_cognee_dataset
from app.tenancy import TENANT_COOKIE

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _provision_tenant_cognee_dataset(tenant_id: uuid.UUID) -> None:
    await ensure_tenant_cognee_dataset(tenant_id)

oauth = OAuth()


def _ensure_oauth_clients() -> None:
    """Register OAuth clients lazily so env vars are loaded before registration."""
    settings = get_settings()

    if settings.google_client_id and settings.google_client_secret:
        if oauth.create_client("google") is None:
            oauth.register(
                name="google",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                server_metadata_url=(
                    "https://accounts.google.com/.well-known/openid-configuration"
                ),
                client_kwargs={"scope": "openid email profile"},
            )

    if settings.github_client_id and settings.github_client_secret:
        if oauth.create_client("github") is None:
            oauth.register(
                name="github",
                client_id=settings.github_client_id,
                client_secret=settings.github_client_secret,
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com/",
                client_kwargs={"scope": "read:user user:email"},
            )


def _get_oauth_client(provider: str):
    _ensure_oauth_clients()
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=f"{provider.title()} OAuth is not configured on the server.",
        )
    return client


def _oauth_configured(provider: str) -> bool:
    settings = get_settings()
    if provider == "google":
        return bool(settings.google_client_id and settings.google_client_secret)
    if provider == "github":
        return bool(settings.github_client_id and settings.github_client_secret)
    return False


def _set_auth_cookies(response: Response, token: str, tenant_id: uuid.UUID) -> None:
    settings = get_settings()
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.jwt_expire_seconds,
        path="/",
    )
    response.set_cookie(
        key=TENANT_COOKIE,
        value=str(tenant_id),
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.jwt_expire_seconds,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE, path="/")
    response.delete_cookie(TENANT_COOKIE, path="/")


def _auth_response(
    response: Response,
    user: User,
    tenant: Tenant,
    *,
    is_new_user: bool,
) -> AuthResponse:
    token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        name=user.name,
    )
    _set_auth_cookies(response, token, tenant.id)
    return AuthResponse(
        user=user_to_response(user, tenant),
        is_new_user=is_new_user,
        access_token=token,
    )


def _redirect_after_auth(user: User, is_new_user: bool) -> str:
    settings = get_settings()
    if is_new_user or not user.onboarded:
        return f"{settings.frontend_url}/onboarding"
    return f"{settings.frontend_url}/dashboard"


def _get_token_from_request(request: Request) -> str | None:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
    return token


def _get_user_from_request(request: Request, db: Session) -> tuple[User, Tenant] | None:
    token = _get_token_from_request(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id") or payload.get("sub")
    tenant_id_claim = payload.get("tenant_id")
    if not user_id or not tenant_id_claim:
        return None

    user = db.query(User).filter(User.id == uuid.UUID(str(user_id))).one_or_none()
    if not user:
        return None

    tenant_uuid = uuid.UUID(str(tenant_id_claim))
    membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant_uuid,
        )
        .one_or_none()
    )
    if not membership:
        home_membership = (
            db.query(UserTenantMembership)
            .filter(
                UserTenantMembership.user_id == user.id,
                UserTenantMembership.tenant_id == user.tenant_id,
            )
            .one_or_none()
        )
        if not home_membership:
            db.add(
                UserTenantMembership(
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                )
            )
            db.commit()
        tenant_uuid = user.tenant_id

    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).one_or_none()
    if not tenant:
        return None

    return user, tenant


@router.post("/signup", response_model=AuthResponse)
def sign_up(
    payload: SignUpRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AuthResponse:
    try:
        user, tenant, _ = create_tenant_and_user(
            db,
            email=payload.email,
            name=payload.name,
            company_name=payload.company,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    background_tasks.add_task(_provision_tenant_cognee_dataset, tenant.id)
    return _auth_response(response, user, tenant, is_new_user=True)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    try:
        user = authenticate_password_user(
            db, email=payload.email, password=payload.password
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).one()
    return _auth_response(response, user, tenant, is_new_user=False)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    _clear_auth_cookies(response)
    return {"status": "logged_out"}


@router.get("/me", response_model=SessionResponse)
def get_me(request: Request, db: Session = Depends(get_db)) -> SessionResponse:
    token = _get_token_from_request(request)
    session = _get_user_from_request(request, db)
    if not session or not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user, tenant = session
    return SessionResponse(user=user_to_response(user, tenant), access_token=token)


@router.get("/tenants", response_model=list[TenantMembership])
def list_user_tenants(
    request: Request,
    db: Session = Depends(get_db),
) -> list[TenantMembership]:
    session = _get_user_from_request(request, db)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user, active_tenant = session

    memberships = (
        db.query(UserTenantMembership, Tenant)
        .join(Tenant, UserTenantMembership.tenant_id == Tenant.id)
        .filter(UserTenantMembership.user_id == user.id)
        .order_by(Tenant.company_name)
        .all()
    )
    return [
        TenantMembership(
            id=tenant.id,
            company_name=tenant.company_name,
            slug=tenant.slug,
            is_active=tenant.id == active_tenant.id,
        )
        for _, tenant in memberships
    ]


@router.post("/switch-tenant/{tenant_id}", response_model=SessionResponse)
def switch_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = _get_user_from_request(request, db)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user, _ = session

    membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant_id,
        )
        .one_or_none()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Tenant access denied.")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one()
    token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        name=user.name,
    )
    _set_auth_cookies(response, token, tenant.id)
    return SessionResponse(user=user_to_response(user, tenant), access_token=token)


@router.post("/onboarding/complete", response_model=SessionResponse)
def complete_onboarding(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = _get_user_from_request(request, db)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user, tenant = session
    user.onboarded = True
    db.commit()
    db.refresh(user)
    token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        name=user.name,
    )
    _set_auth_cookies(response, token, tenant.id)
    return SessionResponse(user=user_to_response(user, tenant), access_token=token)


@router.get("/providers")
def auth_providers() -> dict[str, bool]:
    return {
        "google": _oauth_configured("google"),
        "github": _oauth_configured("github"),
    }


@router.get("/oauth/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
    next_path: str = Query(default="/dashboard", alias="next"),
):
    if provider not in ("google", "github"):
        raise HTTPException(status_code=404, detail="Unknown OAuth provider.")
    if not _oauth_configured(provider):
        raise HTTPException(
            status_code=503,
            detail=f"{provider.title()} OAuth is not configured on the server.",
        )

    redirect_uri = str(request.url_for("oauth_callback", provider=provider))
    request.session["oauth_next"] = next_path
    client = _get_oauth_client(provider)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/oauth/{provider}/callback", name="oauth_callback")
async def oauth_callback(
    provider: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if provider not in ("google", "github"):
        raise HTTPException(status_code=404, detail="Unknown OAuth provider.")
    if not _oauth_configured(provider):
        raise HTTPException(
            status_code=503,
            detail=f"{provider.title()} OAuth is not configured on the server.",
        )

    client = _get_oauth_client(provider)
    token = await client.authorize_access_token(request)

    if provider == "google":
        userinfo = token.get("userinfo")
        if not userinfo:
            try:
                userinfo = await client.parse_id_token(request, token)
            except Exception:
                userinfo = None
        if not userinfo:
            resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                token=token,
            )
            userinfo = resp.json()
        email = userinfo.get("email")
        name = userinfo.get("name") or (email.split("@")[0] if email else "Google User")
        subject = userinfo.get("sub")
    else:
        resp = await client.get("user", token=token)
        profile = resp.json()
        email = profile.get("email")
        if not email:
            emails_resp = await client.get("user/emails", token=token)
            emails = emails_resp.json()
            primary = next(
                (item for item in emails if item.get("primary")),
                emails[0] if emails else None,
            )
            email = primary.get("email") if primary else None
        name = profile.get("name") or profile.get("login") or "GitHub User"
        subject = str(profile.get("id"))

    if not email or not subject:
        raise HTTPException(status_code=400, detail="OAuth provider did not return email.")

    try:
        user, tenant, is_new_user = find_or_create_oauth_user(
            db,
            email=email,
            name=name,
            provider=provider,
            subject=subject,
        )
    except ValueError as exc:
        settings = get_settings()
        return RedirectResponse(
            url=f"{settings.frontend_url}/?auth_error={str(exc)}",
            status_code=302,
        )

    if is_new_user:
        background_tasks.add_task(_provision_tenant_cognee_dataset, tenant.id)

    jwt_token = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        name=user.name,
    )
    redirect_url = request.session.pop("oauth_next", None) or _redirect_after_auth(
        user, is_new_user
    )
    if redirect_url.startswith("/"):
        redirect_url = f"{get_settings().frontend_url}{redirect_url}"

    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_auth_cookies(response, jwt_token, tenant.id)
    return response
