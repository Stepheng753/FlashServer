# Index & Security Module

The `index` package houses the core HTTP Basic Authentication middleware and security boundary for Stephen Giang's Flash Server.

---

## 1. Responsibilities & Architecture

* **Centralized Authentication Middleware**: Implemented as a Flask `before_request` hook in `app.py`. Enforces HTTP Basic Authentication (`WWW-Authenticate: Basic realm="Login Required"`) across all web pages and REST API routes.
* **Credentials Discovery**: Automatically resolves `USERNAME` and `PASSWORD` from `config/secrets.json` (falling back to `config/config.json`).
* **Route Exemption Safeguards**: Selectively bypasses authentication only for:
  * Static brand assets and the shared stylesheet (`/static/*`, incl. `shared.css`, `/favicon.ico`)
  * Public Privacy Policy (`/privacy`, `/TutoringCalculator/privacy`) required for Google Cloud OAuth verification
  * Google OAuth callback redirect (`/login_oauth`) when containing an authorization code

---

## 2. Functions Reference

* **`get_auth_credentials()`**:
  * Traverses `config/` and project root directories for `secrets.json` and `config.json`.
  * Returns `(username, password)`.
* **`check_auth()`**:
  * Evaluates `request.path` against the whitelist.
  * Parses the `Authorization: Basic <base64>` request header.
  * Validates credentials against expected user secrets.
  * Returns `None` if allowed, or a `401 Unauthorized` response with standard authentication challenges.

---

## 3. Package Structure

```
index/
├── index.py                   # Core auth evaluation and credentials resolution
└── README.md                  # Module technical reference
```
