# Swagger Module Overview

Source: [modules/Swagger/swagger.py](../../modules/Swagger/swagger.py)

The Swagger module serves the landing page of the Flash Server. It has no database and no templates folder. The page is an inline HTML string rendered with `render_template_string`, and the API description is a Python dict.

---

## 1. Routes

| Route | Description |
| :--- | :--- |
| `/`, `/docs` | Swagger UI console (`SWAGGER_HTML_TEMPLATE`), styled with `/static/shared.css`. |
| `/openapi.json`, `/swagger.json` | The `OPENAPI_SPEC` dict returned as JSON. |
| `/favicon.ico` | `index/static/flash.png`. |

All routes sit behind the HTTP Basic Auth hook in [index/index.py](../../index/index.py).

---

## 2. How the spec is built

`OPENAPI_SPEC` is a hand-maintained OpenAPI 3.0.3 dict. It is **not** generated from the Flask routes, so a new endpoint only shows up in the console after you add it to the dict.

* **`servers`**: always `/` (current host) and `http://localhost:5000`. If `APP_HOST` is set in `config/config.json`, it is added as the "Dev Production Server".
* **`tags`**: one per module (`Tutoring Calculator`, `Monitoring`, `To Do`, `Invoices`, `Finance`). Every operation's `tags` entry must name one of these.
* **`components.securitySchemes`**: HTTP Basic, which powers the "Authorize" button.
* **`paths`**: keyed by the OpenAPI form of the Flask rule (`/api/todo/items/{item_id}`).

### Adding an endpoint to the docs

1. Add the path and method to `OPENAPI_SPEC["paths"]` using the `{param}` form for path variables.
2. Give it a declared `tag`, declare every path parameter, and add at least one response.
3. Run the Swagger tests (see [testing.md](testing.md)). They fail if you document a route that Flask does not serve, or leave a real endpoint undocumented.

---

## 3. Keeping the spec complete

`test_every_handler_is_documented` fails when a Flask handler (endpoint plus HTTP method) has no entry in the spec. A handler with several URL aliases only needs one of them documented, so the `/api/tutoring/*` form is documented and the legacy aliases (`/api/run-calc`, `/run-calc`, and so on) are not. The prefixed registrations (`/TutoringCalculator/...`, `/InvoiceGenerator/...`, `/Finance/...`) and the Swagger module's own routes are skipped.

Methods that share a handler (for example `PUT` and `PATCH`) are added with `_add_method_alias()` at the bottom of `swagger.py` instead of repeating the whole operation.

---

## 4. UI notes

The top navigation bar links to `/monitoring`, `/tutoring`, `/todo`, `/invoices`, and `/finance`. Theme (light/dark) is toggled client-side with the `day-and-night.svg` icon, and the preference is stored in the browser.
