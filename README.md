# GLOA Identity

The one login behind every GLOA staff app: the shared Cognito **user pool**, its **groups**, the
**post-login hook**, and **login.galaxref.com** (the shared sign-in page). Every GLOA staff
account lives here, so this stack changes rarely and only through reviewed change sets.

| | |
|---|---|
| Stack | `gloa-identity` (us-east-1, AWS profile `gloa`) |
| User pool | `us-east-1_oXFiLITO7` (name `gloa-observation-app-UserPool`, see History) |
| Sign-in page | https://login.galaxref.com (Cognito managed login, version 2) |
| Exports | `gloa-identity-UserPoolId`, `gloa-identity-UserPoolArn`, `gloa-identity-LoginDomain` |
| Part of | GLOA App Refinement Plan, Part 2 (`../GLOA-APP-REFINEMENT-PLAN.md`) |

## What's in the stack

| Resource | What it is |
|---|---|
| `UserPool` | Every staff account (one email + password for every GLOA app). `DeletionPolicy: Retain` and Cognito **deletion protection**: no stack operation can delete it. |
| `PostAuthFunction` (`gloa-identity-PostAuth`) | Runs after every successful sign-in and stamps `custom:lastLogin` (shown in User Admin). Never blocks a sign-in; failures are only logged (`/aws/lambda/gloa-identity-PostAuth`, 90 days). |
| 8 app groups | `observation-`, `registration-`, `validation-`, `playoffs-` × `admins`/`users`. `Retain`, so memberships survive even if the stack is deleted. |
| `LoginDomain` | `login.galaxref.com` → Cognito's own CloudFront distribution (see DNS). |

`gloa-user-admins` (access to User Admin) lives in the **GLOA-Apps-Portal** stack, next to the
admin app that uses it.

## Pool settings (and why)

| Setting | Value | Why |
|---|---|---|
| Sign-up | Admin-only (`AllowAdminCreateUserOnly`) | Accounts are only created by invitation (User Admin) |
| Username | Email | |
| Password | 8+ characters, upper, lower, number; temporary passwords last 7 days | |
| Sign-in | Password only (`SignInPolicy`) | Emailed codes for officials are Plan Phase 3 |
| MFA | Off | Deferred (see the plan) |
| Email | From `GLOA <webmaster@galaxref.com>` via SES (DKIM verified) | Instead of `no-reply@verificationemail.com` |
| Welcome email | "Your GLOA login is ready", points to https://apps.galaxref.com | Wording to be reviewed with the board (Plan TODO) |
| Reset/verification email | "Your GLOA verification code" | |
| Custom attribute | `custom:lastLogin` (mutable string) | Added 2026-10-06 with `AddCustomAttributes`; **not in the template** on purpose (custom attributes can't be removed and the template's `Schema` isn't the place to add them to a live pool) |
| Tier | Essentials | Includes managed login and up to 10,000 monthly active users free |

The template spells out every setting, even ones at their defaults: a CloudFormation update
rewrites the whole pool configuration, so anything left out would be reset.

## Groups (naming scheme)

`<app>-admins` and `<app>-users`, lowercase. `gloa-` is reserved for GLOA-wide groups. The list
must match the app list in `GLOA-Apps-Portal/backend/apps.js` (cards and the User Admin grid).

| App | Admins | Users |
|---|---|---|
| Observation | `observation-admins`: officials, observers, scheduling | `observation-users`: observers |
| Coaches Registration | `registration-admins`: school list, registrations, CSV | `registration-users`: view + CSV |
| Officials Validation | `validation-admins`: run the app | `validation-users`: leadership (view, reports, follow-up) |
| Playoff Eligibility | `playoffs-admins`: everything incl. overrides, sync | `playoffs-users`: read-only |

The older groups (`Administrators`, `Observers`, `CoachesRegistrationAdministrators`,
`CoachesRegistrationUsers`, `OfficialsValidationAdmins`) belong to the app stacks and are retired
as each app switches to the new names (Plan Phase 1).

## Apps using the pool

Each app has its own app client in the pool and refers to the pool by a `UserPoolId` template
parameter (default `us-east-1_oXFiLITO7`).

| App | Stack | App client |
|---|---|---|
| Observation App | `gloa-observation-app` | `gloa-observation-app-WebClient` |
| Coaches Registration (admin) | `gloa-coaches-registration` | `gloa-coaches-registration-AdminWebClient` |
| Officials Validation (admin) | `gloa-officials-validation` | `gloa-officials-validation-AdminWebClient` |
| Apps Portal + User Admin | `gloa-apps-portal` | `gloa-apps-portal-WebClient` |

Playoff Eligibility still uses its own pool (`gloa-playoff-eligibility`) until Plan Phase 1 moves it
here.

## DNS (Cloudflare)

| Record | Type | Target | Proxy |
|---|---|---|---|
| `login` | CNAME | `d2ltc4uud0dew3.cloudfront.net` (stack output `LoginDomainCloudFront`) | **DNS only** |

The `*.galaxref.com` ACM certificate (us-east-1, auto-renewing) covers it. Cognito custom domains
also require the root `galaxref.com` to resolve, which it does.

## Sign-in page look (branding)

Cognito keeps one managed-login "style" per app client. All of them get the same GLOA look from
`branding/`, applied by a script rather than by each app's template (one copy, not one per app):

| File | What |
|---|---|
| `branding/settings.json` | Cognito's style settings with GLOA changes: navy `#003366` buttons, links and focus outlines; logo centered at the top of the sign-in box; no page header; light grey page background; light mode only |
| `branding/form-logo.png` | GLOA shield (cut from the site banner, transparent background) + "Georgia Lacrosse Officials Association" in navy Arial Bold, 1170×300 (3.9:1). Cognito shows the form logo at a fixed small height and requires 1:1–4:1, so a wide lockup uses the most space |
| `branding/default-assets.json` | Cognito's own icons/graphics (light mode), kept so nothing on the page goes blank; third-party sign-in icons removed |

```bash
python3 scripts/apply_branding.py --dry-run   # which app clients it would style
python3 scripts/apply_branding.py             # apply to every client that signs in via login.galaxref.com
```

Cognito's page doesn't allow custom text (wording like "Sign in to your account" is fixed), and
the page-header logo slot is small, so a wide banner shrinks to nothing; hence the shield in the
form instead (decided 2026-10-06).

Cognito shows the form logo at most 60px tall × 240px wide (`object-fit: contain`, from its
stylesheet), so a logo up to 4:1 fills the width. **After changing an image,** browsers that saw
the old one keep showing it: Cognito serves assets with a one-year `immutable` cache header at the
same URL. Check changes in a brand-new private window (close all private windows first).

Run it after changing anything in `branding/` and right after converting an app to
login.galaxref.com (that's when its client becomes OAuth-enabled and needs a style).

## Deploying

```bash
./scripts/deploy.sh            # creates a change set, shows it, asks before applying
./scripts/deploy.sh --preview  # change set only
```

Check every change set: the pool must only ever show **Modify** with **Replacement: False**.
Never anything that replaces or removes `UserPool`.

## History

- **2026-03-27:** Pool created by the GLOA Observation App stack (hence its name).
- **2026-10-06:** Phase 0: self-registration closed, webmaster sender, welcome/reset emails,
  deletion protection, `custom:lastLogin`.
- **2026-10-06:** **Moved to this stack** without recreating it:
  1. Coaches Registration, Officials Validation and the Apps Portal switched from importing the
     Observation stack's export to a `UserPoolId` parameter. Their change sets predicted the app
     clients and groups would be *replaced*; a test on throwaway stacks proved CloudFormation
     compares resolved values and leaves them untouched, and each real deploy was verified
     against a snapshot (same client IDs, group creation dates, members, users).
  2. The Observation App stack marked the pool `Retain`, switched its own references to the
     parameter, then removed it (`DELETE_SKIPPED`: released, not deleted).
  3. Imported into `gloa-identity` (`IMPORT_COMPLETE`; drift check `IN_SYNC`).
  4. Added the post-login hook (replacing the Observation App's), the 8 app groups and
     login.galaxref.com.
- **2026-10-06:** Apps Portal signs in through login.galaxref.com; GLOA branding applied.
- The pool keeps its original name: renaming isn't needed for anything and isn't worth the risk.

## Still to do

- Each remaining app signs in through login.galaxref.com (single sign-on, Plan Phase 2). The
  Apps Portal was first (2026-10-06): OAuth code + PKCE, then `apply_branding.py`.
- Remove the Observation App's old, now-unused post-login function.
- Move `gloa-user-admins` here? (Currently in the portal stack; either works.)
- Officials join with emailed-code sign-in (Plan Phase 3).
